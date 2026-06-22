from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.verify_github_action_runtimes import verify_github_action_runtimes


ROOT = Path(__file__).resolve().parents[1]


class GitHubActionRuntimeGuardTest(unittest.TestCase):
    def test_current_workflows_use_node24_compatible_action_majors(self) -> None:
        report = verify_github_action_runtimes(ROOT)

        self.assertTrue(report["ok"], report["violations"])
        protected_actions = {
            item["action"]
            for item in report["checkedActionRefs"]
            if item["action"] in report["minimumActionMajors"]
        }
        self.assertIn("actions/checkout", protected_actions)
        self.assertIn("actions/setup-python", protected_actions)
        self.assertIn("actions/upload-artifact", protected_actions)
        self.assertIn("actions/upload-pages-artifact", protected_actions)
        self.assertIn("actions/deploy-pages", protected_actions)

    def test_stale_action_majors_fail_with_precise_violations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow_root = root / ".github" / "workflows"
            workflow_root.mkdir(parents=True)
            (workflow_root / "release-proof.yml").write_text(
                "\n".join(
                    [
                        "jobs:",
                        "  release-proof:",
                        "    steps:",
                        "      - uses: actions/checkout@v4",
                        "      - uses: actions/setup-node@v4",
                        "      - uses: actions/setup-python@v5",
                        "      - uses: actions/upload-artifact@v4",
                        "      - uses: actions/upload-pages-artifact@v3",
                        "      - uses: actions/deploy-pages@v4",
                    ]
                ),
                encoding="utf-8",
            )

            report = verify_github_action_runtimes(root)

        self.assertFalse(report["ok"])
        violations_by_action = {item["action"]: item for item in report["violations"]}
        self.assertEqual(violations_by_action["actions/checkout"]["requiredMajor"], 5)
        self.assertEqual(violations_by_action["actions/setup-node"]["requiredMajor"], 5)
        self.assertEqual(violations_by_action["actions/setup-python"]["requiredMajor"], 6)
        self.assertEqual(violations_by_action["actions/upload-artifact"]["requiredMajor"], 6)
        self.assertEqual(violations_by_action["actions/upload-pages-artifact"]["requiredMajor"], 5)
        self.assertEqual(violations_by_action["actions/deploy-pages"]["requiredMajor"], 5)

    def test_cli_writes_machine_readable_proof_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github-action-runtime-guard.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "verify_github_action_runtimes.py"),
                    "--root",
                    str(ROOT),
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema"], "fluxio.github_action_runtime_guard.v1")
        self.assertTrue(payload["ok"])
        self.assertGreater(payload["checkedActionRefCount"], 0)


if __name__ == "__main__":
    unittest.main()
