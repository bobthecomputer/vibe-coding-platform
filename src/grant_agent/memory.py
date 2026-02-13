from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import utc_now_iso


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


@dataclass
class MemoryItem:
    id: str
    created_at: str
    source_session_id: str
    objective: str
    content: str
    tags: list[str]
    kind: str


class MemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.items = self._load(path)

    @staticmethod
    def _load(path: Path) -> list[MemoryItem]:
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        items: list[MemoryItem] = []
        for raw in payload:
            items.append(
                MemoryItem(
                    id=raw["id"],
                    created_at=raw["created_at"],
                    source_session_id=raw["source_session_id"],
                    objective=raw["objective"],
                    content=raw["content"],
                    tags=raw.get("tags", []),
                    kind=raw.get("kind", "note"),
                )
            )
        return items

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(item) for item in self.items], indent=2), encoding="utf-8")

    def add(self, source_session_id: str, objective: str, content: str, tags: list[str], kind: str) -> MemoryItem:
        item = MemoryItem(
            id=f"mem_{uuid.uuid4().hex[:10]}",
            created_at=utc_now_iso(),
            source_session_id=source_session_id,
            objective=objective,
            content=content,
            tags=tags,
            kind=kind,
        )
        self.items.append(item)
        self.save()
        return item

    def recent(self, limit: int = 10) -> list[MemoryItem]:
        return sorted(self.items, key=lambda item: item.created_at, reverse=True)[:limit]

    def search(self, query: str, limit: int = 8) -> list[MemoryItem]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return self.recent(limit=limit)

        def score(item: MemoryItem) -> tuple[int, int]:
            text_tokens = _tokens(item.content + " " + " ".join(item.tags) + " " + item.objective)
            overlap = len(query_tokens & text_tokens)
            return overlap, len(item.tags)

        ranked = sorted(self.items, key=score, reverse=True)
        positive = [item for item in ranked if score(item)[0] > 0]
        if positive:
            return positive[:limit]
        return self.recent(limit=limit)


def ingest_state_into_memory(memory: MemoryStore, session_id: str, state: dict) -> list[str]:
    objective = state.get("objective", "")
    inserted_ids: list[str] = []

    for decision in state.get("decisions", [])[-3:]:
        item = memory.add(
            source_session_id=session_id,
            objective=objective,
            content=decision,
            tags=["decision", "autonomy"],
            kind="decision",
        )
        inserted_ids.append(item.id)

    for risk in state.get("risks", [])[-2:]:
        item = memory.add(
            source_session_id=session_id,
            objective=objective,
            content=risk,
            tags=["risk", "safety"],
            kind="risk",
        )
        inserted_ids.append(item.id)

    for action in state.get("next_actions", [])[:2]:
        item = memory.add(
            source_session_id=session_id,
            objective=objective,
            content=action,
            tags=["next_action", "resume"],
            kind="next_action",
        )
        inserted_ids.append(item.id)

    return inserted_ids
