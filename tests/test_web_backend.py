from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.web_backend import FluxioWebBackend


class FluxioWebBackendTests(unittest.TestCase):
    def test_provider_secret_presence_uses_session_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            backend = FluxioWebBackend(root, root)

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

    def test_admin_config_is_local_and_password_is_required(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
