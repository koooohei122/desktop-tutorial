"""Read/write state to data/state.json."""

import json
from pathlib import Path


def _state_path(cwd: Path | None = None) -> Path:
    base = cwd or Path.cwd()
    return base / "data" / "state.json"


def read_state(cwd: Path | None = None) -> dict:
    """Load state from data/state.json. Returns empty dict if missing."""
    path = _state_path(cwd)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_state(state: dict, cwd: Path | None = None) -> None:
    """Write state to data/state.json."""
    path = _state_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
