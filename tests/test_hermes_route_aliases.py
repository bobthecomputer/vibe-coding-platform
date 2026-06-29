from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.runtimes.hermes import HermesRuntimeAdapter


class HermesRouteAliasTests(unittest.TestCase):
    def test_opencon_alias_routes_to_openrouter_glm52_without_double_provider_prefix(self) -> None:
        adapter = HermesRuntimeAdapter()
        workspace = mock.Mock(root_path=r"C:\repo")
        mission = mock.Mock(
            mission_id="mission_glm52",
            runtime_id="hermes",
            objective="Prove a real GLM 5.2 route through Hermes.",
            route_configs=[
                {
                    "phase": "execute",
                    "role": "executor",
                    "provider": "opencon",
                    "model": "openrouter/z-ai/glm-5.2",
                    "effort": "high",
                }
            ],
        )
        with mock.patch("grant_agent.runtimes.hermes._runtime_which", return_value="hermes"):
            result = adapter.start_mission(mission, workspace)

        command = str(result["launch_command"])
        self.assertEqual(result["route_contract"]["provider"], "openrouter")
        self.assertEqual(result["route_contract"]["model"], "z-ai/glm-5.2")
        self.assertIn("--provider openrouter", command)
        self.assertIn("--model z-ai/glm-5.2", command)
        self.assertNotIn("--model openrouter/z-ai/glm-5.2", command)

    def test_glm_short_alias_expands_for_openrouter(self) -> None:
        adapter = HermesRuntimeAdapter()

        self.assertEqual(adapter._normalize_model("openrouter", "glm-5.2"), "z-ai/glm-5.2")
        self.assertEqual(adapter._normalize_model("openrouter", "openrouter/z-ai/glm-5.2"), "z-ai/glm-5.2")


if __name__ == "__main__":
    unittest.main()
