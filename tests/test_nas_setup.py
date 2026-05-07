from __future__ import annotations

import importlib.util
import pathlib
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "nas_setup.py"
SPEC = importlib.util.spec_from_file_location("nas_setup_module", MODULE_PATH)
assert SPEC and SPEC.loader
nas_setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nas_setup)

HTTPS_MODULE_PATH = ROOT / "scripts" / "setup_nas_https.py"
HTTPS_SPEC = importlib.util.spec_from_file_location("setup_nas_https_module", HTTPS_MODULE_PATH)
assert HTTPS_SPEC and HTTPS_SPEC.loader
setup_nas_https = importlib.util.module_from_spec(HTTPS_SPEC)
HTTPS_SPEC.loader.exec_module(setup_nas_https)

RUNTIME_MODULE_PATH = ROOT / "scripts" / "nas_runtime_doctor.py"
RUNTIME_SPEC = importlib.util.spec_from_file_location("nas_runtime_doctor_module", RUNTIME_MODULE_PATH)
assert RUNTIME_SPEC and RUNTIME_SPEC.loader
nas_runtime_doctor = importlib.util.module_from_spec(RUNTIME_SPEC)
RUNTIME_SPEC.loader.exec_module(nas_runtime_doctor)

INSTALL_RUNTIME_MODULE_PATH = ROOT / "scripts" / "install_nas_runtime_stack.py"
INSTALL_RUNTIME_SPEC = importlib.util.spec_from_file_location(
    "install_nas_runtime_stack_module",
    INSTALL_RUNTIME_MODULE_PATH,
)
assert INSTALL_RUNTIME_SPEC and INSTALL_RUNTIME_SPEC.loader
install_nas_runtime_stack = importlib.util.module_from_spec(INSTALL_RUNTIME_SPEC)
INSTALL_RUNTIME_SPEC.loader.exec_module(install_nas_runtime_stack)


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

    def test_https_setup_splits_dns_and_ip_hosts(self) -> None:
        dns_names, ip_addresses = setup_nas_https.split_hosts(
            [
                "sysnology.tail602108.ts.net",
                "100.125.54.118",
                "sysnology.tail602108.ts.net.",
            ]
        )

        self.assertEqual(dns_names, ["sysnology.tail602108.ts.net"])
        self.assertEqual(ip_addresses, ["100.125.54.118"])

    def test_https_setup_backend_command_includes_tls_files(self) -> None:
        command = setup_nas_https.backend_start_command(
            "https://sysnology.tail602108.ts.net:47880",
            pathlib.Path("/certs/server.crt"),
            pathlib.Path("/certs/server.key"),
            47880,
        )

        self.assertIn("--public-url https://sysnology.tail602108.ts.net:47880", command)
        self.assertIn("--tls-cert-file", command)
        self.assertIn("--tls-key-file", command)

    def test_runtime_doctor_uses_packaged_bin_dirs(self) -> None:
        runtime_bin = ROOT / ".agent_control" / "runtime" / "bin"
        with mock.patch.object(nas_runtime_doctor.Path, "exists", return_value=True):
            entries = nas_runtime_doctor.runtime_path_entries([])

        self.assertIn(str(runtime_bin.resolve()), entries)

    def test_runtime_installer_maps_linux_arch_and_node_url(self) -> None:
        self.assertEqual(install_nas_runtime_stack.node_platform_arch("x86_64"), "x64")
        self.assertEqual(install_nas_runtime_stack.node_platform_arch("aarch64"), "arm64")
        self.assertEqual(
            install_nas_runtime_stack.node_dist_url("22.22.0", "x64"),
            "https://nodejs.org/dist/v22.22.0/node-v22.22.0-linux-x64.tar.xz",
        )


if __name__ == "__main__":
    unittest.main()
