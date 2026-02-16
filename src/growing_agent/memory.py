from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STATE: dict[str, Any] = {"iteration": 0, "history": []}


class MemoryStore:
    """Simple JSON-backed memory store for agent state."""

    def __init__(self, state_path: str | Path = "data/state.json") -> None:
        self.state_path = Path(state_path)

    def read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return dict(DEFAULT_STATE)

        with self.state_path.open("r", encoding="utf-8") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                return dict(DEFAULT_STATE)

        if not isinstance(data, dict):
            return dict(DEFAULT_STATE)
        return data

    def write_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w", encoding="utf-8") as file:
            json.dump(state, file, indent=2, ensure_ascii=True)
            file.write("\n")
