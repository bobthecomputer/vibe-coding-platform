from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.onboarding import _command_version, detect_onboarding_status


class OnboardingTests(unittest.TestCase):
    @mock.patch("grant_agent.onboarding.subprocess.run")
    @mock.patch("grant_agent.onboarding.shutil.which")
    @mock.patch("grant_agent.onboarding.os.name", "nt")
    def test_command_version_uses_wsl_fallback_for_hermes(
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

        status = _command_version("hermes")

        self.assertTrue(status["installed"])
        self.assertEqual(status["command"], "wsl:hermes")
        self.assertIn("WSL2", status["details"])
        self.assertEqual(status["version"], "Hermes Agent v0.4.0")

    @mock.patch("grant_agent.onboarding.detect_wsl_status")
    @mock.patch("grant_agent.onboarding._command_version")
    def test_detect_onboarding_status_collects_checks(
        self,
        command_version: mock.Mock,
        detect_wsl_status: mock.Mock,
    ) -> None:
        detect_wsl_status.return_value = {
            "required": True,
            "installed": True,
            "default_version": 2,
            "details": "WSL2 ready",
        }
        command_version.side_effect = [
            {"installed": True, "command": "node", "version": "v22", "details": "ok"},
            {"installed": True, "command": "python", "version": "3.13", "details": "ok"},
            {"installed": True, "command": "uv", "version": "0.9", "details": "ok"},
            {"installed": True, "command": "openclaw", "version": "2026.2.15", "details": "ok"},
            {"installed": False, "command": None, "version": None, "details": "missing"},
            {"installed": True, "command": "node", "version": "v22", "details": "ok"},
            {"installed": True, "command": "python", "version": "3.13", "details": "ok"},
            {"installed": True, "command": "uv", "version": "0.9", "details": "ok"},
            {"installed": True, "command": "openclaw", "version": "2026.2.15", "details": "ok"},
            {"installed": False, "command": None, "version": None, "details": "missing"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "profiles.json").write_text(
                """
                {
                  "default_profile": "builder",
                  "profiles": {
                    "beginner": {"description": "Beginner", "ui": {"motion": "reduced"}, "agent": {"execution_scope": "isolated", "approval_mode": "strict", "explanation_depth": "high", "delegation_aggressiveness": "low"}},
                    "builder": {"description": "Builder", "ui": {"motion": "standard"}, "agent": {"execution_scope": "isolated", "approval_mode": "tiered", "explanation_depth": "medium", "delegation_aggressiveness": "balanced"}}
                  }
                }
                """,
                encoding="utf-8",
            )
            status = detect_onboarding_status(root)

        self.assertEqual(status["checks"]["node"]["version"], "v22")
        self.assertFalse(status["checks"]["hermes"]["installed"])
        self.assertIn("Install Hermes", status["nextActions"][0])
        self.assertIn("tutorial", status)
        self.assertIn("profileChoices", status)
        self.assertIn("setupHealth", status)
        self.assertIn("repairActions", status["setupHealth"])
        self.assertIn("globalActions", status["setupHealth"])
        self.assertEqual(status["setupHealth"]["globalActions"][0]["actionId"], "verify_setup_health")
        self.assertIn("Hermes", status["setupHealth"]["missingDependencies"])
        self.assertEqual(status["setupHealth"]["installState"], "install_available")
        self.assertFalse(status["setupHealth"]["installerReady"])
        hermes = next(
            item
            for item in status["setupHealth"]["dependencies"]
            if item["dependencyId"] == "hermes"
        )
        self.assertEqual(hermes["stage"], "install_available")
        self.assertEqual(hermes["serviceCategory"], "runtime")
        self.assertEqual(hermes["installSource"], "wsl_script")
        self.assertEqual(hermes["currentHealthStatus"], "install_available")
        self.assertEqual(hermes["lastVerificationResult"], "blocked")
        self.assertEqual(hermes["managementMode"], "fluxio_managed")
        runtime_stack = next(
            item
            for item in status["setupHealth"]["repairActions"]
            if item["actionId"] == "install_runtime_stack"
        )
        self.assertTrue(runtime_stack["autoRunVerify"])
        self.assertEqual(len(runtime_stack["batchCommands"]), 1)
        self.assertEqual(runtime_stack["batchCommands"][0]["dependencyId"], "hermes")
        self.assertIn("serviceManagement", status["setupHealth"])
        self.assertIn("serviceManagementSummary", status["setupHealth"])
        minimax_auth = next(
            item
            for item in status["setupHealth"]["dependencies"]
            if item["dependencyId"] == "minimax_auth"
        )
        minimax_action_ids = {
            action["actionId"] for action in minimax_auth["repairActions"]
        }
        self.assertIn("minimax-global-oauth", minimax_action_ids)
        self.assertIn("minimax-cn-oauth", minimax_action_ids)
        self.assertIn("minimax-global-api", minimax_action_ids)
        self.assertIn("minimax-cn-api", minimax_action_ids)
        telegram = next(
            item
            for item in status["setupHealth"]["dependencies"]
            if item["dependencyId"] == "telegram_ready"
        )
        self.assertEqual(telegram["stage"], "install_available")
        telegram_action_ids = {
            action["actionId"] for action in telegram["repairActions"]
        }
        self.assertIn("configure_telegram_destination", telegram_action_ids)
        self.assertEqual(status["tutorial"]["steps"][0]["status"], "pending")

    @mock.patch("grant_agent.onboarding.detect_wsl_status")
    @mock.patch("grant_agent.onboarding._command_version")
    def test_runtime_stack_action_includes_node_and_uv_when_missing(
        self,
        command_version: mock.Mock,
        detect_wsl_status: mock.Mock,
    ) -> None:
        detect_wsl_status.return_value = {
            "required": True,
            "installed": True,
            "default_version": 2,
            "details": "WSL2 ready",
        }
        command_version.side_effect = [
            {"installed": False, "command": None, "version": None, "details": "node missing"},
            {"installed": True, "command": "python", "version": "3.13", "details": "ok"},
            {"installed": False, "command": None, "version": None, "details": "uv missing"},
            {"installed": False, "command": None, "version": None, "details": "openclaw missing"},
            {"installed": False, "command": None, "version": None, "details": "hermes missing"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "profiles.json").write_text(
                """
                {
                  "default_profile": "builder",
                  "profiles": {
                    "builder": {"description": "Builder", "ui": {"motion": "standard"}, "agent": {"execution_scope": "isolated", "approval_mode": "tiered", "explanation_depth": "medium", "delegation_aggressiveness": "balanced"}}
                  }
                }
                """,
                encoding="utf-8",
            )
            status = detect_onboarding_status(root)

        runtime_stack = next(
            item
            for item in status["setupHealth"]["repairActions"]
            if item["actionId"] == "install_runtime_stack"
        )
        batch_dependency_ids = [
            item.get("dependencyId", "")
            for item in runtime_stack["batchCommands"]
        ]
        self.assertIn("node", batch_dependency_ids)
        self.assertIn("uv", batch_dependency_ids)
        self.assertIn("openclaw", batch_dependency_ids)
        self.assertIn("hermes", batch_dependency_ids)

    @mock.patch("grant_agent.onboarding.detect_wsl_status")
    @mock.patch("grant_agent.onboarding._command_version")
    def test_setup_history_surfaces_verify_pending_stage(
        self,
        command_version: mock.Mock,
        detect_wsl_status: mock.Mock,
    ) -> None:
        detect_wsl_status.return_value = {
            "required": True,
            "installed": True,
            "default_version": 2,
            "details": "WSL2 ready",
        }
        command_version.side_effect = [
            {"installed": True, "command": "node", "version": "v22", "details": "ok"},
            {"installed": True, "command": "python", "version": "3.13", "details": "ok"},
            {"installed": True, "command": "uv", "version": "0.9", "details": "ok"},
            {"installed": True, "command": "openclaw", "version": "2026.2.15", "details": "ok"},
            {"installed": True, "command": "hermes", "version": "0.4.0", "details": "ok"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            control_dir = root / ".agent_control"
            control_dir.mkdir()
            (control_dir / "workspace_actions.json").write_text(
                """
                {
                  "__setup__": [
                    {
                      "action_id": "setup_uv_install",
                      "executed_at": "2026-04-06T12:00:00+00:00",
                      "proposal": {
                        "title": "Install uv",
                        "args": {
                          "workspaceActionId": "install_uv",
                          "surface": "setup",
                          "commandSurface": "setup.install",
                          "dependencyId": "uv"
                        }
                      },
                      "gate": {"status": "approved"},
                      "result": {"ok": true, "payload": {"dependencyId": "uv"}}
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "profiles.json").write_text(
                """
                {
                  "default_profile": "builder",
                  "profiles": {
                    "builder": {"description": "Builder", "ui": {"motion": "standard"}, "agent": {"execution_scope": "isolated", "approval_mode": "tiered", "explanation_depth": "medium", "delegation_aggressiveness": "balanced"}}
                  }
                }
                """,
                encoding="utf-8",
            )
            status = detect_onboarding_status(root)

        uv_dependency = next(
            item for item in status["setupHealth"]["dependencies"] if item["dependencyId"] == "uv"
        )
        self.assertEqual(uv_dependency["stage"], "verify_pending")
        self.assertEqual(uv_dependency["lastVerificationResult"], "pending")
        self.assertEqual(uv_dependency["managementMode"], "fluxio_managed")
        self.assertEqual(
            status["setupHealth"]["actionHistoryByDependency"]["uv"][-1]["proposal"]["args"]["workspaceActionId"],
            "install_uv",
        )

    @mock.patch("grant_agent.onboarding.detect_wsl_status")
    @mock.patch("grant_agent.onboarding._command_version")
    def test_tutorial_completes_after_workspace_mission_and_phone_destination_exist(
        self,
        command_version: mock.Mock,
        detect_wsl_status: mock.Mock,
    ) -> None:
        detect_wsl_status.return_value = {
            "required": True,
            "installed": True,
            "default_version": 2,
            "details": "WSL2 ready",
        }
        command_version.side_effect = [
            {"installed": True, "command": "node", "version": "v22", "details": "ok"},
            {"installed": True, "command": "python", "version": "3.13", "details": "ok"},
            {"installed": True, "command": "uv", "version": "0.9", "details": "ok"},
            {"installed": True, "command": "openclaw", "version": "2026.2.15", "details": "ok"},
            {"installed": True, "command": "hermes", "version": "0.4.0", "details": "ok"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            control_dir = root / ".agent_control"
            control_dir.mkdir()
            (control_dir / "workspaces.json").write_text(
                """
                [
                  {
                    "workspace_id": "workspace_demo",
                    "name": "Fluxio Workspace",
                    "root_path": ".",
                    "default_runtime": "hermes",
                    "user_profile": "builder"
                  }
                ]
                """,
                encoding="utf-8",
            )
            (control_dir / "missions.json").write_text(
                """
                [
                  {
                    "mission_id": "mission_demo",
                    "title": "Run the first proving mission",
                    "state": {
                      "status": "completed",
                      "latest_session_id": "session_demo"
                    },
                    "escalation_policy": {
                      "destination": "@fluxio"
                    }
                  }
                ]
                """,
                encoding="utf-8",
            )
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "profiles.json").write_text(
                """
                {
                  "default_profile": "builder",
                  "profiles": {
                    "builder": {"description": "Builder", "ui": {"motion": "standard"}, "agent": {"execution_scope": "isolated", "approval_mode": "tiered", "explanation_depth": "medium", "delegation_aggressiveness": "balanced"}}
                  }
                }
                """,
                encoding="utf-8",
            )
            status = detect_onboarding_status(root)

        self.assertTrue(status["setupHealth"]["environmentReady"])
        self.assertTrue(status["setupHealth"]["firstMissionLaunched"])
        self.assertTrue(status["setupHealth"]["telegramReady"])
        self.assertTrue(status["tutorial"]["isComplete"])
        self.assertEqual(status["tutorial"]["currentStepId"], "")
        self.assertEqual(
            status["tutorial"]["completedSteps"],
            [
                "detect_environment",
                "choose_profile",
                "add_workspace",
                "launch_mission",
                "enable_phone",
            ],
        )
        self.assertEqual(status["nextActions"], ["Setup is complete. Launch or resume a mission."])

    @mock.patch("grant_agent.onboarding.detect_wsl_status")
    @mock.patch("grant_agent.onboarding._command_version")
    def test_healthy_dependency_stays_passed_when_global_verify_has_other_blockers(
        self,
        command_version: mock.Mock,
        detect_wsl_status: mock.Mock,
    ) -> None:
        detect_wsl_status.return_value = {
            "required": True,
            "installed": True,
            "default_version": 2,
            "details": "WSL2 ready",
        }
        command_version.side_effect = [
            {"installed": True, "command": "node", "version": "v22", "details": "ok"},
            {"installed": True, "command": "python", "version": "3.13", "details": "ok"},
            {"installed": True, "command": "uv", "version": "0.9", "details": "ok"},
            {"installed": True, "command": "openclaw", "version": "2026.2.15", "details": "ok"},
            {"installed": True, "command": "hermes", "version": "0.4.0", "details": "ok"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            control_dir = root / ".agent_control"
            control_dir.mkdir()
            (control_dir / "workspace_actions.json").write_text(
                """
                {
                  "__setup__": [
                    {
                      "action_id": "setup_verify",
                      "executed_at": "2026-04-08T09:00:00+00:00",
                      "proposal": {
                        "title": "Verify setup health",
                        "args": {
                          "workspaceActionId": "verify_setup_health",
                          "surface": "setup",
                          "commandSurface": "setup.verify"
                        }
                      },
                      "gate": {"status": "completed"},
                      "result": {"ok": false, "payload": {"setupHealth": {"missingDependencies": ["First guided mission"]}}}
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "profiles.json").write_text(
                """
                {
                  "default_profile": "builder",
                  "profiles": {
                    "builder": {"description": "Builder", "ui": {"motion": "standard"}, "agent": {"execution_scope": "isolated", "approval_mode": "tiered", "explanation_depth": "medium", "delegation_aggressiveness": "balanced"}}
                  }
                }
                """,
                encoding="utf-8",
            )
            status = detect_onboarding_status(root)

        hermes_dependency = next(
            item for item in status["setupHealth"]["dependencies"] if item["dependencyId"] == "hermes"
        )
        self.assertEqual(hermes_dependency["stage"], "healthy")
        self.assertEqual(hermes_dependency["lastVerificationResult"], "passed")


if __name__ == "__main__":
    unittest.main()
