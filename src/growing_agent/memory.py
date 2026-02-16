"""Persistent state backed by data/state.json."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path("data/state.json")

_DEFAULT_STATE: dict[str, Any] = {
    "iteration": 0,
    "score": 0.0,
    "history": [],
    "plan": [],
}


def _resolve(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_STATE_PATH


def read_state(path: Path | None = None) -> dict[str, Any]:
    """Load state from *path* (default ``data/state.json``).

    Returns a fresh default state when the file does not exist yet.
    """
    fpath = _resolve(path)
    if not fpath.exists():
        logger.info("State file %s not found – using defaults.", fpath)
        return dict(_DEFAULT_STATE)
    with fpath.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    logger.debug("Loaded state from %s", fpath)
    return data


def write_state(state: dict[str, Any], path: Path | None = None) -> None:
    """Persist *state* to *path* (default ``data/state.json``)."""
    fpath = _resolve(path)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    with fpath.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
    logger.info("State written to %s", fpath)
