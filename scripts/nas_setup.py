from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from grant_agent.web_backend import ADMIN_PASSWORD_RELATIVE_PATH, ensure_admin_config


def run(command: list[str]) -> None:
    completed = subprocess.run(command, cwd=str(ROOT), check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare Grand Agent for NAS hosting.")
    parser.add_argument("--skip-npm", action="store_true", help="Do not install/build frontend assets.")
    parser.add_argument(
        "--reset-admin-password",
        action="store_true",
        help="Generate a fresh ignored admin password file.",
    )
    args = parser.parse_args(argv)

    _, generated = ensure_admin_config(ROOT, reset_password=args.reset_admin_password)
    if not args.skip_npm:
        run(["npm", "ci"])
        run(["npm", "run", "frontend:build"])

    password_path = ROOT / ADMIN_PASSWORD_RELATIVE_PATH
    if generated:
        print(f"Admin password generated at {password_path}")
    else:
        print(f"Admin config already exists at {ROOT / '.agent_control' / 'grand_agent_web_admin.json'}")
    print("Start with: python scripts/run_web_backend.py --host 0.0.0.0 --port 47880")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
