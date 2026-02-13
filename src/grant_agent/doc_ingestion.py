from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass
class DocEvidence:
    source: str
    kind: str
    status: str
    chars: int
    excerpt: str
    error: str = ""


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _excerpt(text: str, max_chars: int = 500) -> str:
    return text[:max_chars].replace("\n", " ").strip()


def _read_url(source: str, timeout_seconds: int = 10) -> DocEvidence:
    request = Request(source, headers={"User-Agent": "grant-agent-harness/0.1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            raw = response.read(20000)
        text = raw.decode("utf-8", errors="ignore")
        return DocEvidence(
            source=source,
            kind="url",
            status="ok",
            chars=len(text),
            excerpt=_excerpt(text),
        )
    except (URLError, TimeoutError, OSError) as exc:
        return DocEvidence(
            source=source,
            kind="url",
            status="error",
            chars=0,
            excerpt="",
            error=str(exc),
        )


def _read_file(source: str, repo_path: Path) -> DocEvidence:
    path = Path(source)
    if not path.is_absolute():
        path = (repo_path / source).resolve()
    try:
        text = path.read_text(encoding="utf-8")
        return DocEvidence(
            source=str(path),
            kind="file",
            status="ok",
            chars=len(text),
            excerpt=_excerpt(text),
        )
    except OSError as exc:
        return DocEvidence(
            source=str(path),
            kind="file",
            status="error",
            chars=0,
            excerpt="",
            error=str(exc),
        )


def ingest_docs(docs: list[str], repo_path: Path, session_path: Path) -> list[DocEvidence]:
    records: list[DocEvidence] = []
    for source in docs:
        if _is_url(source):
            records.append(_read_url(source))
        else:
            records.append(_read_file(source, repo_path=repo_path))

    evidence_path = session_path / "docs_evidence.json"
    evidence_path.write_text(json.dumps([asdict(item) for item in records], indent=2), encoding="utf-8")
    return records
