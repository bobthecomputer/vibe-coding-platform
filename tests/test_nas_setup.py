from __future__ import annotations

import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "nas_setup.py"
SPEC = importlib.util.spec_from_file_location("nas_setup_module", MODULE_PATH)
assert SPEC and SPEC.loader
nas_setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nas_setup)


class NasSetupTests(unittest.TestCase):
    def test_collect_add_users_supports_repeated_flag(self) -> None:
        users = nas_setup.collect_add_users(["theo", "sam"], "")
        self.assertEqual(users, ["theo", "sam"])

    def test_collect_add_users_supports_comma_list_and_dedupes(self) -> None:
        users = nas_setup.collect_add_users(["theo,sam", "sam"], "alex, theo")
        self.assertEqual(users, ["theo", "sam", "alex"])

    def test_collect_add_users_ignores_empty_fragments(self) -> None:
        users = nas_setup.collect_add_users(["", "  ,  "], "theo,,")
        self.assertEqual(users, ["theo"])


if __name__ == "__main__":
    unittest.main()
