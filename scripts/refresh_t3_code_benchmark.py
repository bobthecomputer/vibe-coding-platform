from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from grant_agent.t3_benchmark import (  # noqa: E402
    fetch_t3_code_release_benchmark,
    write_t3_code_release_benchmark,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh Fluxio's T3 Code release benchmark evidence.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    payload = fetch_t3_code_release_benchmark(timeout_seconds=max(1, int(args.timeout_seconds)))
    if args.write:
        payload["evidencePath"] = str(write_t3_code_release_benchmark(Path(args.root), payload))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
