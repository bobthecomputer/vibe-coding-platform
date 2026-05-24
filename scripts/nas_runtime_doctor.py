from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_BIN_DIRS = [
    ROOT / ".agent_control" / "runtime" / "bin",
    ROOT.parent / "runtime" / "bin",
]
COMMANDS = ("node", "npm", "npx", "openclaw", "hermes", "python3", "python", "pytest", "git")


def runtime_path_entries(extra_bin_dir: list[str] | None = None) -> list[str]:
    candidates = [Path(value) for value in extra_bin_dir or [] if value]
    candidates.extend(DEFAULT_RUNTIME_BIN_DIRS)
    output: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate.exists():
            continue
        value = str(candidate.resolve())
        if value in seen:
            continue
        output.append(value)
        seen.add(value)
    return output


def runtime_env(extra_bin_dir: list[str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    path_entries = runtime_path_entries(extra_bin_dir)
    if path_entries:
        env["PATH"] = os.pathsep.join([*path_entries, env.get("PATH", "")])
    return env


def command_version(command: str, env: dict[str, str]) -> str:
    resolved = shutil.which(command, path=env.get("PATH"))
    if not resolved:
        return ""
    try:
        completed = subprocess.run(
            [resolved, "--version"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - defensive for live NAS installs.
        return f"error: {exc}"
    return (completed.stdout or completed.stderr or "").strip().splitlines()[0:1][0] if (
        completed.stdout or completed.stderr
    ).strip() else "installed"


def inspect_commands(extra_bin_dir: list[str] | None = None) -> dict[str, object]:
    env = runtime_env(extra_bin_dir)
    commands = {}
    for command in COMMANDS:
        resolved = shutil.which(command, path=env.get("PATH"))
        commands[command] = {
            "detected": bool(resolved),
            "command": resolved or "",
            "version": command_version(command, env) if resolved else "",
        }
    verification_ready = bool(
        commands["python"]["detected"]
        and commands["pytest"]["detected"]
        and commands["git"]["detected"]
    )
    return {
        "runtimeBinDirs": runtime_path_entries(extra_bin_dir),
        "commands": commands,
        "ready": bool(
            commands["node"]["detected"]
            and commands["npm"]["detected"]
            and commands["openclaw"]["detected"]
            and commands["hermes"]["detected"]
        ),
        "verificationReady": verification_ready,
        "verificationIssues": [
            message
            for detected, message in (
                (commands["python"]["detected"], "Runtime python is missing."),
                (commands["pytest"]["detected"], "pytest is missing from the runtime PATH."),
                (commands["git"]["detected"], "git is missing from the runtime PATH; git diff/status cannot work."),
            )
            if not detected
        ],
        "installPlan": [
            "Run: python scripts/install_nas_runtime_stack.py --install-openclaw --install-hermes.",
            "Install Synology Git through Package Center or ensure a compatible git binary is on PATH.",
            "Start the web backend with SYNTELOS_RUNTIME_BIN_DIR pointing to the runtime bin directory if it is not one of the default locations.",
            "Run openclaw onboard --install-daemon and configure provider auth before the first model request.",
            "Run hermes setup or connect provider auth before the first Hermes model request.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check NAS runtime binaries for Syntelos web missions.")
    parser.add_argument("--extra-bin-dir", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    payload = inspect_commands(args.extra_bin_dir)
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0 if payload["ready"] else 1

    print("Syntelos NAS runtime doctor")
    for name, item in payload["commands"].items():
        status = "ready" if item["detected"] else "missing"
        version = f" ({item['version']})" if item["version"] else ""
        print(f"- {name}: {status}{version}")
        if item["command"]:
            print(f"  {item['command']}")
    if payload["runtimeBinDirs"]:
        print("")
        print("Runtime bin directories:")
        for value in payload["runtimeBinDirs"]:
            print(f"  {value}")
    if not payload["verificationReady"]:
        print("")
        print("Verification issues:")
        for issue in payload["verificationIssues"]:
            print(f"- {issue}")
    if not payload["ready"]:
        print("")
        print("Install plan:")
        for step in payload["installPlan"]:
            print(f"- {step}")
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
