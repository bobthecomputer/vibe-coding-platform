from __future__ import annotations

import pathlib
import io
import json
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent import web_backend
from grant_agent.web_backend import (
    FluxioWebBackend,
    MISSION_ACTION_TIMEOUT_SECONDS,
    MISSION_START_TIMEOUT_SECONDS,
    OpenAICodexOAuthSession,
    MiniMaxOAuthSession,
    add_or_reset_admin_user,
)


class FluxioWebBackendTests(unittest.TestCase):
    def test_provider_secret_presence_uses_session_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "",
                    "ANTHROPIC_API_KEY": "",
                    "OPENROUTER_API_KEY": "",
                    "MINIMAX_API_KEY": "",
                    "MINIMAX_OAUTH_TOKEN": "",
                    "FLUXIO_OPENAI_CODEX_OAUTH_PRESENT": "",
                    "FLUXIO_MINIMAX_OPENCLAW_OAUTH_PRESENT": "",
                    "HOME": str(root / "home"),
                    "OPENCLAW_STATE_DIR": str(root / "home" / ".openclaw"),
                },
            ):
                before = backend.dispatch(
                    "get_provider_secret_presence_command",
                    {"providerIds": ["openai", "openai-codex", "minimax"]},
                )
                self.assertFalse(before["openai"])
                self.assertFalse(before["openai-codex"])

                self.assertTrue(
                    backend.dispatch(
                        "save_provider_secret_command",
                        {"providerId": "openai", "secret": "test-key"},
                    )
                )
                after = backend.dispatch(
                    "get_provider_secret_presence_command",
                    {"providerIds": ["openai", "openai-codex", "minimax"]},
                )
                self.assertTrue(after["openai"])
                self.assertTrue(after["openai-codex"])
                self.assertFalse(after["minimax"])

                self.assertTrue(
                    backend.dispatch("clear_provider_secret_command", {"providerId": "openai"})
                )
                cleared = backend.dispatch(
                    "get_provider_secret_presence_command",
                    {"providerIds": ["openai", "openai-codex"]},
                )
                self.assertFalse(cleared["openai"])
                self.assertFalse(cleared["openai-codex"])

    def test_web_backend_prepends_packaged_runtime_bin_to_cli_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            runtime_bin = root / ".agent_control" / "runtime" / "bin"
            runtime_bin.mkdir(parents=True)
            backend = FluxioWebBackend(root, root)

            env = backend._provider_env()

            self.assertIn("PATH", env)
            self.assertEqual(env["PATH"].split(__import__("os").pathsep)[0], str(runtime_bin))

    def test_web_backend_reports_minimax_openclaw_manual_auth_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {"HOME": str(root / "home"), "OPENCLAW_STATE_DIR": str(root / "home" / ".openclaw")},
            ):
                status = backend.dispatch("get_minimax_openclaw_auth_status_command", {})
            self.assertFalse(status["authenticated"])
            self.assertIn("credentialsPath", status)

            with mock.patch.dict(
                "os.environ",
                {"HOME": str(root / "home"), "OPENCLAW_STATE_DIR": str(root / "home" / ".openclaw")},
            ):
                with mock.patch(
                    "grant_agent.web_backend._request_minimax_oauth_code",
                    side_effect=RuntimeError("network unavailable"),
                ):
                    start = backend.dispatch(
                        "start_minimax_openclaw_auth_command",
                        {"payload": {"region": "global"}},
                    )
            self.assertTrue(start["manualRequired"])
            self.assertIn("openclaw models auth login", start["command"])
            self.assertEqual(start["method"], "oauth")

    def test_web_backend_starts_minimax_oauth_user_code_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {"HOME": str(root / "home"), "OPENCLAW_STATE_DIR": str(root / "home" / ".openclaw")},
            ):
                with mock.patch(
                    "grant_agent.web_backend._minimax_openclaw_auth_status",
                    return_value={"authenticated": False},
                ):
                    with mock.patch(
                        "grant_agent.web_backend._request_minimax_oauth_code",
                        return_value={
                            "user_code": "MM-1234",
                            "verification_uri": "https://api.minimax.io/oauth/verify",
                            "state": "",
                            "interval": 2000,
                            "expired_in": 1990000000000,
                        },
                    ):
                        result = backend.dispatch(
                            "start_minimax_openclaw_auth_command",
                            {"payload": {"region": "global"}},
                        )

            self.assertTrue(result["manualRequired"])
            self.assertEqual(result["providerId"], "minimax-portal")
            self.assertEqual(result["userCode"], "MM-1234")
            self.assertEqual(result["verificationUrl"], "https://api.minimax.io/oauth/verify")
            self.assertTrue(result["sessionId"])

    def test_web_backend_completes_minimax_oauth_user_code_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            session = MiniMaxOAuthSession(
                verifier="verifier",
                state="state",
                region="global",
                user_code="MM-1234",
                verification_url="https://api.minimax.io/oauth/verify",
                interval_ms=2000,
                expires_at_ms=1990000000000,
            )

            with mock.patch.dict(
                "os.environ",
                {"HOME": str(root), "OPENCLAW_STATE_DIR": str(root / ".openclaw")},
            ):
                with mock.patch.dict(
                    "grant_agent.web_backend._MINIMAX_OAUTH_SESSIONS",
                    {"minimax": session},
                    clear=True,
                ):
                    with mock.patch(
                        "grant_agent.web_backend._poll_minimax_oauth_token",
                        return_value={
                            "pending": False,
                            "access": "access",
                            "refresh": "refresh",
                            "expires": 1990000000000,
                        },
                    ):
                        with mock.patch(
                            "grant_agent.web_backend._minimax_openclaw_auth_status",
                            return_value={"authenticated": True},
                        ):
                            result = backend.dispatch(
                                "complete_minimax_openclaw_auth_command",
                                {"payload": {"sessionId": "minimax"}},
                            )

            self.assertTrue(result["authenticated"])
            auth_store = root / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
            payload = json.loads(auth_store.read_text(encoding="utf-8"))
            credential = payload["profiles"]["minimax-portal:default"]
            self.assertEqual(credential["provider"], "minimax-portal")
            self.assertEqual(credential["access"], "access")

    def test_minimax_status_does_not_claim_auth_store_source_without_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            home = root / "home"
            auth_store = home / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
            auth_store.parent.mkdir(parents=True)
            auth_store.write_text(
                json.dumps({"version": 1, "profiles": {"openai-codex:test": {"provider": "openai-codex"}}}),
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {"HOME": str(home), "OPENCLAW_STATE_DIR": str(home / ".openclaw")},
            ):
                status = backend.dispatch("get_minimax_openclaw_auth_status_command", {})

            self.assertFalse(status["authenticated"])
            self.assertIsNone(status["source"])

    def test_web_backend_reports_openai_codex_env_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
                status = backend.dispatch("get_openai_codex_oauth_status_command", {})

            self.assertTrue(status["authenticated"])

    def test_web_backend_reports_openai_codex_openclaw_auth_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            home = root / "home"
            auth_store = home / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
            auth_store.parent.mkdir(parents=True)
            auth_store.write_text(
                '{"profiles":{"openai-codex:test@example.com":{"provider":"openai-codex","access":"token","refresh":"refresh"}}}',
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict("os.environ", {"HOME": str(home), "OPENCLAW_STATE_DIR": str(home / ".openclaw")}):
                status = backend.dispatch("get_openai_codex_oauth_status_command", {})

            self.assertTrue(status["authenticated"])
            self.assertEqual(status["source"], "openclaw-auth-profile")

    def test_agent_chat_command_runs_openclaw_with_selected_non_codex_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            backend = FluxioWebBackend(root, root)
            calls: list[list[str]] = []

            def fake_run(args, **kwargs):
                calls.append(list(args))
                return mock.Mock(
                    returncode=0,
                    stdout='{"reply":"Hello from the selected model."}',
                    stderr="",
                )

            with mock.patch("grant_agent.web_backend.shutil.which", return_value="openclaw"):
                with mock.patch("grant_agent.web_backend.subprocess.run", side_effect=fake_run):
                    result = backend.dispatch(
                        "send_agent_chat_command",
                        {
                            "payload": {
                                "runtime": "openclaw",
                                "message": "hello",
                                "workspaceId": "workspace_primary",
                                "workspacePath": str(workspace),
                                "route": {
                                    "role": "executor",
                                    "provider": "openrouter",
                                    "model": "openai/gpt-5.3-codex",
                                    "effort": "medium",
                                },
                            }
                        },
                    )

            self.assertEqual(result["reply"], "Hello from the selected model.")
            self.assertEqual(calls[-1][1:4], ["infer", "model", "run"])
            self.assertIn("--prompt", calls[-1])
            self.assertIn("openai/gpt-5.3-codex", calls[-1])

    def test_agent_chat_command_uses_codex_cli_for_openai_codex_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            backend = FluxioWebBackend(root, root)
            calls: list[list[str]] = []

            def fake_run(args, **kwargs):
                calls.append(list(args))
                output_path = pathlib.Path(args[args.index("--output-last-message") + 1])
                output_path.write_text("pong", encoding="utf-8")
                return mock.Mock(returncode=0, stdout='{"type":"turn.completed"}', stderr="")

            with mock.patch("grant_agent.web_backend.shutil.which", return_value="codex"):
                with mock.patch("grant_agent.web_backend.subprocess.run", side_effect=fake_run):
                    result = backend.dispatch(
                        "send_agent_chat_command",
                        {
                            "payload": {
                                "runtime": "openclaw",
                                "message": "hello",
                                "workspaceId": "workspace_primary",
                                "workspacePath": str(workspace),
                                "route": {
                                    "role": "executor",
                                    "provider": "openai",
                                    "model": "gpt-5.3-codex",
                                    "effort": "medium",
                                },
                            }
                        },
                    )

            self.assertEqual(result["reply"], "pong")
            self.assertEqual(calls[-1][1], "exec")
            self.assertIn("gpt-5.3-codex", calls[-1])

    def test_agent_chat_prefers_minimax_portal_when_oauth_profile_is_connected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            home = root / "home"
            auth_store = home / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
            auth_store.parent.mkdir(parents=True)
            auth_store.write_text(
                '{"profiles":{"minimax-portal:default":{"provider":"minimax-portal","access":"token","refresh":"refresh"}}}',
                encoding="utf-8",
            )
            backend = FluxioWebBackend(root, root)

            with mock.patch.dict(
                "os.environ",
                {
                    "HOME": str(home),
                    "OPENCLAW_STATE_DIR": str(home / ".openclaw"),
                    "MINIMAX_API_KEY": "",
                    "MINIMAX_OAUTH_TOKEN": "",
                },
            ):
                route = backend._chat_route(
                    {"route": {"provider": "minimax", "model": "MiniMax-M2.7", "effort": "low"}}
                )

            self.assertEqual(route["provider"], "minimax-portal")
            self.assertEqual(route["model_id"], "minimax-portal/MiniMax-M2.7")

    def test_agent_chat_uses_wsl_hermes_when_native_cli_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            backend = FluxioWebBackend(root, root)
            calls: list[list[str]] = []

            def fake_which(name, *args, **kwargs):  # noqa: ANN001
                if name == "wsl":
                    return "wsl"
                return None

            def fake_run(args, **kwargs):
                calls.append(list(args))
                return mock.Mock(
                    returncode=0,
                    stdout='{"reply":"Hermes via WSL."}',
                    stderr="",
                )

            with mock.patch("grant_agent.web_backend.shutil.which", side_effect=fake_which):
                with mock.patch("grant_agent.web_backend._wsl_has_command", return_value=True):
                    with mock.patch("grant_agent.web_backend.subprocess.run", side_effect=fake_run):
                        result = backend.dispatch(
                            "send_agent_chat_command",
                            {
                                "payload": {
                                    "runtime": "hermes",
                                    "message": "hello",
                                    "workspaceId": "workspace_primary",
                                    "workspacePath": str(workspace),
                                    "route": {
                                        "role": "executor",
                                        "provider": "anthropic",
                                        "model": "claude-sonnet-4.5",
                                        "effort": "medium",
                                    },
                                }
                            },
                        )

            self.assertEqual(result["runtime"], "hermes")
            self.assertEqual(result["reply"], "Hermes via WSL.")
            self.assertEqual(calls[-1][0], "wsl")
            self.assertEqual(calls[-1][1:3], ["bash", "-lc"])
            self.assertIn("hermes chat -q", calls[-1][3])

    def test_web_backend_starts_direct_openai_codex_oauth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch(
                "grant_agent.web_backend._openai_codex_oauth_status",
                return_value={"authenticated": False},
            ):
                result = backend.dispatch("start_openai_codex_oauth_command", {})

            self.assertEqual(result["status"], "manual_required")
            self.assertEqual(result["method"], "oauth")
            self.assertIn("https://auth.openai.com/oauth/authorize", result["authUrl"])
            self.assertIn("code_challenge=", result["authUrl"])
            self.assertNotIn("codex/device", result["authUrl"])
            self.assertEqual(result["callbackPort"], 1455)
            self.assertIn("/api/codex/login/browser-relay/complete/", result["relayUrl"])
            self.assertIn("--relay-token", result["helperCommand"])

    def test_openai_codex_oauth_completion_uses_only_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            session = OpenAICodexOAuthSession(
                verifier="verifier",
                state="state",
                auth_url="https://auth.openai.com/oauth/authorize",
            )

            with mock.patch.dict(
                "grant_agent.web_backend._OPENAI_CODEX_OAUTH_SESSIONS",
                {"only": session},
                clear=True,
            ):
                with mock.patch(
                    "grant_agent.web_backend._exchange_openai_codex_authorization_code",
                    return_value={"access": "token", "refresh": "refresh", "expires": 1770000000000},
                ) as exchange_mock:
                    with mock.patch(
                        "grant_agent.web_backend._write_openai_codex_auth_profile",
                        return_value={"profileId": "openai-codex:default"},
                    ) as write_profile_mock:
                        with mock.patch(
                            "grant_agent.web_backend._openai_codex_oauth_status",
                            return_value={"authenticated": True},
                        ):
                            result = backend.dispatch(
                                "complete_openai_codex_oauth_command",
                                {"callback": "http://localhost:1455/auth/callback?code=abc&state=state"},
                            )

            self.assertTrue(result["authenticated"])
            exchange_mock.assert_called_once_with("abc", "verifier")
            write_profile_mock.assert_called_once()

    def test_openai_codex_oauth_relay_completes_relative_callback_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            session = OpenAICodexOAuthSession(
                verifier="verifier",
                state="state",
                auth_url="https://auth.openai.com/oauth/authorize",
                relay_token_hash=web_backend._sha256_hex("relay-token"),
            )

            with mock.patch.dict(
                "grant_agent.web_backend._OPENAI_CODEX_OAUTH_SESSIONS",
                {"only": session},
                clear=True,
            ):
                with mock.patch(
                    "grant_agent.web_backend._exchange_openai_codex_authorization_code",
                    return_value={"access": "token", "refresh": "refresh", "expires": 1770000000000},
                ) as exchange_mock:
                    with mock.patch(
                        "grant_agent.web_backend._write_openai_codex_auth_profile",
                        return_value={"profileId": "openai-codex:default"},
                    ):
                        with mock.patch(
                            "grant_agent.web_backend._openai_codex_oauth_status",
                            return_value={"authenticated": True},
                        ):
                            result = backend.complete_openai_codex_oauth_relay(
                                session_id="only",
                                payload={"callbackPath": "/auth/callback?code=abc&state=state"},
                                authorization="Bearer relay-token",
                            )

            self.assertTrue(result["authenticated"])
            exchange_mock.assert_called_once_with("abc", "verifier")

    def test_openai_codex_oauth_session_status_reports_single_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            session = OpenAICodexOAuthSession(
                verifier="verifier",
                state="state",
                auth_url="https://auth.openai.com/oauth/authorize",
            )

            with mock.patch.dict(
                "grant_agent.web_backend._OPENAI_CODEX_OAUTH_SESSIONS",
                {"active": session},
                clear=True,
            ):
                result = backend.dispatch("get_openai_codex_oauth_session_command", {})

            self.assertTrue(result["active"])
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["sessionId"], "active")

    def test_account_config_is_local_and_password_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            self.assertEqual(backend.username, "admin")
            self.assertTrue((root / ".agent_control" / "grand_agent_web_admin.json").exists())
            self.assertTrue((root / ".agent_control" / "grand_agent_admin_password.txt").exists())
            self.assertIsNone(backend.login({"username": "admin", "password": "wrong"}))
            password_text = (root / ".agent_control" / "grand_agent_admin_password.txt").read_text(
                encoding="utf-8"
            )
            password_line = next(line for line in password_text.splitlines() if line.startswith("Password: "))
            token = backend.login(
                {
                    "username": " Admin ",
                    "password": password_line.replace("Password: ", "", 1),
                }
            )
            self.assertIsInstance(token, str)
            self.assertEqual(backend.sessions[str(token)]["role"], "account")

    def test_additional_local_user_can_login(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            _, password, password_path = add_or_reset_admin_user(
                root,
                username="paul",
                display_name="Paul",
            )
            backend = FluxioWebBackend(root, root)

            self.assertTrue(password_path.exists())
            self.assertIsNone(backend.login({"username": "paul", "password": "wrong"}))
            token = backend.login({"username": "paul", "password": password})
            self.assertIsInstance(token, str)
            self.assertEqual(backend.sessions[str(token)]["displayName"], "Paul")

    def test_auth_status_exposes_local_account_hints_without_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)
            add_or_reset_admin_user(root, username="theo", display_name="Theo")
            backend = FluxioWebBackend(root, root)

            class DummyHeaders:
                def get(self, _key: str) -> str:
                    return ""

            class DummyHandler:
                def __init__(self) -> None:
                    self.headers = DummyHeaders()

            status = backend.session_status(DummyHandler())
            self.assertFalse(status["authenticated"])
            self.assertIsNone(status["user"])
            hints = status.get("accountHints")
            self.assertIsInstance(hints, list)
            usernames = [item.get("username") for item in hints if isinstance(item, dict)]
            self.assertIn("admin", usernames)
            self.assertIn("theo", usernames)

    def test_environment_account_aliases_can_login_without_writing_password_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            with mock.patch.dict(
                "os.environ",
                {
                    "SYNTELOS_ACCOUNT_USER": "theo",
                    "SYNTELOS_ACCOUNT_DISPLAY_NAME": "Theo",
                    "SYNTELOS_ACCOUNT_PASSWORD": "local-password",
                },
            ):
                backend = FluxioWebBackend(root, root)

            self.assertFalse((root / ".agent_control" / "grand_agent_admin_password.txt").exists())
            token = backend.login({"username": "theo", "password": "local-password"})
            self.assertIsInstance(token, str)
            self.assertEqual(backend.sessions[str(token)]["displayName"], "Theo")

    def test_public_https_url_is_written_to_password_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            FluxioWebBackend(root, root, public_url="https://syntelos.example.test")

            password_text = (root / ".agent_control" / "grand_agent_admin_password.txt").read_text(
                encoding="utf-8"
            )
            self.assertIn("URL: https://syntelos.example.test", password_text)

    def test_list_workspace_directory_command_returns_directory_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            workspace = root / "workspace"
            docs = workspace / "docs"
            workspace.mkdir()
            docs.mkdir()
            (workspace / "README.md").write_text("# test\n", encoding="utf-8")
            backend = FluxioWebBackend(root, root)

            result = backend.dispatch(
                "list_workspace_directory_command",
                {"path": str(workspace)},
            )

            self.assertEqual(result["currentPath"], str(workspace.resolve()))
            self.assertEqual(result["parentPath"], str(workspace.parent.resolve()))
            names = {(entry["name"], entry["isDirectory"]) for entry in result["entries"]}
            self.assertIn(("docs", True), names)
            self.assertIn(("README.md", False), names)
            self.assertIn(str(root.resolve()), result["roots"])

    def test_run_cli_sets_pythonpath_to_workspace_src(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "src").mkdir(parents=True)

            completed = mock.Mock()
            completed.returncode = 0
            completed.stdout = "{}"
            completed.stderr = ""
            with mock.patch("grant_agent.web_backend.subprocess.run", return_value=completed) as run_mock:
                backend = FluxioWebBackend(root, root)
                backend.dispatch("get_control_room_snapshot_command", {"root": str(root)})

            called_env = run_mock.call_args.kwargs["env"]
            self.assertIn("PYTHONPATH", called_env)
            self.assertTrue(str(root / "src") in called_env["PYTHONPATH"])

    def test_start_control_room_mission_command_uses_async_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.object(backend, "_run_cli", return_value={"ok": True}) as run_cli:
                result = backend.dispatch(
                    "start_control_room_mission_command",
                    {
                        "workspaceId": "workspace_123",
                        "runtime": "hermes",
                        "objective": "Run Golf 40 for 2 days.",
                        "mode": "Autopilot",
                        "budgetHours": 48,
                    },
                )

            self.assertEqual(result, {"ok": True})
            self.assertEqual(run_cli.call_args.args[1], "mission-start")
            command_args = run_cli.call_args.args[2]
            self.assertIn("--launch-async", command_args)
            self.assertEqual(
                run_cli.call_args.kwargs["timeout"],
                MISSION_START_TIMEOUT_SECONDS,
            )

    def test_apply_control_room_mission_action_resume_uses_async_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

            with mock.patch.object(backend, "_run_cli", return_value={"ok": True}) as run_cli:
                result = backend.dispatch(
                    "apply_control_room_mission_action_command",
                    {
                        "missionId": "mission_abc",
                        "action": "resume",
                    },
                )

            self.assertEqual(result, {"ok": True})
            self.assertEqual(run_cli.call_args.args[1], "mission-action")
            command_args = run_cli.call_args.args[2]
            self.assertIn("--launch-async", command_args)
            self.assertEqual(
                run_cli.call_args.kwargs["timeout"],
                MISSION_ACTION_TIMEOUT_SECONDS,
            )

    def test_health_response_includes_security_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            FluxioWebBackend(root, root)

            class DummyHeaders:
                def get(self, key: str) -> str:
                    return ""

            class DummyHandler:
                def __init__(self) -> None:
                    self.headers = DummyHeaders()
                    self.headers_out: dict[str, str] = {}
                    self.wfile = io.BytesIO()

                def send_response(self, _status: int) -> None:
                    return

                def send_header(self, key: str, value: str) -> None:
                    self.headers_out[key] = value

                def end_headers(self) -> None:
                    return

            from grant_agent.web_backend import _json_response

            handler = DummyHandler()
            _json_response(handler, 200, {"ok": True})
            self.assertEqual(handler.headers_out.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(handler.headers_out.get("X-Frame-Options"), "DENY")
            self.assertEqual(handler.headers_out.get("Referrer-Policy"), "no-referrer")
            self.assertEqual(handler.headers_out.get("Cache-Control"), "no-store")


if __name__ == "__main__":
    unittest.main()
