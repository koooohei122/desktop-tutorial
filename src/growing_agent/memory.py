from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "history": [],
        "last_score": None,
    }


@dataclass(frozen=True)
class StateStore:
    """
    Very small JSON-backed state store.

    Reads/writes `data/state.json` relative to the current working directory.
    """

    base_dir: Path = field(default_factory=Path.cwd)

    @property
    def state_path(self) -> Path:
        return self.base_dir / "data" / "state.json"

    def load(self) -> dict[str, Any]:
        path = self.state_path
        if not path.exists():
            return _default_state()

        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return _default_state()
            data.setdefault("version", 1)
            data.setdefault("history", [])
            data.setdefault("last_score", None)
            data.setdefault("created_at", _utc_now_iso())
            data["updated_at"] = _utc_now_iso()
            return data
        except Exception:
            # If the file is corrupted, start fresh rather than crashing.
            return _default_state()

    def save(self, state: dict[str, Any]) -> None:
        path = self.state_path
        path.parent.mkdir(parents=True, exist_ok=True)

        state = dict(state)
        state.setdefault("version", 1)
        state.setdefault("created_at", _utc_now_iso())
        state["updated_at"] = _utc_now_iso()

        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)

