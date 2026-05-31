from __future__ import annotations

import json
import os
import shutil
import subprocess
import argparse
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def find_executable(name: str) -> str | None:
    suffixes = [""]
    if not name.endswith(".cmd"):
        suffixes.append(".cmd")
    if not name.endswith(".exe"):
        suffixes.append(".exe")
    for candidate in [shutil.which(name), shutil.which(f"{name}.cmd"), shutil.which(f"{name}.exe")]:
        if candidate:
            return candidate
    for parent in [ROOT, *ROOT.parents]:
        for suffix in suffixes:
            candidate = parent / "runtime" / "bin" / f"{name}{suffix}"
            if candidate.exists():
                return str(candidate)
        runtime_root = parent / "runtime"
        if runtime_root.exists():
            for candidate in runtime_root.glob(f"node-*/bin/{name}"):
                if candidate.exists():
                    return str(candidate)
    return None


def verify_launcher_package(root: Path = ROOT) -> dict:
    root = root.resolve()
    package_path = root / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    npm = find_executable("npm")
    node = find_executable("node")
    require(npm is not None, "npm must be available to verify the package tarball")
    require(node is not None, "node must be available to verify the package bin")
    tool_path = os.pathsep.join(
        [
            str(Path(node).parent),
            str(Path(npm).parent),
            os.environ.get("PATH", ""),
        ]
    )
    npm_home = ROOT / ".agent_control" / "npm-home"
    npm_cache = ROOT / ".agent_control" / "npm-cache"
    npm_home.mkdir(parents=True, exist_ok=True)
    npm_cache.mkdir(parents=True, exist_ok=True)
    tool_env = {
        **os.environ,
        "PATH": tool_path,
        "HOME": str(npm_home),
        "USERPROFILE": str(npm_home),
        "npm_config_cache": str(npm_cache),
        "npm_config_update_notifier": "false",
        "npm_config_audit": "false",
        "npm_config_fund": "false",
    }
    bin_map = package.get("bin", {})
    files = set(package.get("files", []))
    cli_path = root / str(bin_map.get("fluxio", ""))
    cli_text = cli_path.read_text(encoding="utf-8")

    require(bin_map.get("fluxio") == "scripts/fluxio-cli.mjs", "package bin.fluxio must point to scripts/fluxio-cli.mjs")
    require(cli_text.startswith("#!/usr/bin/env node"), "CLI bin must be directly executable by Node")
    require("launch_fluxio.py" in cli_text, "CLI bin must delegate to the existing web launcher")
    require("scripts/launch_fluxio.py" in files, "package files must include the Python launcher")
    require("scripts/run_web_backend.py" in files, "package files must include the backend runner")
    require("web/dist" in files, "package files must include the built web app")
    require("web/public" in files, "package files must include PWA public assets")

    help_check = subprocess.run(
        [node, "scripts/fluxio-cli.mjs", "--help"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env=tool_env,
    )
    require("Start Fluxio's local web console" in help_check.stdout, "package bin must delegate to launcher help")
    npm_exec_check = subprocess.run(
        [npm, "exec", "--", "fluxio", "--help"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env=tool_env,
    )
    require(
        "Start Fluxio's local web console" in npm_exec_check.stdout,
        "npm exec must reach the Fluxio package bin",
    )

    packed = subprocess.run(
        [npm, "pack", "--dry-run", "--json"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env=tool_env,
    )
    payload = json.loads(packed.stdout)[0]
    packed_files = {item["path"] for item in payload.get("files", [])}
    for required in [
        "scripts/fluxio-cli.mjs",
        "scripts/launch_fluxio.py",
        "scripts/run_web_backend.py",
        "web/dist/index.html",
        "web/dist/manifest.webmanifest",
        "web/dist/service-worker.js",
        "web/dist/offline.html",
    ]:
        require(required in packed_files, f"npm package is missing {required}")

    return {
        "ok": True,
        "schema": "fluxio.launcher_package_verification.v1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "package": payload.get("name", package.get("name")),
        "version": payload.get("version", package.get("version")),
        "entrypoint": bin_map["fluxio"],
        "packedFileCount": len(packed_files),
        "helpCommand": "node scripts/fluxio-cli.mjs --help",
        "npmExecCommand": "npm exec -- fluxio --help",
        "packCommand": "npm pack --dry-run --json",
        "requiredPackedFiles": [
            "scripts/fluxio-cli.mjs",
            "scripts/launch_fluxio.py",
            "scripts/run_web_backend.py",
            "web/dist/index.html",
            "web/dist/manifest.webmanifest",
            "web/dist/service-worker.js",
            "web/dist/offline.html",
        ],
        "nextAction": "Attach this launcher receipt to the release candidate before public npm or signed installer publication.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the Fluxio npx-style package launcher.")
    parser.add_argument("--write", action="store_true", help="Write .agent_control/launcher_package/latest.json")
    args = parser.parse_args(argv)

    payload = verify_launcher_package(ROOT)
    if args.write:
        out_dir = ROOT / ".agent_control" / "launcher_package"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "latest.json"
        payload["evidencePath"] = str(out_path)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
