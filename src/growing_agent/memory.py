from __future__ import annotations

import json
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
from typing import Any

from .i18n import DEFAULT_LANGUAGE, normalize_language


def build_default_autonomy_state() -> dict[str, Any]:
    return {
        "queue": [],
        "completed": [],
        "learning": {
            "task_type_stats": {},
            "improvement_backlog": [],
        },
    }


DEFAULT_STATE: dict[str, Any] = {
    "iteration": 0,
    "last_score": None,
    "history": [],
    "language": DEFAULT_LANGUAGE,
    "autonomy": build_default_autonomy_state(),
}


def build_default_state() -> dict[str, Any]:
    return {
        "iteration": 0,
        "last_score": None,
        "history": [],
        "language": DEFAULT_LANGUAGE,
        "autonomy": build_default_autonomy_state(),
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
        autonomy = self._normalize_autonomy(data.get("autonomy", default["autonomy"]))

        normalized = {
            **extras,
            "iteration": max(0, iteration),
            "last_score": last_score,
            "history": history,
            "language": language,
            "autonomy": autonomy,
        }
        return normalized

    def _normalize_autonomy(self, autonomy: Any) -> dict[str, Any]:
        default = build_default_autonomy_state()
        if not isinstance(autonomy, dict):
            return default

        extras = {k: v for k, v in autonomy.items() if k not in default}

        queue = autonomy.get("queue", default["queue"])
        if not isinstance(queue, list):
            queue = []
        else:
            queue = [item for item in queue if isinstance(item, dict)]

        completed = autonomy.get("completed", default["completed"])
        if not isinstance(completed, list):
            completed = []
        else:
            completed = [item for item in completed if isinstance(item, dict)]

        learning_raw = autonomy.get("learning", default["learning"])
        if not isinstance(learning_raw, dict):
            learning_raw = {}

        stats_raw = learning_raw.get("task_type_stats", {})
        if not isinstance(stats_raw, dict):
            stats_raw = {}
        task_type_stats: dict[str, dict[str, Any]] = {}
        for task_type, stat in stats_raw.items():
            if not isinstance(task_type, str) or not isinstance(stat, dict):
                continue
            attempts_raw = stat.get("attempts", 0)
            successes_raw = stat.get("successes", 0)
            avg_reward_raw = stat.get("avg_reward", 0.0)
            try:
                attempts = max(0, int(attempts_raw))
            except (TypeError, ValueError):
                attempts = 0
            try:
                successes = max(0, int(successes_raw))
            except (TypeError, ValueError):
                successes = 0
            try:
                avg_reward = float(avg_reward_raw)
            except (TypeError, ValueError):
                avg_reward = 0.0
            task_type_stats[task_type] = {
                **stat,
                "attempts": attempts,
                "successes": successes,
                "avg_reward": round(avg_reward, 3),
            }

        backlog_raw = learning_raw.get("improvement_backlog", [])
        if not isinstance(backlog_raw, list):
            backlog_raw = []
        improvement_backlog = [item for item in backlog_raw if isinstance(item, dict)]

        learning = {
            **learning_raw,
            "task_type_stats": task_type_stats,
            "improvement_backlog": improvement_backlog,
        }

        normalized = {
            **extras,
            "queue": queue,
            "completed": completed,
            "learning": learning,
        }
        return normalized
