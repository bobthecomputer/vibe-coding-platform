from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .models import VerificationResult
from .safety import risk_level_for_command


class VerificationRunner:
    def __init__(self, default_timeout_seconds: int = 120) -> None:
        self.default_timeout_seconds = default_timeout_seconds

    def run(self, commands: list[str], workdir: Path) -> list[VerificationResult]:
        results: list[VerificationResult] = []
        for command in commands:
            risk_level = risk_level_for_command(command)
            if risk_level == "high":
                results.append(
                    VerificationResult(
                        command=command,
                        return_code=126,
                        stdout="",
                        stderr="Blocked high-risk command by safety policy.",
                        duration_ms=0,
                        status="blocked",
                        risk_level=risk_level,
                    )
                )
                continue

            start = time.monotonic()
            completed = subprocess.run(  # noqa: S603
                command,
                shell=True,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=self.default_timeout_seconds,
                check=False,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            results.append(
                VerificationResult(
                    command=command,
                    return_code=completed.returncode,
                    stdout=completed.stdout.strip(),
                    stderr=completed.stderr.strip(),
                    duration_ms=duration_ms,
                    status="executed",
                    risk_level=risk_level,
                )
            )
        return results


def detect_default_verification_commands(workdir: Path) -> list[str]:
    commands: list[str] = []
    has_pyproject = (workdir / "pyproject.toml").exists()
    has_tests_dir = (workdir / "tests").exists()
    if has_pyproject and has_tests_dir:
        commands.append("python -m unittest discover -s tests")
    return commands
