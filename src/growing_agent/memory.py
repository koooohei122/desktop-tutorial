from __future__ import annotations

import json
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
from typing import Any

from .i18n import DEFAULT_LANGUAGE, normalize_language

DEFAULT_STATE: dict[str, Any] = {
    "iteration": 0,
    "last_score": None,
    "history": [],
    "language": DEFAULT_LANGUAGE,
}


def build_default_state() -> dict[str, Any]:
    return {
        "iteration": 0,
        "last_score": None,
        "history": [],
        "language": DEFAULT_LANGUAGE,
    }


class MemoryStore:
    """Simple JSON-backed memory store for agent state."""

    def __init__(self, state_path: str | Path = "data/state.json") -> None:
        self.state_path = Path(state_path)

    def read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return build_default_state()

        with self.state_path.open("r", encoding="utf-8") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                self._backup_corrupt_file()
                state = build_default_state()
                try:
                    self.write_state(state)
                except OSError:
                    # Fallback to in-memory recovery if filesystem writes fail.
                    pass
                return state

        return self._normalize_state(data)

    def write_state(self, state: dict[str, Any]) -> None:
        normalized = self._normalize_state(state)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(normalized, file, indent=2, ensure_ascii=True)
            file.write("\n")
        os.replace(temp_path, self.state_path)

    def reset_state(self) -> dict[str, Any]:
        state = build_default_state()
        self.write_state(state)
        return state

    def _backup_corrupt_file(self) -> None:
        if not self.state_path.exists():
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = self.state_path.with_suffix(self.state_path.suffix + f".corrupt-{timestamp}")
        counter = 1
        while backup.exists():
            backup = self.state_path.with_suffix(
                self.state_path.suffix + f".corrupt-{timestamp}-{counter}"
            )
            counter += 1
        shutil.copy2(self.state_path, backup)

    def _normalize_state(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            return build_default_state()

        default = build_default_state()
        extras = {k: v for k, v in data.items() if k not in default}

        raw_iteration = data.get("iteration", default["iteration"])
        try:
            iteration = int(raw_iteration)
        except (TypeError, ValueError):
            iteration = 0

        history = data.get("history", default["history"])
        if not isinstance(history, list):
            history = []
        else:
            history = [item for item in history if isinstance(item, dict)]

        raw_last_score = data.get("last_score", default["last_score"])
        if isinstance(raw_last_score, (int, float)):
            last_score: float | None = round(float(raw_last_score), 3)
        else:
            last_score = None

        language = normalize_language(data.get("language", default["language"]))

        normalized = {
            **extras,
            "iteration": max(0, iteration),
            "last_score": last_score,
            "history": history,
            "language": language,
        }
        return normalized
