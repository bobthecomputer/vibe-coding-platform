from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path


EXCLUDED_DIRS = {".git", ".agent_runs", ".agent_runs_test", "__pycache__", ".venv", "venv"}


@dataclass
class SearchMatch:
    path: str
    line: int
    snippet: str


def search_workspace(
    root: Path,
    query: str,
    include_glob: str = "**/*",
    max_results: int = 25,
    case_sensitive: bool = False,
) -> list[dict]:
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(query, flags=flags)

    results: list[SearchMatch] = []
    for path in root.glob(include_glob):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        for index, line in enumerate(lines, start=1):
            if pattern.search(line):
                relative = str(path.relative_to(root))
                results.append(SearchMatch(path=relative, line=index, snippet=line.strip()))
                if len(results) >= max_results:
                    return [asdict(item) for item in results]
    return [asdict(item) for item in results]
