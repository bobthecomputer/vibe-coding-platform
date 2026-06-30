from __future__ import annotations

import pathlib
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.runtime_worker import _popen_command, _runtime_env
from grant_agent.runtimes import runtime_adapter_map
from grant_agent.runtimes.base import runtime_bin_candidates, runtime_subprocess_env
from grant_agent.runtimes.hermes import HermesRuntimeAdapter
from grant_agent.runtimes.openclaw import OpenClawRuntimeAdapter
from grant_agent.runtimes.opencode import OpenCodeRuntimeAdapter


class RuntimeAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.openclaw_latest_patcher = mock.patch(
            "grant_agent.runtimes.openclaw.latest_openclaw_release",
            return_value={
                "version": "2026.4.14",
                "sourceUrl": "https://www.npmjs.com/package/openclaw",
            },
        )
        self.hermes_latest_patcher = mock.patch(
            "grant_agent.runtimes.hermes.latest_hermes_release",
            return_value={
                "version": "v0.9.0",
                "sourceUrl": "https://github.com/NousResearch/hermes-agent/blob/main/RELEASE_v0.9.0.md",
            },
        )
        self.openclaw_latest_patcher.start()
        self.hermes_latest_patcher.start()

    def tearDown(self) -> None:
        self.hermes_latest_patcher.stop()
        self.openclaw_latest_patcher.stop()
        super().tearDown()

    @mock.patch("grant_agent.runtimes.openclaw.subprocess.run")
    @mock.patch("grant_agent.runtimes.openclaw.shutil.which")
    def test_openclaw_adapter_detects_runtime(
        self, which_mock: mock.Mock, run_mock: mock.Mock
    ) -> None:
        which_mock.return_value = "openclaw"
        run_mock.return_value = mock.Mock(stdout="2026.2.15\n", stderr="")

        adapter = OpenClawRuntimeAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            status = adapter.doctor(pathlib.Path(temp_dir))

        self.assertTrue(status.detected)
        self.assertEqual(status.version, "2026.2.15")
        self.assertEqual(status.latest_version, "2026.4.14")
        self.assertTrue(status.update_available)
        self.assertGreaterEqual(len(status.capabilities), 1)
        self.assertIn("opencode_go_provider", {item.key for item in status.capabilities})

    @mock.patch("grant_agent.runtimes.openclaw.subprocess.run")
    @mock.patch("grant_agent.runtimes.openclaw.read_openclaw_package_version")
    @mock.patch("grant_agent.runtimes.openclaw.shutil.which")
    def test_openclaw_adapter_does_not_report_missing_when_package_version_is_read(
        self,
        which_mock: mock.Mock,
        package_version_mock: mock.Mock,
        run_mock: mock.Mock,
    ) -> None:
        which_mock.return_value = r"C:\Users\paul\AppData\Roaming\npm\openclaw.CMD"
        package_version_mock.return_value = "2026.4.22"

        adapter = OpenClawRuntimeAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            status = adapter.doctor(pathlib.Path(temp_dir))

        self.assertTrue(status.detected)
        self.assertEqual(status.version, "2026.4.22")
        self.assertFalse(any("not found on PATH" in issue for issue in status.issues))
        run_mock.assert_not_called()

    @mock.patch("grant_agent.runtimes.hermes.shutil.which")
    def test_hermes_adapter_reports_missing_runtime(self, which_mock: mock.Mock) -> None:
        which_mock.return_value = None

        adapter = HermesRuntimeAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            status = adapter.doctor(pathlib.Path(temp_dir))

        self.assertFalse(status.detected)
        self.assertIn("Install Hermes", status.doctor_summary)
        self.assertIn("code_mod_skills", {item.key for item in status.capabilities})

    def test_runtime_env_loads_bundled_home_and_provider_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            runtime_home = root / "runtime" / "home"
            (root / "runtime" / "bin").mkdir(parents=True)
            (runtime_home / ".hermes").mkdir(parents=True)
            (runtime_home / ".fluxio_provider_env").write_text(
                "HERMES_HOME=/custom/hermes\nFLUXIO_TEST_PROVIDER=ready\n",
                encoding="utf-8",
            )
            session_path = root / ".agent_control" / "runtime_sessions" / "delegate.json"
            session_path.parent.mkdir(parents=True)
            session_path.write_text(json.dumps({}), encoding="utf-8")

            with mock.patch.dict("os.environ", {"HOME": str(root / "missing-home")}, clear=False):
                env = runtime_subprocess_env(root)
                worker_env = _runtime_env(session_path, root)

            self.assertEqual(env["HOME"], str(runtime_home))
            self.assertEqual(env["HERMES_HOME"], "/custom/hermes")
            self.assertEqual(env["FLUXIO_TEST_PROVIDER"], "ready")
            self.assertEqual(worker_env["HOME"], str(runtime_home))
            self.assertEqual(worker_env["HERMES_HOME"], "/custom/hermes")
            self.assertEqual(worker_env["FLUXIO_TEST_PROVIDER"], "ready")

    @unittest.skipUnless(os.name == "nt", "Windows command parsing is platform-specific")
    def test_runtime_worker_preserves_windows_paths_and_quoted_prompt(self) -> None:
        command = (
            r"C:\Users\paul\AppData\Local\Programs\Python\Python313\python.exe "
            r"-m grant_agent.opencode_bridge "
            r"--opencode-command C:\Users\paul\AppData\Roaming\npm\opencode.CMD "
            r'--prompt "hello world"'
        )

        args = _popen_command(command)

        self.assertEqual(
            args[0],
            r"C:\Users\paul\AppData\Local\Programs\Python\Python313\python.exe",
        )
        self.assertEqual(
            args[4],
            r"C:\Users\paul\AppData\Roaming\npm\opencode.CMD",
        )
        self.assertEqual(args[-1], "hello world")

    def test_runtime_bin_candidates_include_sibling_syntelos_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            projects = pathlib.Path(temp_dir) / "volume1" / "Saclay" / "projects"
            workspace = projects / "solantir-mindtower-fusion"
            shared_runtime_bin = projects / "syntelos" / "runtime" / "bin"
            workspace.mkdir(parents=True)
            shared_runtime_bin.mkdir(parents=True)

            candidates = runtime_bin_candidates(workspace)

            self.assertIn(shared_runtime_bin, candidates)

    @mock.patch("grant_agent.runtimes.hermes.subprocess.run")
    @mock.patch("grant_agent.runtimes.hermes.shutil.which")
    @mock.patch("grant_agent.runtimes.hermes.os.name", "nt")
    def test_hermes_adapter_detects_runtime_inside_wsl(
        self,
        which_mock: mock.Mock,
        run_mock: mock.Mock,
    ) -> None:
        def _which(name: str) -> str | None:
            if name == "wsl":
                return "C:/Windows/System32/wsl.exe"
            return None

        which_mock.side_effect = _which
        run_mock.return_value = mock.Mock(
            returncode=0,
            stdout="Hermes Agent v0.4.0\n",
            stderr="",
        )

        adapter = HermesRuntimeAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            status = adapter.doctor(pathlib.Path(temp_dir))

        self.assertTrue(status.detected)
        self.assertEqual(status.command, "wsl:hermes")
        self.assertTrue(status.update_available)
        self.assertIn("latest upstream release", status.doctor_summary)

    @mock.patch("grant_agent.runtimes.hermes.subprocess.run")
    @mock.patch("grant_agent.runtimes.hermes.shutil.which")
    def test_hermes_adapter_prefers_release_version_over_stale_commit_warning(
        self,
        which_mock: mock.Mock,
        run_mock: mock.Mock,
    ) -> None:
        which_mock.return_value = "hermes"
        run_mock.return_value = mock.Mock(
            stdout="Hermes Agent v0.9.0 (2026.4.13)\nUpdate available: 1563 commits behind\n",
            stderr="",
        )

        adapter = HermesRuntimeAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            status = adapter.doctor(pathlib.Path(temp_dir))

        self.assertEqual(status.version, "v0.9.0")
        self.assertFalse(status.update_available)

    def test_openclaw_launch_uses_session_id_and_json_output(self) -> None:
        adapter = OpenClawRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_abcd1234",
            objective='Fix "quote" handling',
            route_configs=[
                {
                    "role": "executor",
                    "provider": "openai",
                    "model": "gpt-5.4-mini",
                    "effort": "medium",
                }
            ],
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        launch = adapter.start_mission(mission, workspace)

        command = str(launch["launch_command"])
        self.assertIn("openclaw", command.lower())
        self.assertIn("agents add", command)
        self.assertIn("--agent fluxio_mission_abcd1234_", command)
        self.assertIn("--model openai-codex/gpt-5.4-mini", command)
        self.assertIn("--session-id fluxio_mission_abcd1234", command)
        self.assertIn("--thinking medium", command)
        self.assertIn("--json", command)
        self.assertIn("Fix", command)
        self.assertIn("quote", command)
        self.assertIn("handling", command)
        self.assertEqual(
            launch["route_contract"]["canonical_model_id"],
            "openai-codex/gpt-5.4-mini",
        )

    def test_openclaw_launch_can_use_local_agent_mode_for_web_backend_env_auth(self) -> None:
        adapter = OpenClawRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_local1234",
            objective="Use web backend provider env for OpenClaw",
            route_configs=[
                {
                    "role": "executor",
                    "provider": "openai",
                    "model": "gpt-5.4-mini",
                    "effort": "low",
                }
            ],
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        with mock.patch.dict("os.environ", {"SYNTELOS_OPENCLAW_AGENT_MODE": "local"}):
            launch = adapter.start_mission(mission, workspace)

        self.assertIn("--local", str(launch["launch_command"]))

    def test_openclaw_launch_supports_opencodego_route(self) -> None:
        adapter = OpenClawRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_opencodego",
            objective="Use OpenCodeGo for this mission",
            route_configs=[
                {
                    "role": "executor",
                    "provider": "opencodego",
                    "model": "opencode-go/kimi-k2.5",
                    "effort": "high",
                }
            ],
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        launch = adapter.start_mission(mission, workspace)

        self.assertEqual(launch["route_contract"]["provider"], "opencode-go")
        self.assertEqual(
            launch["route_contract"]["canonical_model_id"],
            "opencode-go/kimi-k2.5",
        )
        self.assertIn("--model opencode-go/kimi-k2.5", str(launch["launch_command"]))

    def test_openclaw_launch_supports_opencon_glm52_route(self) -> None:
        adapter = OpenClawRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_opencon_glm52",
            objective="Run GLM 5.2 through the OpenCon/OpenRouter route.",
            route_configs=[
                {
                    "role": "executor",
                    "provider": "opencon-pro",
                    "model": "glm-5.2",
                    "effort": "high",
                }
            ],
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        launch = adapter.start_mission(mission, workspace)

        self.assertEqual(launch["route_contract"]["provider"], "openrouter")
        self.assertEqual(launch["route_contract"]["model"], "z-ai/glm-5.2")
        self.assertEqual(
            launch["route_contract"]["canonical_model_id"],
            "openrouter/z-ai/glm-5.2",
        )
        self.assertIn("--model openrouter/z-ai/glm-5.2", str(launch["launch_command"]))

    @mock.patch("grant_agent.runtimes.opencode.subprocess.run")
    @mock.patch("grant_agent.runtimes.opencode.runtime_which")
    def test_opencode_adapter_detects_runtime(
        self, which_mock: mock.Mock, run_mock: mock.Mock
    ) -> None:
        which_mock.return_value = "opencode"
        run_mock.return_value = mock.Mock(stdout="1.15.13\n", stderr="")

        adapter = OpenCodeRuntimeAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            status = adapter.doctor(pathlib.Path(temp_dir))

        self.assertTrue(status.detected)
        self.assertEqual(status.version, "1.15.13")
        self.assertIn("native_opencode_run", {item.key for item in status.capabilities})

    @mock.patch("grant_agent.runtimes.opencode.runtime_which", return_value="opencode")
    def test_opencode_launch_supports_openrouter_deepseek_route(
        self, which_mock: mock.Mock
    ) -> None:
        adapter = OpenCodeRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_opencode_deepseek",
            title="OpenCode DeepSeek visibility",
            objective="Make the real OpenCode reply show in Agent Live.",
            route_configs=[
                {
                    "role": "executor",
                    "provider": "openrouter",
                    "model": "openrouter/deepseek/deepseek-v4-flash",
                    "effort": "high",
                }
            ],
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        launch = adapter.start_mission(mission, workspace)

        command = str(launch["launch_command"])
        self.assertEqual(launch["runtime_id"], "opencode")
        self.assertEqual(launch["route_contract"]["provider"], "openrouter")
        self.assertEqual(
            launch["route_contract"]["canonical_model_id"],
            "openrouter/deepseek/deepseek-v4-flash",
        )
        self.assertIn("grant_agent.opencode_bridge", command)
        self.assertIn("--opencode-command opencode", command)
        self.assertIn("--model openrouter/deepseek/deepseek-v4-flash", command)
        self.assertIn("--variant high", command)
        self.assertIn("Make the real OpenCode reply show in Agent Live", command)

    @mock.patch("grant_agent.runtimes.opencode.runtime_which", return_value="opencode")
    def test_opencode_launch_strips_opencodego_model_prefix(
        self, which_mock: mock.Mock
    ) -> None:
        adapter = OpenCodeRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_opencodego",
            title="OpenCodeGo visibility",
            objective="Make the OpenCodeGo reply show in Agent Live.",
            route_configs=[
                {
                    "role": "executor",
                    "provider": "opencode-go",
                    "model": "opencode-go/glm-5.2",
                    "effort": "low",
                }
            ],
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        launch = adapter.start_mission(mission, workspace)

        command = str(launch["launch_command"])
        self.assertEqual(launch["route_contract"]["provider"], "opencode-go")
        self.assertEqual(launch["route_contract"]["model"], "opencode-go/glm-5.2")
        self.assertEqual(launch["route_contract"]["canonical_model_id"], "openrouter/z-ai/glm-5.2")
        self.assertIn("--model openrouter/z-ai/glm-5.2", command)
        self.assertNotIn("--model opencode-go/glm-5.2", command)

    def test_runtime_adapter_map_includes_native_opencode(self) -> None:
        self.assertIn("opencode", runtime_adapter_map())

    def test_hermes_launch_supports_opencodego_route(self) -> None:
        adapter = HermesRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_opencodego",
            objective="Use OpenCodeGo through Hermes",
            route_configs=[
                {
                    "role": "executor",
                    "provider": "opencode-go",
                    "model": "opencode-go/glm-5.2",
                    "effort": "high",
                }
            ],
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        with mock.patch("grant_agent.runtimes.hermes.shutil.which", return_value="hermes"):
            launch = adapter.start_mission(mission, workspace)

        self.assertEqual(launch["route_contract"]["provider"], "opencode-go")
        self.assertIn("--provider opencode-go", str(launch["launch_command"]))
        self.assertIn("--model openrouter/z-ai/glm-5.2", str(launch["launch_command"]))
        self.assertNotIn("--model opencode-go/glm-5.2", str(launch["launch_command"]))

    def test_hermes_launch_uses_wsl_bash_lc_when_hermes_only_in_wsl(self) -> None:
        adapter = HermesRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_abcd1234",
            objective="Run from WSL",
            route_configs=[
                {
                    "role": "executor",
                    "provider": "openai",
                    "model": "gpt-5.4",
                    "effort": "high",
                }
            ],
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        with mock.patch("grant_agent.runtimes.hermes.shutil.which", return_value=None):
            with mock.patch.object(adapter, "_wsl_hermes_available", return_value=True):
                launch = adapter.start_mission(mission, workspace)

        command = str(launch["launch_command"])
        self.assertTrue(command.startswith("wsl bash -lc "))
        self.assertIn("hermes chat", command)
        self.assertIn("--provider openai-codex", command)
        self.assertIn("--model gpt-5.4", command)
        self.assertEqual(launch["route_contract"]["provider"], "openai-codex")

    def test_openclaw_launch_uses_planner_route_during_plan_phase(self) -> None:
        adapter = OpenClawRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_plan1234",
            objective="Plan the migration",
            route_configs=[
                {
                    "role": "planner",
                    "provider": "openai",
                    "model": "gpt-5.4",
                    "effort": "high",
                },
                {
                    "role": "executor",
                    "provider": "openai",
                    "model": "gpt-5.4-mini",
                    "effort": "medium",
                },
            ],
            state=SimpleNamespace(current_cycle_phase="plan", status="running"),
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        launch = adapter.start_mission(mission, workspace)

        self.assertEqual(launch["route_contract"]["role"], "planner")
        self.assertEqual(launch["route_contract"]["phase"], "plan")
        self.assertEqual(
            launch["route_contract"]["canonical_model_id"],
            "openai-codex/gpt-5.4",
        )

    def test_hermes_launch_uses_verifier_route_during_verify_phase(self) -> None:
        adapter = HermesRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_verify1234",
            objective="Verify the patch",
            route_configs=[
                {
                    "role": "planner",
                    "provider": "openai",
                    "model": "gpt-5.4",
                    "effort": "high",
                },
                {
                    "role": "executor",
                    "provider": "openai",
                    "model": "gpt-5.4-mini",
                    "effort": "medium",
                },
                {
                    "role": "verifier",
                    "provider": "openai",
                    "model": "gpt-5.4",
                    "effort": "high",
                },
            ],
            state=SimpleNamespace(current_cycle_phase="verify", status="running"),
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        with mock.patch("grant_agent.runtimes.hermes.shutil.which", return_value="hermes"):
            launch = adapter.start_mission(mission, workspace)

        self.assertEqual(launch["route_contract"]["role"], "verifier")
        self.assertEqual(launch["route_contract"]["phase"], "verify")
        self.assertIn("--model gpt-5.4", str(launch["launch_command"]))

    def test_hermes_launch_normalizes_minimax_model_for_cli(self) -> None:
        adapter = HermesRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_minimax1234",
            objective="Build the visual surface",
            route_configs=[
                {
                    "role": "executor",
                    "provider": "minimax",
                    "model": "MiniMax-M3",
                    "effort": "high",
                }
            ],
            state=SimpleNamespace(current_cycle_phase="execute", status="running"),
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        with mock.patch("grant_agent.runtimes.hermes.shutil.which", return_value="hermes"):
            launch = adapter.start_mission(mission, workspace)

        self.assertEqual(launch["route_contract"]["provider"], "minimax")
        self.assertEqual(launch["route_contract"]["model"], "MiniMax-M3")
        self.assertIn("--model MiniMax-M3", str(launch["launch_command"]))

    def test_hermes_resume_carries_operator_artifact_repair_gate(self) -> None:
        adapter = HermesRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_repair1234",
            title="Repair live mission proof",
            objective="Build a polished phone/tablet Builder progress surface",
            route_configs=[
                {
                    "role": "verifier",
                    "provider": "openai",
                    "model": "gpt-5.5",
                    "effort": "high",
                }
            ],
            state=SimpleNamespace(
                current_cycle_phase="verify",
                status="running",
                stop_reason="",
                last_error="",
                code_execution={},
            ),
            proof=SimpleNamespace(
                summary="Artifact gate passed but transcript is missing_runtime_output.",
                blocked_by=["runtime transcript missing_runtime_output"],
                failed_checks=[],
                artifacts=[],
            ),
            code_execution=SimpleNamespace(artifacts=[]),
            delegated_runtime_sessions=[
                SimpleNamespace(
                    latest_events=[
                        {
                            "kind": "operator.followup",
                            "message": (
                                "Required repair evidence: create or update a file under "
                                ".agent_control/mission_artifacts for this mission."
                            ),
                        }
                    ]
                )
            ],
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        with mock.patch("grant_agent.runtimes.hermes.shutil.which", return_value="hermes"):
            launch = adapter.resume_mission(mission, workspace)

        command = str(launch["launch_command"])
        self.assertIn("Required repair evidence", command)
        self.assertIn(".agent_control/mission_artifacts", command)
        self.assertIn("Hard artifact/runtime-output gate", command)
        self.assertIn("Do not mark the mission completed", command)
        self.assertEqual(launch["route_contract"]["role"], "verifier")

    def test_openclaw_resume_carries_same_artifact_repair_context(self) -> None:
        adapter = OpenClawRuntimeAdapter()
        mission = mock.Mock(
            mission_id="mission_openclaw_repair",
            title="Repair fallback proof",
            objective="Repair a mission artifact",
            route_configs=[
                {
                    "role": "executor",
                    "provider": "openai",
                    "model": "gpt-5.5",
                    "effort": "high",
                }
            ],
            state=SimpleNamespace(
                current_cycle_phase="execute",
                status="running",
                stop_reason="",
                last_error="",
                code_execution={},
            ),
            proof=SimpleNamespace(
                summary="Needs hard artifact repair.",
                blocked_by=[],
                failed_checks=["missing served artifact"],
                artifacts=[],
            ),
            code_execution=SimpleNamespace(artifacts=[]),
            delegated_runtime_sessions=[
                SimpleNamespace(
                    latest_events=[
                        {
                            "kind": "operator.followup",
                            "message": "Attach a verifier receipt from Workbench.",
                        }
                    ]
                )
            ],
        )
        workspace = mock.Mock(root_path=r"C:\repo")

        launch = adapter.resume_mission(mission, workspace)

        command = str(launch["launch_command"])
        self.assertIn("Attach a verifier receipt from Workbench", command)
        self.assertIn("Hard artifact/runtime-output gate", command)
        self.assertIn("--message", command)

    @mock.patch("grant_agent.runtimes.hermes.shutil.which", return_value="hermes")
    def test_hermes_update_prefers_native_command_when_available(
        self, which_mock: mock.Mock
    ) -> None:
        adapter = HermesRuntimeAdapter()
        with tempfile.TemporaryDirectory() as temp_dir:
            update = adapter.update(pathlib.Path(temp_dir))

        self.assertEqual(update["command"], "hermes update")


if __name__ == "__main__":
    unittest.main()
