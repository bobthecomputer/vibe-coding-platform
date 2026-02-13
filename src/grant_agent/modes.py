from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModePreset:
    name: str
    persona: str
    max_tokens: int
    max_handoffs: int
    max_runtime_seconds: int


class ModeRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._modes = self._load(path)

    @staticmethod
    def _load(path: Path) -> dict[str, ModePreset]:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        out: dict[str, ModePreset] = {}
        for key, value in payload.items():
            out[key] = ModePreset(
                name=key,
                persona=value["persona"],
                max_tokens=int(value["max_tokens"]),
                max_handoffs=int(value["max_handoffs"]),
                max_runtime_seconds=int(value["max_runtime_seconds"]),
            )
        return out

    def get(self, name: str) -> ModePreset:
        if name in self._modes:
            return self._modes[name]
        if "balanced" in self._modes:
            return self._modes["balanced"]
        return ModePreset(
            name="fallback",
            persona="balanced_builder",
            max_tokens=2400,
            max_handoffs=6,
            max_runtime_seconds=300,
        )
