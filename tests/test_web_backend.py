from __future__ import annotations

import pathlib
import io
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.web_backend import FluxioWebBackend, add_or_reset_admin_user


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
                    "username": "admin",
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
