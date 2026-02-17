from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time
from typing import Any
from urllib.parse import urlparse
import uuid

from .i18n import DEFAULT_LANGUAGE, normalize_language
from .memory import MemoryStore
from .tools.runner import BLOCKED_TOKENS, CommandRunner

SUPPORTED_AUTONOMY_TASKS = (
    "command",
    "write_note",
    "analyze_state",
    "desktop_action",
    "desktop_perception",
    "mission",
)
DEFAULT_AUTONOMY_ALLOWED_COMMANDS = (
    "python3",
    "python",
    "pytest",
    "echo",
    "google-chrome",
    "chromium-browser",
    "chromium",
    "microsoft-edge",
    "firefox",
    "code",
    "gnome-terminal",
    "x-terminal-emulator",
    "slack",
    "spotify",
    "gedit",
    "xed",
    "mousepad",
    "kate",
    "notepadqq",
    "pluma",
    "xdotool",
    "scrot",
    "xdg-open",
    "tesseract",
)
LEVEL_XP_STEP = 100
WINDOW_TARGETABLE_ACTIONS = {"focus_window", "hotkey", "type_text", "click", "move", "screenshot"}
TEXT_INPUT_ACTIONS = {"hotkey", "type_text"}
WINDOW_MATCH_MODES = ("smart", "exact", "contains", "regex")
DEFAULT_FOCUS_SETTLE_SECONDS = 0.12
MAX_FOCUS_SETTLE_SECONDS = 2.0
MAX_WINDOW_SEARCH_CANDIDATES = 200
MAX_DESKTOP_ENTRY_CANDIDATES = 120
MAX_APP_LAUNCH_ATTEMPTS = 10
DESKTOP_EXEC_PLACEHOLDER_PATTERN = re.compile(r"%[fFuUdDnNickvm]")
DESKTOP_APPLICATION_DIRS: tuple[Path, ...] = (
    Path("/usr/share/applications"),
    Path.home() / ".local/share/applications",
    Path("/var/lib/flatpak/exports/share/applications"),
    Path.home() / ".local/share/flatpak/exports/share/applications",
)
UNSAFE_LAUNCH_EXECUTABLES = {
    "bash",
    "sh",
    "zsh",
    "fish",
    "python",
    "python3",
    "node",
    "perl",
    "ruby",
    "sudo",
    "su",
}

FUN_TITLES: tuple[tuple[int, str], ...] = (
    (1, "Rookie"),
    (2, "Operator"),
    (4, "Strategist"),
    (7, "Maestro"),
    (10, "Legend"),
)

CHALLENGE_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "task_type": "write_note",
        "title": "Daily highlight challenge #{index}",
        "payload": {
            "path": "data/autonomy/challenges.md",
            "text": "Challenge #{index}: write one positive highlight.",
        },
        "priority": 7,
    },
    {
        "task_type": "analyze_state",
        "title": "State insight challenge #{index}",
        "payload": {"path": "data/autonomy/insights.log"},
        "priority": 6,
    },
    {
        "task_type": "command",
        "title": "Quick command challenge #{index}",
        "payload": {"command": ["echo", "challenge-{index}"]},
        "priority": 6,
    },
)


def build_default_game_state() -> dict[str, Any]:
    return {
        "xp": 0,
        "level": 1,
        "title": "Rookie",
        "streak_days": 0,
        "last_active_date_utc": None,
        "current_success_streak": 0,
        "best_success_streak": 0,
        "badges": [],
        "completed_challenges": 0,
        "active_challenges": [],
    }


def build_default_autonomy_state() -> dict[str, Any]:
    return {
        "queue": [],
        "completed": [],
        "learning": {
            "task_type_stats": {},
            "improvement_backlog": [],
        },
        "game": build_default_game_state(),
    }


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utcday() -> date:
    return datetime.now(timezone.utc).date()


class AutonomousWorker:
    """General autonomous worker for non-coding and coding-adjacent tasks."""

    def __init__(
        self,
        memory: MemoryStore,
        runner: CommandRunner,
        language: str | None = None,
        workspace_root: str | Path | None = None,
        max_completed: int = 300,
        max_improvements: int = 300,
        max_active_challenges: int = 50,
    ) -> None:
        if max_completed < 1:
            raise ValueError("max_completed must be >= 1")
        if max_improvements < 1:
            raise ValueError("max_improvements must be >= 1")
        if max_active_challenges < 1:
            raise ValueError("max_active_challenges must be >= 1")
        self.memory = memory
        self.runner = runner
        self.language = normalize_language(language or DEFAULT_LANGUAGE)
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.max_completed = max_completed
        self.max_improvements = max_improvements
        self.max_active_challenges = max_active_challenges

    def enqueue(
        self,
        task_type: str,
        title: str,
        payload: dict[str, Any] | None = None,
        priority: int = 5,
    ) -> dict[str, Any]:
        task = self._create_task(
            task_type=task_type,
            title=title,
            payload=payload,
            priority=priority,
        )

        state = self.memory.read_state()
        autonomy = self._ensure_autonomy_state(state)
        autonomy["queue"].append(task)
        state["language"] = normalize_language(self.language)
        self.memory.write_state(state)
        return task

    def spawn_challenges(self, count: int = 3, base_priority: int = 6) -> list[dict[str, Any]]:
        if count < 1:
            raise ValueError("count must be >= 1")
        if count > 50:
            raise ValueError("count must be <= 50")

        state = self.memory.read_state()
        autonomy = self._ensure_autonomy_state(state)
        game = self._ensure_game_state(autonomy)

        created: list[dict[str, Any]] = []
        for index in range(count):
            template = CHALLENGE_TEMPLATES[index % len(CHALLENGE_TEMPLATES)]
            payload = json.loads(json.dumps(template["payload"]))
            payload = self._format_template_payload(payload, index + 1)
            template_priority = int(template.get("priority", 6))
            priority = max(1, min(10, max(base_priority, template_priority)))

            task = self._create_task(
                task_type=str(template["task_type"]),
                title=str(template["title"]).format(index=index + 1),
                payload=payload,
                priority=priority,
                is_challenge=True,
                challenge_code=f"challenge-{index + 1}",
            )
            autonomy["queue"].append(task)
            self._register_active_challenge(game, task)
            created.append(task)

        state["language"] = normalize_language(self.language)
        self.memory.write_state(state)
        return created

    def fun_status(self) -> dict[str, Any]:
        state = self.memory.read_state()
        autonomy = self._ensure_autonomy_state(state)
        game = self._ensure_game_state(autonomy)
        learning = autonomy.get("learning", {})
        if not isinstance(learning, dict):
            learning = {"task_type_stats": {}, "improvement_backlog": []}

        queue_size = len(autonomy.get("queue", [])) if isinstance(autonomy.get("queue"), list) else 0
        completed_size = (
            len(autonomy.get("completed", [])) if isinstance(autonomy.get("completed"), list) else 0
        )
        backlog_size = len(learning.get("improvement_backlog", []))
        return {
            "game": game,
            "queue_size": queue_size,
            "completed_size": completed_size,
            "improvement_backlog_size": backlog_size,
            "known_task_types": sorted(learning.get("task_type_stats", {}).keys()),
        }

    def inspect_windows(
        self,
        title: str | None = None,
        window_class: str | None = None,
        window_pid: int | None = None,
        match_mode: str = "smart",
        limit: int = 20,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        normalized_title = title.strip() if isinstance(title, str) else ""
        normalized_class = window_class.strip() if isinstance(window_class, str) else ""
        normalized_pid = self._normalize_window_pid(window_pid)
        safe_limit = max(1, min(200, int(limit)))
        normalized_mode = self._normalize_window_match_mode(match_mode)

        if dry_run:
            return {
                "success": True,
                "summary": "Window inspection simulated (dry-run).",
                "windows": [],
                "window_title": normalized_title,
                "window_class": normalized_class,
                "window_pid": normalized_pid,
                "match_mode": normalized_mode,
                "search_plan": self._build_window_search_plan(
                    window_title=normalized_title,
                    match_mode=normalized_mode,
                    window_class=normalized_class,
                    window_pid=normalized_pid,
                ),
                "dry_run": True,
            }

        candidate_result = self._collect_window_candidates(
            window_title=normalized_title,
            window_class=normalized_class,
            window_pid=normalized_pid,
            match_mode=normalized_mode,
            max_candidates=safe_limit * 3,
        )
        details = candidate_result.get("details", {})
        if not isinstance(details, dict):
            details = {}
        matched_ids_raw = details.get("matched_window_ids", [])
        matched_ids = [
            str(item)
            for item in matched_ids_raw
            if isinstance(item, str) and item.strip()
        ][:safe_limit]
        windows = self._describe_windows(matched_ids, dry_run=False)
        return {
            "success": bool(candidate_result.get("success") is True),
            "summary": str(candidate_result.get("summary", "")),
            "windows": windows,
            "window_title": normalized_title,
            "window_class": normalized_class,
            "window_pid": normalized_pid,
            "match_mode": normalized_mode,
            "selected_strategy": details.get("selected_strategy"),
            "search_plan": details.get("search_plan", []),
            "dry_run": False,
        }

    def run(self, cycles: int = 1, dry_run: bool = False) -> dict[str, Any]:
        if cycles < 1:
            raise ValueError("cycles must be >= 1")

        state = self.memory.read_state()
        autonomy = self._ensure_autonomy_state(state)
        state["language"] = normalize_language(self.language)

        executed: list[dict[str, Any]] = []
        game_events: list[dict[str, Any]] = []
        for _ in range(cycles):
            task = self._select_next_task(autonomy)
            if task is None:
                break

            result = self._execute_task(task, state, dry_run=dry_run, depth=0)
            self._update_learning(autonomy, task, result)
            self._record_completion(autonomy, task, result)
            game_event = self._update_game_progress(autonomy, task, result)
            result["fun"] = game_event
            self._maybe_enqueue_follow_up(autonomy, task, result)
            executed.append(result)
            game_events.append(game_event)

        summary = self._build_summary(autonomy, executed, game_events, dry_run)
        autonomy["last_run"] = summary
        state["autonomy"] = autonomy
        self.memory.write_state(state)
        return {"state": state, "executed": executed, "summary": summary}

    def _create_task(
        self,
        task_type: str,
        title: str,
        payload: dict[str, Any] | None,
        priority: int,
        is_challenge: bool = False,
        challenge_code: str | None = None,
    ) -> dict[str, Any]:
        normalized_task_type = str(task_type).strip()
        if normalized_task_type not in SUPPORTED_AUTONOMY_TASKS:
            raise ValueError(
                f"task_type must be one of: {', '.join(SUPPORTED_AUTONOMY_TASKS)}"
            )
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")

        safe_priority = int(priority)
        safe_priority = max(1, min(10, safe_priority))
        task = {
            "task_id": uuid.uuid4().hex[:12],
            "task_type": normalized_task_type,
            "title": title.strip(),
            "payload": payload,
            "priority": safe_priority,
            "attempts": 0,
            "created_at_utc": _utcnow(),
        }
        if is_challenge:
            task["is_challenge"] = True
            if challenge_code:
                task["challenge_code"] = challenge_code
        return task

    def _format_template_payload(self, payload: dict[str, Any], index: int) -> dict[str, Any]:
        formatted: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, str):
                formatted[key] = value.format(index=index)
            elif isinstance(value, list):
                formatted[key] = [item.format(index=index) if isinstance(item, str) else item for item in value]
            elif isinstance(value, dict):
                formatted[key] = self._format_template_payload(value, index=index)
            else:
                formatted[key] = value
        return formatted

    def _ensure_autonomy_state(self, state: dict[str, Any]) -> dict[str, Any]:
        autonomy = state.get("autonomy")
        if not isinstance(autonomy, dict):
            autonomy = build_default_autonomy_state()

        queue = autonomy.get("queue", [])
        completed = autonomy.get("completed", [])
        learning = autonomy.get("learning", {})

        if not isinstance(queue, list):
            queue = []
        if not isinstance(completed, list):
            completed = []
        if not isinstance(learning, dict):
            learning = {}

        task_type_stats = learning.get("task_type_stats", {})
        improvement_backlog = learning.get("improvement_backlog", [])
        if not isinstance(task_type_stats, dict):
            task_type_stats = {}
        if not isinstance(improvement_backlog, list):
            improvement_backlog = []

        normalized = {
            **autonomy,
            "queue": [item for item in queue if isinstance(item, dict)],
            "completed": [item for item in completed if isinstance(item, dict)],
            "learning": {
                **learning,
                "task_type_stats": {
                    str(key): value
                    for key, value in task_type_stats.items()
                    if isinstance(value, dict)
                },
                "improvement_backlog": [
                    item for item in improvement_backlog if isinstance(item, dict)
                ],
            },
        }
        normalized["game"] = self._normalize_game_state(normalized.get("game"))
        state["autonomy"] = normalized
        return normalized

    def _normalize_game_state(self, game: Any) -> dict[str, Any]:
        default = build_default_game_state()
        if not isinstance(game, dict):
            return default

        extras = {k: v for k, v in game.items() if k not in default}
        badges = game.get("badges", default["badges"])
        if not isinstance(badges, list):
            badges = []
        else:
            badges = [str(item) for item in badges if isinstance(item, str)]

        active = game.get("active_challenges", default["active_challenges"])
        if not isinstance(active, list):
            active = []
        else:
            active = [item for item in active if isinstance(item, dict)]
        active = active[-self.max_active_challenges :]

        normalized = {
            **extras,
            "xp": max(0, int(game.get("xp", default["xp"]))),
            "level": max(1, int(game.get("level", default["level"]))),
            "title": str(game.get("title", default["title"])),
            "streak_days": max(0, int(game.get("streak_days", default["streak_days"]))),
            "last_active_date_utc": game.get("last_active_date_utc"),
            "current_success_streak": max(
                0, int(game.get("current_success_streak", default["current_success_streak"]))
            ),
            "best_success_streak": max(
                0, int(game.get("best_success_streak", default["best_success_streak"]))
            ),
            "badges": badges,
            "completed_challenges": max(
                0, int(game.get("completed_challenges", default["completed_challenges"]))
            ),
            "active_challenges": active,
        }
        normalized["title"] = self._title_for_level(normalized["level"])
        return normalized

    def _ensure_game_state(self, autonomy: dict[str, Any]) -> dict[str, Any]:
        game = self._normalize_game_state(autonomy.get("game"))
        autonomy["game"] = game
        return game

    def _select_next_task(self, autonomy: dict[str, Any]) -> dict[str, Any] | None:
        queue = autonomy["queue"]
        if not queue:
            return None

        learning = autonomy.get("learning", {})
        stats = learning.get("task_type_stats", {})
        if not isinstance(stats, dict):
            stats = {}

        completed = autonomy.get("completed", [])
        recent_types: set[str] = set()
        if isinstance(completed, list):
            for record in completed[-10:]:
                if isinstance(record, dict):
                    recent_types.add(str(record.get("task_type", "")))

        def score(task: dict[str, Any]) -> float:
            raw_priority = task.get("priority", 5)
            raw_attempts = task.get("attempts", 0)
            task_type = str(task.get("task_type", ""))
            task_stats = stats.get(task_type, {})

            try:
                priority = float(raw_priority)
            except (TypeError, ValueError):
                priority = 5.0
            try:
                attempts = float(raw_attempts)
            except (TypeError, ValueError):
                attempts = 0.0
            try:
                avg_reward = float(task_stats.get("avg_reward", 0.5))
            except (TypeError, ValueError):
                avg_reward = 0.5

            challenge_bonus = 0.5 if task.get("is_challenge") is True else 0.0
            novelty_bonus = 0.2 if task_type and task_type not in recent_types else 0.0
            return priority + avg_reward + challenge_bonus + novelty_bonus - (0.1 * attempts)

        best_index = max(range(len(queue)), key=lambda index: score(queue[index]))
        task = queue.pop(best_index)
        task["attempts"] = int(task.get("attempts", 0)) + 1
        task["started_at_utc"] = _utcnow()
        return task

    def _execute_task(
        self,
        task: dict[str, Any],
        state: dict[str, Any],
        dry_run: bool,
        depth: int = 0,
    ) -> dict[str, Any]:
        if depth > 3:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="Task nesting depth exceeded the safety limit.",
                details={},
            )

        task_type = str(task.get("task_type", ""))
        if task_type == "command":
            return self._execute_command_task(task, dry_run=dry_run)
        if task_type == "write_note":
            return self._execute_write_note_task(task, dry_run=dry_run)
        if task_type == "analyze_state":
            return self._execute_analyze_state_task(task, state=state, dry_run=dry_run)
        if task_type == "desktop_action":
            return self._execute_desktop_action_task(task, dry_run=dry_run)
        if task_type == "desktop_perception":
            return self._execute_desktop_perception_task(task, dry_run=dry_run)
        if task_type == "mission":
            return self._execute_mission_task(task, state=state, dry_run=dry_run, depth=depth)

        return self._build_result(
            task=task,
            success=False,
            reward=0.0,
            summary=f"Unsupported task type: {task_type}",
            details={"task_type": task_type},
        )

    def _execute_command_task(self, task: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        payload = task.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        command = payload.get("command")
        if not isinstance(command, list) or not command:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="Command task requires a non-empty command list.",
                details={},
            )
        if not all(isinstance(item, str) and item for item in command):
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="Command list must only contain non-empty strings.",
                details={"command": command},
            )

        raw_timeout = payload.get("timeout_seconds", 30.0)
        try:
            timeout_seconds = float(raw_timeout)
        except (TypeError, ValueError):
            timeout_seconds = 30.0

        try:
            run_result = self.runner.run(
                command,
                dry_run=dry_run,
                timeout_seconds=timeout_seconds,
            )
        except ValueError as error:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="Command execution rejected by validation.",
                details={"error": str(error)},
            )

        success = bool(run_result.allowed and run_result.returncode == 0 and not run_result.timed_out)
        reward = 1.0 if success else 0.0
        summary = "Command task succeeded." if success else "Command task failed."
        details = {
            "command": run_result.command,
            "returncode": run_result.returncode,
            "allowed": run_result.allowed,
            "timed_out": run_result.timed_out,
            "duration_seconds": run_result.duration_seconds,
            "stdout_excerpt": run_result.stdout.strip()[:500],
            "stderr_excerpt": run_result.stderr.strip()[:500],
        }
        return self._build_result(
            task=task,
            success=success,
            reward=reward,
            summary=summary,
            details=details,
        )

    def _execute_write_note_task(self, task: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        payload = task.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="write_note task requires non-empty text.",
                details={},
            )

        raw_path = payload.get("path", "data/autonomy/notes.md")
        try:
            target_path = self._safe_data_path(raw_path)
        except ValueError as error:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="write_note target path is invalid.",
                details={"error": str(error)},
            )

        line = f"- [{_utcnow()}] {text.strip()}\n"
        if not dry_run:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with target_path.open("a", encoding="utf-8") as file:
                file.write(line)

        return self._build_result(
            task=task,
            success=True,
            reward=1.0,
            summary="write_note task completed.",
            details={
                "path": str(target_path),
                "dry_run": dry_run,
                "text_excerpt": text.strip()[:200],
            },
        )

    def _execute_analyze_state_task(
        self,
        task: dict[str, Any],
        state: dict[str, Any],
        dry_run: bool,
    ) -> dict[str, Any]:
        payload = task.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        history = state.get("history", [])
        metrics = state.get("metrics", {})
        autonomy = state.get("autonomy", {})
        if not isinstance(history, list):
            history = []
        if not isinstance(metrics, dict):
            metrics = {}
        if not isinstance(autonomy, dict):
            autonomy = {}

        learning = autonomy.get("learning", {})
        if not isinstance(learning, dict):
            learning = {}
        task_type_stats = learning.get("task_type_stats", {})
        if not isinstance(task_type_stats, dict):
            task_type_stats = {}

        report = {
            "timestamp_utc": _utcnow(),
            "iteration": int(state.get("iteration", 0)),
            "history_entries": len(history),
            "average_score": float(metrics.get("average_score", 0.0)),
            "best_score": float(metrics.get("best_score", 0.0)),
            "queued_tasks": len(autonomy.get("queue", []))
            if isinstance(autonomy.get("queue", []), list)
            else 0,
            "completed_tasks": len(autonomy.get("completed", []))
            if isinstance(autonomy.get("completed", []), list)
            else 0,
            "known_task_types": sorted(task_type_stats.keys()),
        }

        raw_path = payload.get("path", "data/autonomy/insights.log")
        try:
            target_path = self._safe_data_path(raw_path)
        except ValueError as error:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="analyze_state target path is invalid.",
                details={"error": str(error)},
            )

        if not dry_run:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with target_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(report, ensure_ascii=True) + "\n")

        reward = 1.0 if report["history_entries"] > 0 or report["completed_tasks"] > 0 else 0.5
        return self._build_result(
            task=task,
            success=True,
            reward=reward,
            summary="analyze_state task completed.",
            details={"path": str(target_path), "report": report, "dry_run": dry_run},
        )

    def _execute_desktop_action_task(self, task: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        payload = task.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        action = str(payload.get("action", "")).strip().lower()
        if not action:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="desktop_action requires an action field.",
                details={},
            )

        if action == "launch_app":
            raw_app_name = payload.get("app_name", payload.get("app"))
            app_name = raw_app_name.strip() if isinstance(raw_app_name, str) else ""
            if not app_name:
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="launch_app action requires app_name.",
                    details={},
                )
            launch_result = self._launch_app(app_name=app_name, dry_run=dry_run)
            details_raw = launch_result.get("details", {})
            details = details_raw if isinstance(details_raw, dict) else {}
            details["action"] = "launch_app"
            details["app_name"] = app_name
            success = bool(launch_result.get("success") is True)
            return self._build_result(
                task=task,
                success=success,
                reward=1.0 if success else 0.0,
                summary=(
                    "Desktop action 'launch_app' succeeded."
                    if success
                    else "Desktop action 'launch_app' failed."
                ),
                details=details,
            )

        window_title_raw = payload.get("window_title")
        window_title = window_title_raw.strip() if isinstance(window_title_raw, str) else ""
        window_class_raw = payload.get("window_class")
        window_class = window_class_raw.strip() if isinstance(window_class_raw, str) else ""
        window_pid = self._normalize_window_pid(payload.get("window_pid"))
        has_window_selector = bool(window_title or window_class or window_pid is not None)
        raw_window_index = payload.get("window_index", 0)
        try:
            window_index = max(0, int(raw_window_index))
        except (TypeError, ValueError):
            window_index = 0
        window_match_mode = self._normalize_window_match_mode(payload.get("window_match_mode"))

        raw_focus_settle = payload.get("focus_settle_seconds", DEFAULT_FOCUS_SETTLE_SECONDS)
        try:
            focus_settle_seconds = max(0.0, min(MAX_FOCUS_SETTLE_SECONDS, float(raw_focus_settle)))
        except (TypeError, ValueError):
            focus_settle_seconds = DEFAULT_FOCUS_SETTLE_SECONDS

        relative_to_window = self._as_bool(payload.get("relative_to_window", False))

        if action == "wait":
            raw_seconds = payload.get("seconds", 1.0)
            try:
                seconds = float(raw_seconds)
            except (TypeError, ValueError):
                seconds = -1.0
            if seconds < 0:
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="wait action requires seconds >= 0.",
                    details={"seconds": raw_seconds},
                )
            capped = min(seconds, 30.0)
            if not dry_run:
                time.sleep(capped)
            return self._build_result(
                task=task,
                success=True,
                reward=0.7,
                summary="Desktop wait action completed.",
                details={"seconds": capped, "dry_run": dry_run},
            )

        if action == "focus_window":
            if not has_window_selector:
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="focus_window action requires window_title, window_class, or window_pid.",
                    details={},
                )
            focus_result = self._focus_window(
                window_title=window_title,
                window_class=window_class,
                window_pid=window_pid,
                window_index=window_index,
                match_mode=window_match_mode,
                dry_run=dry_run,
            )
            success = bool(focus_result.get("success") is True)
            reward = 1.0 if success else 0.0
            summary = (
                "Desktop action 'focus_window' succeeded."
                if success
                else "Desktop action 'focus_window' failed."
            )
            raw_focus_details = focus_result.get("details", {})
            focus_details = raw_focus_details if isinstance(raw_focus_details, dict) else {}
            focus_target = window_title or window_class or (f"pid:{window_pid}" if window_pid is not None else None)
            details = {
                "action": action,
                "target": focus_target,
                "window_title": window_title if window_title else None,
                "window_class": window_class if window_class else None,
                "window_pid": window_pid,
                "window_index": window_index,
                "window_match_mode": window_match_mode,
                "focus": focus_details,
                "focus_summary": str(focus_result.get("summary", "")),
            }
            return self._build_result(
                task=task,
                success=success,
                reward=reward,
                summary=summary,
                details=details,
            )

        command: list[str] | None = None
        detail_target: str | None = None
        focus_details: dict[str, Any] | None = None
        target_window_id: str = ""
        relative_geometry: dict[str, Any] | None = None
        relative_coordinates: dict[str, Any] | None = None
        click_x: int | None = None
        click_y: int | None = None
        if action == "hotkey":
            raw_keys = payload.get("keys")
            if isinstance(raw_keys, str):
                keys = [raw_keys]
            elif isinstance(raw_keys, list):
                keys = [str(item) for item in raw_keys if str(item).strip()]
            else:
                keys = []
            if not keys:
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="hotkey action requires keys list.",
                    details={},
                )
            command = ["xdotool", "key", "+".join(keys)]
            detail_target = "+".join(keys)
        elif action == "type_text":
            text = payload.get("text")
            if not isinstance(text, str) or not text:
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="type_text action requires non-empty text.",
                    details={},
                )
            raw_delay = payload.get("delay_ms", 12)
            try:
                delay_ms = max(0, int(raw_delay))
            except (TypeError, ValueError):
                delay_ms = 12
            command = ["xdotool", "type", "--delay", str(delay_ms), text]
            detail_target = text[:120]
        elif action == "click":
            try:
                x = int(payload.get("x"))
                y = int(payload.get("y"))
            except (TypeError, ValueError):
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="click action requires integer x and y.",
                    details={},
                )
            try:
                button = int(payload.get("button", 1))
            except (TypeError, ValueError):
                button = 1
            button = max(1, min(5, button))
            click_x = x
            click_y = y
            if not relative_to_window:
                command = ["xdotool", "mousemove", str(x), str(y), "click", str(button)]
            detail_target = f"x={x},y={y},button={button}"
        elif action == "move":
            try:
                x = int(payload.get("x"))
                y = int(payload.get("y"))
            except (TypeError, ValueError):
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="move action requires integer x and y.",
                    details={},
                )
            click_x = x
            click_y = y
            if not relative_to_window:
                command = ["xdotool", "mousemove", str(x), str(y)]
            detail_target = f"x={x},y={y}"
        elif action == "screenshot":
            raw_path = payload.get("path", "data/autonomy/screenshot.png")
            try:
                target = self._safe_data_path(raw_path)
            except ValueError as error:
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="screenshot path is invalid.",
                    details={"error": str(error)},
                )
            detail_target = str(target)
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
            if has_window_selector:
                command = ["scrot", "-u", str(target)]
            else:
                command = ["scrot", str(target)]
        elif action == "open_url":
            url = payload.get("url")
            if not isinstance(url, str) or not url.strip():
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="open_url action requires a url string.",
                    details={},
                )
            parsed = urlparse(url.strip())
            if parsed.scheme not in {"http", "https", "file"}:
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="open_url only supports http/https/file schemes.",
                    details={"url": url},
                )
            command = ["xdg-open", url.strip()]
            detail_target = url.strip()
        else:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary=f"Unsupported desktop action: {action}",
                details={"action": action},
            )

        if has_window_selector and action not in WINDOW_TARGETABLE_ACTIONS:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary=f"Window selectors are not supported for desktop action '{action}'.",
                details={
                    "action": action,
                    "window_title": window_title if window_title else None,
                    "window_class": window_class if window_class else None,
                    "window_pid": window_pid,
                },
            )

        if relative_to_window and action not in {"click", "move"}:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary=f"relative_to_window is only supported for click/move actions, not '{action}'.",
                details={"action": action, "relative_to_window": relative_to_window},
            )

        if relative_to_window and not has_window_selector:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="relative_to_window requires window_title, window_class, or window_pid.",
                details={"action": action, "relative_to_window": relative_to_window},
            )

        if has_window_selector:
            focus_result = self._focus_window(
                window_title=window_title,
                window_class=window_class,
                window_pid=window_pid,
                window_index=window_index,
                match_mode=window_match_mode,
                dry_run=dry_run,
            )
            raw_focus_details = focus_result.get("details", {})
            focus_details = raw_focus_details if isinstance(raw_focus_details, dict) else {}
            if not bool(focus_result.get("success") is True):
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary=f"Desktop action '{action}' failed: unable to focus target window.",
                    details={
                        "action": action,
                        "target": detail_target,
                        "window_title": window_title,
                        "window_class": window_class if window_class else None,
                        "window_pid": window_pid,
                        "window_index": window_index,
                        "window_match_mode": window_match_mode,
                        "focus": focus_details,
                        "focus_summary": str(focus_result.get("summary", "")),
                    },
                )
            target_window_id = str(focus_details.get("window_id", "")).strip()
            if action in TEXT_INPUT_ACTIONS and not dry_run and focus_settle_seconds > 0:
                time.sleep(focus_settle_seconds)

        if relative_to_window:
            if click_x is None or click_y is None:
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="relative_to_window requires click/move coordinates.",
                    details={"action": action},
                )
            if not target_window_id:
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary="relative_to_window could not resolve focused window id.",
                    details={"action": action},
                )
            geometry_result = self._get_window_geometry(
                window_id=target_window_id,
                dry_run=dry_run,
            )
            geometry_raw = geometry_result.get("details", {})
            relative_geometry = geometry_raw if isinstance(geometry_raw, dict) else {}
            if not bool(geometry_result.get("success") is True):
                return self._build_result(
                    task=task,
                    success=False,
                    reward=0.0,
                    summary=f"Desktop action '{action}' failed: unable to resolve window geometry.",
                    details={
                        "action": action,
                        "window_id": target_window_id,
                        "geometry": relative_geometry,
                        "geometry_summary": str(geometry_result.get("summary", "")),
                    },
                )

            base_x = int(relative_geometry.get("x", 0))
            base_y = int(relative_geometry.get("y", 0))
            absolute_x = base_x + click_x
            absolute_y = base_y + click_y
            relative_coordinates = {
                "base_x": base_x,
                "base_y": base_y,
                "offset_x": click_x,
                "offset_y": click_y,
                "absolute_x": absolute_x,
                "absolute_y": absolute_y,
            }
            if action == "click":
                try:
                    button = int(payload.get("button", 1))
                except (TypeError, ValueError):
                    button = 1
                button = max(1, min(5, button))
                command = ["xdotool", "mousemove", str(absolute_x), str(absolute_y), "click", str(button)]
            else:
                command = ["xdotool", "mousemove", str(absolute_x), str(absolute_y)]

        if command is None:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="desktop_action could not resolve command.",
                details={"action": action},
            )

        run_result = self.runner.run(command, dry_run=dry_run, timeout_seconds=30.0)
        retry_attempted = False
        retry_succeeded = False
        retry_focus_details: dict[str, Any] | None = None
        retry_run_result: dict[str, Any] | None = None
        success = bool(run_result.allowed and run_result.returncode == 0 and not run_result.timed_out)
        if (
            not success
            and not dry_run
            and has_window_selector
            and action in TEXT_INPUT_ACTIONS
        ):
            retry_attempted = True
            second_focus = self._focus_window(
                window_title=window_title,
                window_class=window_class,
                window_pid=window_pid,
                window_index=window_index,
                match_mode=window_match_mode,
                dry_run=False,
            )
            second_focus_raw = second_focus.get("details", {})
            retry_focus_details = second_focus_raw if isinstance(second_focus_raw, dict) else {}
            if bool(second_focus.get("success") is True):
                if focus_settle_seconds > 0:
                    time.sleep(focus_settle_seconds)
                second_run = self.runner.run(command, dry_run=False, timeout_seconds=30.0)
                retry_run_result = {
                    "command": second_run.command,
                    "returncode": second_run.returncode,
                    "allowed": second_run.allowed,
                    "timed_out": second_run.timed_out,
                    "duration_seconds": second_run.duration_seconds,
                    "stdout_excerpt": second_run.stdout.strip()[:500],
                    "stderr_excerpt": second_run.stderr.strip()[:500],
                }
                if bool(second_run.allowed and second_run.returncode == 0 and not second_run.timed_out):
                    run_result = second_run
                    success = True
                    retry_succeeded = True

        reward = 1.0 if success else 0.0
        summary = f"Desktop action '{action}' succeeded." if success else f"Desktop action '{action}' failed."
        details = {
            "action": action,
            "target": detail_target,
            "command": run_result.command,
            "window_title": window_title if window_title else None,
            "window_class": window_class if window_class else None,
            "window_pid": window_pid,
            "window_index": window_index if has_window_selector else None,
            "window_match_mode": window_match_mode if has_window_selector else None,
            "focus_settle_seconds": focus_settle_seconds if (has_window_selector and action in TEXT_INPUT_ACTIONS) else None,
            "relative_to_window": relative_to_window,
            "returncode": run_result.returncode,
            "allowed": run_result.allowed,
            "timed_out": run_result.timed_out,
            "duration_seconds": run_result.duration_seconds,
            "stdout_excerpt": run_result.stdout.strip()[:500],
            "stderr_excerpt": run_result.stderr.strip()[:500],
            "retry_attempted": retry_attempted,
            "retry_succeeded": retry_succeeded,
        }
        if focus_details is not None:
            details["focus"] = focus_details
        if target_window_id:
            details["target_window_id"] = target_window_id
        if relative_geometry is not None:
            details["window_geometry"] = relative_geometry
        if relative_coordinates is not None:
            details["relative_coordinates"] = relative_coordinates
        if retry_focus_details is not None:
            details["retry_focus"] = retry_focus_details
        if retry_run_result is not None:
            details["retry_run"] = retry_run_result
        return self._build_result(
            task=task,
            success=success,
            reward=reward,
            summary=summary,
            details=details,
        )

    def _execute_desktop_perception_task(self, task: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        payload = task.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        raw_capture_path = payload.get(
            "capture_path",
            f"data/autonomy/perception-{str(task.get('task_id', 'snapshot'))}.png",
        )
        try:
            capture_path = self._safe_data_path(raw_capture_path)
        except ValueError as error:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="desktop_perception capture_path is invalid.",
                details={"error": str(error)},
            )

        if not dry_run:
            capture_path.parent.mkdir(parents=True, exist_ok=True)

        capture_result = self.runner.run(
            ["scrot", str(capture_path)],
            dry_run=dry_run,
            timeout_seconds=30.0,
        )
        capture_success = bool(
            capture_result.allowed and capture_result.returncode == 0 and not capture_result.timed_out
        )
        if not capture_success:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="Desktop perception screenshot capture failed.",
                details={
                    "capture_path": str(capture_path),
                    "returncode": capture_result.returncode,
                    "allowed": capture_result.allowed,
                    "timed_out": capture_result.timed_out,
                    "stdout_excerpt": capture_result.stdout.strip()[:500],
                    "stderr_excerpt": capture_result.stderr.strip()[:500],
                },
            )

        ocr_enabled = self._as_bool(payload.get("ocr", True))
        ocr_status = "skipped"
        ocr_excerpt = ""
        ocr_error = ""
        ocr_lang = str(payload.get("ocr_lang", "eng"))
        if ocr_enabled:
            ocr_command = ["tesseract", str(capture_path), "stdout"]
            if ocr_lang.strip():
                ocr_command.extend(["-l", ocr_lang.strip()])
            ocr_result = self.runner.run(
                ocr_command,
                dry_run=dry_run,
                timeout_seconds=30.0,
            )
            ocr_ok = bool(ocr_result.allowed and ocr_result.returncode == 0 and not ocr_result.timed_out)
            if ocr_ok:
                ocr_status = "ok"
                ocr_excerpt = ocr_result.stdout.strip()[:1000]
            else:
                ocr_status = "failed"
                ocr_error = ocr_result.stderr.strip()[:500]
        success = capture_success
        reward = 1.0 if ocr_status in {"ok", "skipped"} else 0.8
        summary = "Desktop perception completed."
        if ocr_status == "failed":
            summary = "Desktop perception completed with OCR fallback."
        return self._build_result(
            task=task,
            success=success,
            reward=reward,
            summary=summary,
            details={
                "capture_path": str(capture_path),
                "ocr_enabled": ocr_enabled,
                "ocr_status": ocr_status,
                "ocr_lang": ocr_lang,
                "ocr_excerpt": ocr_excerpt,
                "ocr_error_excerpt": ocr_error,
                "dry_run": dry_run,
            },
        )

    def _execute_mission_task(
        self,
        task: dict[str, Any],
        state: dict[str, Any],
        dry_run: bool,
        depth: int,
    ) -> dict[str, Any]:
        payload = task.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        raw_steps = payload.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            return self._build_result(
                task=task,
                success=False,
                reward=0.0,
                summary="mission task requires a non-empty steps list.",
                details={},
            )

        raw_max_failures = payload.get("max_step_failures", 0)
        try:
            max_step_failures = max(0, int(raw_max_failures))
        except (TypeError, ValueError):
            max_step_failures = 0
        auto_recovery = self._as_bool(payload.get("auto_recovery", True))

        step_results: list[dict[str, Any]] = []
        failure_count = 0
        hard_stop = False
        for idx, step in enumerate(raw_steps, start=1):
            if not isinstance(step, dict):
                failure_count += 1
                step_results.append(
                    {
                        "step_index": idx,
                        "success": False,
                        "summary": "Invalid step payload; expected object.",
                    }
                )
                if failure_count > max_step_failures:
                    hard_stop = True
                    break
                continue

            step_task_type = str(step.get("task_type", "")).strip()
            if step_task_type not in SUPPORTED_AUTONOMY_TASKS or step_task_type == "mission":
                failure_count += 1
                step_results.append(
                    {
                        "step_index": idx,
                        "success": False,
                        "summary": f"Unsupported mission step task_type: {step_task_type}",
                    }
                )
                if failure_count > max_step_failures:
                    hard_stop = True
                    break
                continue

            step_title_raw = step.get("title")
            if isinstance(step_title_raw, str) and step_title_raw.strip():
                step_title = step_title_raw.strip()
            else:
                step_title = f"{task.get('title', 'mission')} :: step {idx}"

            step_payload = step.get("payload", {})
            if not isinstance(step_payload, dict):
                step_payload = {}

            raw_step_priority = step.get("priority", task.get("priority", 5))
            try:
                step_priority = max(1, min(10, int(raw_step_priority)))
            except (TypeError, ValueError):
                step_priority = 5

            step_task = {
                "task_id": f"{task.get('task_id', 'mission')}:step:{idx}",
                "task_type": step_task_type,
                "title": step_title,
                "payload": step_payload,
                "priority": step_priority,
                "attempts": 0,
                "created_at_utc": _utcnow(),
                "from_mission": str(task.get("task_id", "")),
            }
            step_result = self._execute_task(step_task, state, dry_run=dry_run, depth=depth + 1)
            step_result["step_index"] = idx
            step_results.append(step_result)

            step_success = bool(step_result.get("success") is True)
            continue_on_failure = bool(step.get("continue_on_failure", False))
            if not step_success:
                recovered = False
                on_failure_results: list[dict[str, Any]] = []
                raw_on_failure = step.get("on_failure", [])
                if isinstance(raw_on_failure, list):
                    for rec_idx, rec_step in enumerate(raw_on_failure, start=1):
                        if not isinstance(rec_step, dict):
                            on_failure_results.append(
                                {
                                    "step_index": idx,
                                    "recovery_index": rec_idx,
                                    "success": False,
                                    "summary": "Invalid recovery step payload; expected object.",
                                }
                            )
                            continue
                        rec_task_type = str(rec_step.get("task_type", "")).strip()
                        if rec_task_type not in SUPPORTED_AUTONOMY_TASKS or rec_task_type == "mission":
                            on_failure_results.append(
                                {
                                    "step_index": idx,
                                    "recovery_index": rec_idx,
                                    "success": False,
                                    "summary": (
                                        f"Unsupported recovery task_type: {rec_task_type}"
                                    ),
                                }
                            )
                            continue
                        rec_payload = rec_step.get("payload", {})
                        if not isinstance(rec_payload, dict):
                            rec_payload = {}
                        rec_title = str(
                            rec_step.get(
                                "title",
                                f"{step_title} :: recovery {rec_idx}",
                            )
                        ).strip()
                        raw_rec_priority = rec_step.get("priority", step_priority)
                        try:
                            rec_priority = max(1, min(10, int(raw_rec_priority)))
                        except (TypeError, ValueError):
                            rec_priority = step_priority
                        rec_task = {
                            "task_id": f"{task.get('task_id', 'mission')}:step:{idx}:recovery:{rec_idx}",
                            "task_type": rec_task_type,
                            "title": rec_title,
                            "payload": rec_payload,
                            "priority": rec_priority,
                            "attempts": 0,
                            "created_at_utc": _utcnow(),
                            "from_mission": str(task.get("task_id", "")),
                            "recovery_for_step": idx,
                        }
                        rec_result = self._execute_task(
                            rec_task,
                            state,
                            dry_run=dry_run,
                            depth=depth + 1,
                        )
                        rec_result["recovery_index"] = rec_idx
                        on_failure_results.append(rec_result)
                        if not bool(rec_result.get("success") is True):
                            # keep evaluating remaining recovery steps for traceability
                            continue
                    if on_failure_results:
                        step_result["on_failure_results"] = on_failure_results
                        recovered = all(
                            bool(item.get("success") is True)
                            for item in on_failure_results
                        )

                if not recovered:
                    failure_count += 1
                    if (
                        auto_recovery
                        and not on_failure_results
                        and str(step_task_type) in {"desktop_action", "desktop_perception"}
                    ):
                        step_result["auto_recovery_hint"] = (
                            "No explicit on_failure steps. A follow-up recovery mission may be enqueued."
                        )
                    if not continue_on_failure or failure_count > max_step_failures:
                        hard_stop = True
                        break
                else:
                    step_result["recovered"] = True

        executed_steps = len(step_results)
        total_steps = len(raw_steps)
        completed_all = executed_steps == total_steps and not hard_stop
        success = completed_all and failure_count <= max_step_failures

        reward = 0.0
        if step_results:
            reward = sum(float(item.get("reward", 0.0)) for item in step_results) / len(step_results)
            if success:
                reward = min(1.0, reward + 0.1)
        reward = round(max(0.0, reward), 3)

        summary = (
            "Mission completed successfully."
            if success
            else f"Mission finished with {failure_count} failed step(s)."
        )
        details = {
            "executed_steps": executed_steps,
            "total_steps": total_steps,
            "failure_count": failure_count,
            "max_step_failures": max_step_failures,
            "auto_recovery": auto_recovery,
            "completed_all_steps": completed_all,
            "dry_run": dry_run,
            "step_results": step_results,
        }
        return self._build_result(
            task=task,
            success=success,
            reward=reward,
            summary=summary,
            details=details,
        )

    def _build_result(
        self,
        task: dict[str, Any],
        success: bool,
        reward: float,
        summary: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "task_id": str(task.get("task_id", "")),
            "task_type": str(task.get("task_type", "")),
            "title": str(task.get("title", "")),
            "success": bool(success),
            "reward": round(float(reward), 3),
            "summary": summary,
            "details": details,
            "finished_at_utc": _utcnow(),
        }

    def _update_learning(
        self,
        autonomy: dict[str, Any],
        task: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        learning = autonomy.setdefault(
            "learning",
            {"task_type_stats": {}, "improvement_backlog": []},
        )
        if not isinstance(learning, dict):
            learning = {"task_type_stats": {}, "improvement_backlog": []}
            autonomy["learning"] = learning

        task_stats = learning.setdefault("task_type_stats", {})
        if not isinstance(task_stats, dict):
            task_stats = {}
            learning["task_type_stats"] = task_stats

        task_type = str(task.get("task_type", "unknown"))
        stats = task_stats.setdefault(
            task_type,
            {"attempts": 0, "successes": 0, "avg_reward": 0.0, "last_summary": ""},
        )
        if not isinstance(stats, dict):
            stats = {"attempts": 0, "successes": 0, "avg_reward": 0.0, "last_summary": ""}
            task_stats[task_type] = stats

        attempts = int(stats.get("attempts", 0)) + 1
        successes = int(stats.get("successes", 0)) + (1 if result["success"] else 0)
        previous_avg = float(stats.get("avg_reward", 0.0))
        reward = float(result["reward"])
        avg_reward = ((previous_avg * (attempts - 1)) + reward) / attempts

        stats["attempts"] = attempts
        stats["successes"] = successes
        stats["avg_reward"] = round(avg_reward, 3)
        stats["last_summary"] = str(result.get("summary", ""))
        stats["last_updated_utc"] = _utcnow()

        backlog = learning.setdefault("improvement_backlog", [])
        if not isinstance(backlog, list):
            backlog = []
            learning["improvement_backlog"] = backlog

        if not result["success"]:
            backlog.append(self._build_improvement_item(task, result))
            if len(backlog) > self.max_improvements:
                learning["improvement_backlog"] = backlog[-self.max_improvements :]

    def _update_game_progress(
        self,
        autonomy: dict[str, Any],
        task: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        game = self._ensure_game_state(autonomy)

        today = _utcday()
        previous_level = int(game.get("level", 1))
        previous_xp = int(game.get("xp", 0))
        streak_days = self._update_day_streak(game, today=today)

        success = bool(result.get("success") is True)
        if success:
            game["current_success_streak"] = int(game.get("current_success_streak", 0)) + 1
        else:
            game["current_success_streak"] = 0
        game["best_success_streak"] = max(
            int(game.get("best_success_streak", 0)),
            int(game.get("current_success_streak", 0)),
        )

        priority = int(task.get("priority", 5))
        xp_gain = 5 + max(0, priority - 5)
        xp_gain += int(round(float(result.get("reward", 0.0)) * 10))
        if success:
            xp_gain += 10
        if task.get("is_challenge") is True:
            xp_gain += 12 if success else 4
        xp_gain = max(1, xp_gain)

        game["xp"] = previous_xp + xp_gain
        game["level"] = max(1, int(game["xp"]) // LEVEL_XP_STEP + 1)
        game["title"] = self._title_for_level(int(game["level"]))

        if task.get("is_challenge") is True:
            self._resolve_active_challenge(game, str(task.get("task_id", "")))
            if success:
                game["completed_challenges"] = int(game.get("completed_challenges", 0)) + 1

        new_badges = self._award_badges(game, autonomy)
        level_up = int(game["level"]) > previous_level
        return {
            "xp_gained": xp_gain,
            "xp_total": int(game["xp"]),
            "level": int(game["level"]),
            "title": str(game["title"]),
            "level_up": level_up,
            "streak_days": streak_days,
            "new_badges": new_badges,
            "current_success_streak": int(game["current_success_streak"]),
            "best_success_streak": int(game["best_success_streak"]),
            "completed_challenges": int(game["completed_challenges"]),
        }

    def _update_day_streak(self, game: dict[str, Any], today: date) -> int:
        raw_last = game.get("last_active_date_utc")
        last_day: date | None = None
        if isinstance(raw_last, str):
            try:
                last_day = date.fromisoformat(raw_last)
            except ValueError:
                last_day = None

        current = int(game.get("streak_days", 0))
        if last_day is None:
            current = 1
        elif last_day == today:
            current = max(current, 1)
        elif last_day == today - timedelta(days=1):
            current = max(1, current + 1)
        else:
            current = 1

        game["streak_days"] = current
        game["last_active_date_utc"] = today.isoformat()
        return current

    def _award_badges(self, game: dict[str, Any], autonomy: dict[str, Any]) -> list[str]:
        existing = set(str(item) for item in game.get("badges", []))
        completed = autonomy.get("completed", [])
        if not isinstance(completed, list):
            completed = []

        successful_task_types = set()
        for record in completed:
            if not isinstance(record, dict):
                continue
            result = record.get("result", {})
            if isinstance(result, dict) and result.get("success") is True:
                successful_task_types.add(str(record.get("task_type", "")))

        badge_checks: list[tuple[str, bool]] = [
            ("first_steps", len(completed) >= 1),
            ("steady_runner", int(game.get("streak_days", 0)) >= 3),
            ("hot_hand", int(game.get("best_success_streak", 0)) >= 5),
            ("explorer", len(successful_task_types) >= 3),
            ("challenger", int(game.get("completed_challenges", 0)) >= 3),
            ("level_5", int(game.get("level", 1)) >= 5),
        ]

        new_badges: list[str] = []
        for badge_code, unlocked in badge_checks:
            if unlocked and badge_code not in existing:
                existing.add(badge_code)
                new_badges.append(badge_code)

        ordered_badges = [code for code, _ in badge_checks if code in existing]
        game["badges"] = ordered_badges
        return new_badges

    def _title_for_level(self, level: int) -> str:
        title = "Rookie"
        for min_level, candidate in FUN_TITLES:
            if level >= min_level:
                title = candidate
        return title

    def _register_active_challenge(self, game: dict[str, Any], task: dict[str, Any]) -> None:
        active = game.get("active_challenges", [])
        if not isinstance(active, list):
            active = []
        entry = {
            "task_id": str(task.get("task_id", "")),
            "challenge_code": str(task.get("challenge_code", "")),
            "title": str(task.get("title", "")),
            "created_at_utc": str(task.get("created_at_utc", _utcnow())),
        }
        active.append(entry)
        game["active_challenges"] = active[-self.max_active_challenges :]

    def _resolve_active_challenge(self, game: dict[str, Any], task_id: str) -> None:
        active = game.get("active_challenges", [])
        if not isinstance(active, list):
            game["active_challenges"] = []
            return
        game["active_challenges"] = [
            entry
            for entry in active
            if isinstance(entry, dict) and str(entry.get("task_id", "")) != task_id
        ]

    def _build_improvement_item(
        self,
        task: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        task_type = str(task.get("task_type", "unknown"))
        recommendation = {
            "command": "Verify allowlist, executable path, and command arguments.",
            "write_note": "Ensure target path is under data/ and text is non-empty.",
            "analyze_state": "Verify report output path and state structure.",
            "desktop_action": (
                "Check desktop backend tools, selector fields (title/class/pid), and relative coordinate payload."
            ),
            "desktop_perception": "Check screenshot path and OCR availability.",
            "mission": "Inspect failed steps and retry with continue_on_failure where needed.",
        }.get(task_type, "Review task payload and executor support.")

        details = result.get("details", {})
        if not isinstance(details, dict):
            details = {}
        stderr_excerpt = str(details.get("stderr_excerpt", ""))[:200]

        return {
            "timestamp_utc": _utcnow(),
            "task_id": str(task.get("task_id", "")),
            "task_type": task_type,
            "recommendation": recommendation,
            "error_excerpt": stderr_excerpt,
        }

    def _record_completion(
        self,
        autonomy: dict[str, Any],
        task: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        completed = autonomy.setdefault("completed", [])
        if not isinstance(completed, list):
            completed = []
            autonomy["completed"] = completed

        record = {
            **task,
            "result": result,
            "finished_at_utc": result.get("finished_at_utc", _utcnow()),
        }
        completed.append(record)
        if len(completed) > self.max_completed:
            autonomy["completed"] = completed[-self.max_completed :]

    def _maybe_enqueue_follow_up(
        self,
        autonomy: dict[str, Any],
        task: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        if result["success"]:
            return
        if str(task.get("task_type")) == "analyze_state":
            return
        if int(task.get("attempts", 1)) > 1:
            return

        queue = autonomy.get("queue", [])
        if not isinstance(queue, list):
            return

        source_task_id = str(task.get("task_id", ""))
        task_type = str(task.get("task_type", ""))

        if task_type in {"desktop_action", "desktop_perception", "mission"}:
            for queued in queue:
                if not isinstance(queued, dict):
                    continue
                if str(queued.get("task_type")) != "mission":
                    continue
                payload = queued.get("payload", {})
                if not isinstance(payload, dict):
                    continue
                if str(payload.get("source_task_id")) != source_task_id:
                    continue
                if payload.get("auto_recovery") is True:
                    return

            recovery_mission = {
                "task_id": uuid.uuid4().hex[:12],
                "task_type": "mission",
                "title": f"Auto recovery for {task.get('title', source_task_id)}",
                "payload": {
                    "source_task_id": source_task_id,
                    "auto_recovery": True,
                    "max_step_failures": 1,
                    "steps": [
                        {
                            "task_type": "desktop_action",
                            "title": "Recovery wait",
                            "payload": {"action": "wait", "seconds": 0.3},
                            "continue_on_failure": True,
                        },
                        {
                            "task_type": "desktop_perception",
                            "title": "Recovery perception snapshot",
                            "payload": {
                                "capture_path": "data/autonomy/recovery-snapshot.png",
                                "ocr": False,
                            },
                            "continue_on_failure": True,
                        },
                        {
                            "task_type": "analyze_state",
                            "title": "Recovery state analysis",
                            "payload": {
                                "path": "data/autonomy/insights.log",
                                "source_task_id": source_task_id,
                            },
                            "continue_on_failure": True,
                        },
                    ],
                },
                "priority": min(10, int(task.get("priority", 5)) + 2),
                "attempts": 0,
                "created_at_utc": _utcnow(),
                "auto_generated": True,
            }
            queue.append(recovery_mission)
            return

        for queued in queue:
            if not isinstance(queued, dict):
                continue
            if str(queued.get("task_type")) != "analyze_state":
                continue
            payload = queued.get("payload", {})
            if isinstance(payload, dict) and str(payload.get("source_task_id")) == source_task_id:
                return

        queue.append(
            {
                "task_id": uuid.uuid4().hex[:12],
                "task_type": "analyze_state",
                "title": f"Analyze failure for {task.get('title', source_task_id)}",
                "payload": {
                    "path": "data/autonomy/insights.log",
                    "source_task_id": source_task_id,
                },
                "priority": min(10, int(task.get("priority", 5)) + 1),
                "attempts": 0,
                "created_at_utc": _utcnow(),
                "auto_generated": True,
            }
        )

    def _build_summary(
        self,
        autonomy: dict[str, Any],
        executed: list[dict[str, Any]],
        game_events: list[dict[str, Any]],
        dry_run: bool,
    ) -> dict[str, Any]:
        success_count = sum(1 for item in executed if item.get("success") is True)
        failure_count = len(executed) - success_count
        avg_reward = (
            round(
                sum(float(item.get("reward", 0.0)) for item in executed) / len(executed),
                3,
            )
            if executed
            else 0.0
        )
        queue_size = len(autonomy.get("queue", [])) if isinstance(autonomy.get("queue"), list) else 0
        xp_gained = sum(int(item.get("xp_gained", 0)) for item in game_events)
        level_ups = sum(1 for item in game_events if item.get("level_up") is True)
        new_badges: list[str] = []
        for item in game_events:
            badges = item.get("new_badges", [])
            if not isinstance(badges, list):
                continue
            for badge in badges:
                if isinstance(badge, str) and badge not in new_badges:
                    new_badges.append(badge)

        game = self._ensure_game_state(autonomy)
        return {
            "timestamp_utc": _utcnow(),
            "executed_count": len(executed),
            "success_count": success_count,
            "failure_count": failure_count,
            "average_reward": avg_reward,
            "queue_size": queue_size,
            "dry_run": dry_run,
            "xp_gained": xp_gained,
            "level": int(game.get("level", 1)),
            "title": str(game.get("title", "Rookie")),
            "streak_days": int(game.get("streak_days", 0)),
            "level_ups": level_ups,
            "new_badges": new_badges,
            "completed_challenges": int(game.get("completed_challenges", 0)),
        }

    def _as_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y", "on"}:
                return True
            if normalized in {"0", "false", "no", "n", "off"}:
                return False
        return bool(value)

    def _normalize_window_match_mode(self, value: Any) -> str:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in WINDOW_MATCH_MODES:
                return normalized
        return "smart"

    def _normalize_window_pid(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        if parsed <= 0:
            return None
        return parsed

    def _build_window_search_plan(
        self,
        window_title: str,
        match_mode: str,
        window_class: str = "",
        window_pid: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_title = window_title.strip()
        normalized_mode = self._normalize_window_match_mode(match_mode)
        normalized_class = window_class.strip()
        normalized_pid = self._normalize_window_pid(window_pid)

        base_entry: dict[str, Any] = {}
        if normalized_class:
            base_entry["window_class"] = normalized_class
        if normalized_pid is not None:
            base_entry["window_pid"] = normalized_pid

        if not normalized_title:
            if not base_entry:
                return [{"strategy": "all", "pattern": ".*"}]
            return [{**base_entry, "strategy": "filters_only", "pattern": ""}]

        escaped = re.escape(normalized_title)
        exact_pattern = f"^{escaped}$"
        contains_pattern = normalized_title
        regex_pattern = normalized_title

        if normalized_mode == "exact":
            return [{**base_entry, "strategy": "exact", "pattern": exact_pattern}]
        if normalized_mode == "contains":
            return [{**base_entry, "strategy": "contains", "pattern": contains_pattern}]
        if normalized_mode == "regex":
            return [{**base_entry, "strategy": "regex", "pattern": regex_pattern}]
        # smart: strict exact first, then broader contains match.
        return [
            {**base_entry, "strategy": "exact", "pattern": exact_pattern},
            {**base_entry, "strategy": "contains", "pattern": contains_pattern},
        ]

    def _search_window_ids(
        self,
        pattern: str,
        window_class: str = "",
        window_pid: int | None = None,
        max_candidates: int = 200,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        normalized_class = window_class.strip()
        normalized_pid = self._normalize_window_pid(window_pid)

        command = ["xdotool", "search"]
        if normalized_pid is not None:
            command.extend(["--pid", str(normalized_pid)])
        if normalized_class:
            command.extend(["--class", normalized_class])

        normalized_pattern = pattern.strip()
        if normalized_pattern:
            command.extend(["--name", normalized_pattern])
        elif not normalized_class and normalized_pid is None:
            command.extend(["--name", ".*"])

        result = self.runner.run(
            command,
            dry_run=dry_run,
            timeout_seconds=30.0,
        )
        tokens = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        ]

        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            deduped.append(token)

        numeric: list[tuple[int, str]] = []
        non_numeric: list[str] = []
        for token in deduped:
            try:
                numeric.append((int(token), token))
            except ValueError:
                non_numeric.append(token)
        numeric.sort(key=lambda item: item[0])
        ordered = [item[1] for item in numeric] + sorted(non_numeric)
        ordered = ordered[: max(1, int(max_candidates))]

        success = bool(result.allowed and result.returncode == 0 and not result.timed_out and bool(ordered))
        return {
            "success": success,
            "matched_window_ids": ordered,
            "command": command,
            "returncode": result.returncode,
            "allowed": result.allowed,
            "timed_out": result.timed_out,
            "stdout_excerpt": result.stdout.strip()[:500],
            "stderr_excerpt": result.stderr.strip()[:500],
        }

    def _collect_window_candidates(
        self,
        window_title: str,
        window_class: str,
        window_pid: int | None,
        match_mode: str,
        max_candidates: int = 200,
    ) -> dict[str, Any]:
        search_plan = self._build_window_search_plan(
            window_title=window_title,
            match_mode=match_mode,
            window_class=window_class,
            window_pid=window_pid,
        )
        attempts: list[dict[str, Any]] = []
        for plan_item in search_plan:
            strategy = str(plan_item.get("strategy", "unknown"))
            pattern = str(plan_item.get("pattern", ""))
            plan_window_class = str(plan_item.get("window_class", window_class))
            plan_window_pid = self._normalize_window_pid(plan_item.get("window_pid", window_pid))
            search = self._search_window_ids(
                pattern=pattern,
                window_class=plan_window_class,
                window_pid=plan_window_pid,
                max_candidates=max_candidates,
                dry_run=False,
            )
            attempts.append(
                {
                    "strategy": strategy,
                    "pattern": pattern,
                    "window_class": plan_window_class if plan_window_class else None,
                    "window_pid": plan_window_pid,
                    "success": bool(search["success"]),
                    "matched_count": len(search["matched_window_ids"]),
                    "command": search["command"],
                    "returncode": search["returncode"],
                    "allowed": search["allowed"],
                    "timed_out": search["timed_out"],
                }
            )
            if bool(search["success"]):
                return {
                    "success": True,
                    "summary": "Window candidates resolved.",
                    "details": {
                        "selected_strategy": strategy,
                        "search_pattern": pattern,
                        "window_class": plan_window_class if plan_window_class else None,
                        "window_pid": plan_window_pid,
                        "search_plan": search_plan,
                        "search_attempts": attempts,
                        "matched_count": len(search["matched_window_ids"]),
                        "matched_window_ids": search["matched_window_ids"],
                        "search_command": search["command"],
                        "search_returncode": search["returncode"],
                        "search_allowed": search["allowed"],
                        "search_timed_out": search["timed_out"],
                        "search_stdout_excerpt": search["stdout_excerpt"],
                        "search_stderr_excerpt": search["stderr_excerpt"],
                    },
                }

        last_attempt = attempts[-1] if attempts else {}
        return {
            "success": False,
            "summary": "No matching window found for provided selectors.",
            "details": {
                "window_title": window_title,
                "window_class": window_class if window_class else None,
                "window_pid": self._normalize_window_pid(window_pid),
                "search_plan": search_plan,
                "search_attempts": attempts,
                "selected_strategy": last_attempt.get("strategy"),
                "search_pattern": last_attempt.get("pattern"),
                "search_command": last_attempt.get("command"),
                "search_returncode": last_attempt.get("returncode"),
                "search_allowed": last_attempt.get("allowed"),
                "search_timed_out": last_attempt.get("timed_out"),
                "matched_count": int(last_attempt.get("matched_count", 0) or 0),
                "matched_window_ids": [],
            },
        }

    def _describe_windows(self, window_ids: list[str], dry_run: bool) -> list[dict[str, Any]]:
        if dry_run:
            return [{"window_id": item, "title": "(dry-run)", "title_lookup_ok": True} for item in window_ids]

        windows: list[dict[str, Any]] = []
        for window_id in window_ids:
            name_result = self.runner.run(
                ["xdotool", "getwindowname", str(window_id)],
                dry_run=False,
                timeout_seconds=10.0,
            )
            title = name_result.stdout.strip().splitlines()
            windows.append(
                {
                    "window_id": str(window_id),
                    "title": title[0] if title else "",
                    "title_lookup_ok": bool(
                        name_result.allowed and name_result.returncode == 0 and not name_result.timed_out
                    ),
                }
            )
        return windows

    def _get_window_geometry(self, window_id: str, dry_run: bool) -> dict[str, Any]:
        normalized_window_id = str(window_id).strip()
        if not normalized_window_id:
            return {
                "success": False,
                "summary": "window_id is required for geometry lookup.",
                "details": {},
            }

        if dry_run:
            return {
                "success": True,
                "summary": "Window geometry simulated (dry-run).",
                "details": {
                    "window_id": normalized_window_id,
                    "x": 0,
                    "y": 0,
                    "width": 0,
                    "height": 0,
                    "dry_run": True,
                },
            }

        geometry_result = self.runner.run(
            ["xdotool", "getwindowgeometry", "--shell", normalized_window_id],
            dry_run=False,
            timeout_seconds=10.0,
        )
        if not bool(geometry_result.allowed and geometry_result.returncode == 0 and not geometry_result.timed_out):
            return {
                "success": False,
                "summary": "Window geometry lookup failed.",
                "details": {
                    "window_id": normalized_window_id,
                    "returncode": geometry_result.returncode,
                    "allowed": geometry_result.allowed,
                    "timed_out": geometry_result.timed_out,
                    "stdout_excerpt": geometry_result.stdout.strip()[:500],
                    "stderr_excerpt": geometry_result.stderr.strip()[:500],
                },
            }

        parsed: dict[str, int] = {}
        for line in geometry_result.stdout.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key_norm = key.strip().lower()
            value_norm = value.strip()
            if key_norm in {"x", "y", "width", "height"}:
                try:
                    parsed[key_norm] = int(value_norm)
                except ValueError:
                    continue

        required = {"x", "y", "width", "height"}
        if not required.issubset(parsed.keys()):
            return {
                "success": False,
                "summary": "Window geometry output was incomplete.",
                "details": {
                    "window_id": normalized_window_id,
                    "parsed": parsed,
                    "stdout_excerpt": geometry_result.stdout.strip()[:500],
                },
            }

        return {
            "success": True,
            "summary": "Window geometry resolved.",
            "details": {
                "window_id": normalized_window_id,
                "x": int(parsed["x"]),
                "y": int(parsed["y"]),
                "width": int(parsed["width"]),
                "height": int(parsed["height"]),
            },
        }

    def _focus_window(
        self,
        window_title: str,
        window_class: str,
        window_pid: int | None,
        window_index: int,
        match_mode: str,
        dry_run: bool,
    ) -> dict[str, Any]:
        normalized_title = window_title.strip()
        normalized_class = window_class.strip()
        normalized_pid = self._normalize_window_pid(window_pid)
        try:
            safe_index = max(0, int(window_index))
        except (TypeError, ValueError):
            safe_index = 0
        normalized_mode = self._normalize_window_match_mode(match_mode)

        if not normalized_title and not normalized_class and normalized_pid is None:
            return {
                "success": False,
                "summary": "At least one selector is required: window_title, window_class, or window_pid.",
                "details": {},
            }

        if dry_run:
            return {
                "success": True,
                "summary": "Window focus simulated (dry-run).",
                "details": {
                    "window_title": normalized_title if normalized_title else None,
                    "window_class": normalized_class if normalized_class else None,
                    "window_pid": normalized_pid,
                    "window_index": safe_index,
                    "window_match_mode": normalized_mode,
                    "window_id": "dry-run-window",
                    "search_plan": self._build_window_search_plan(
                        window_title=normalized_title,
                        match_mode=normalized_mode,
                        window_class=normalized_class,
                        window_pid=normalized_pid,
                    ),
                    "matched_window_ids": [],
                    "dry_run": True,
                },
            }

        candidate_result = self._collect_window_candidates(
            window_title=normalized_title,
            window_class=normalized_class,
            window_pid=normalized_pid,
            match_mode=normalized_mode,
            max_candidates=MAX_WINDOW_SEARCH_CANDIDATES,
        )
        candidate_details = candidate_result.get("details", {})
        if not isinstance(candidate_details, dict):
            candidate_details = {}
        if not bool(candidate_result.get("success") is True):
            return {
                "success": False,
                "summary": str(candidate_result.get("summary", "No matching window found for provided selectors.")),
                "details": {
                    **candidate_details,
                    "window_title": normalized_title if normalized_title else None,
                    "window_class": normalized_class if normalized_class else None,
                    "window_pid": normalized_pid,
                    "window_index": safe_index,
                    "window_match_mode": normalized_mode,
                },
            }

        matched_window_ids_raw = candidate_details.get("matched_window_ids", [])
        matched_window_ids = [
            str(item)
            for item in matched_window_ids_raw
            if isinstance(item, str) and item.strip()
        ]
        if safe_index >= len(matched_window_ids):
            return {
                "success": False,
                "summary": "window_index is out of range for matched windows.",
                "details": {
                    "window_title": normalized_title if normalized_title else None,
                    "window_class": normalized_class if normalized_class else None,
                    "window_pid": normalized_pid,
                    "window_index": safe_index,
                    "window_match_mode": normalized_mode,
                    "matched_count": len(matched_window_ids),
                    "matched_window_ids": matched_window_ids[:10],
                    "search_plan": candidate_details.get("search_plan", []),
                },
            }

        selected_window_id = matched_window_ids[safe_index]
        activation_attempts: list[dict[str, Any]] = []
        active_window_id = ""
        activation_verified = False
        for attempt in range(1, 3):
            activate_result = self.runner.run(
                ["xdotool", "windowactivate", "--sync", selected_window_id],
                dry_run=False,
                timeout_seconds=30.0,
            )
            active_result = self.runner.run(
                ["xdotool", "getactivewindow"],
                dry_run=False,
                timeout_seconds=10.0,
            )
            active_window_lines = [line.strip() for line in active_result.stdout.splitlines() if line.strip()]
            active_window_id = active_window_lines[0] if active_window_lines else ""

            activate_success = bool(
                activate_result.allowed
                and activate_result.returncode == 0
                and not activate_result.timed_out
            )
            active_success = bool(
                active_result.allowed
                and active_result.returncode == 0
                and not active_result.timed_out
                and bool(active_window_id)
            )
            matched_active = bool(active_success and active_window_id == selected_window_id)
            activation_attempts.append(
                {
                    "attempt": attempt,
                    "activate_returncode": activate_result.returncode,
                    "activate_allowed": activate_result.allowed,
                    "activate_timed_out": activate_result.timed_out,
                    "activate_stdout_excerpt": activate_result.stdout.strip()[:200],
                    "activate_stderr_excerpt": activate_result.stderr.strip()[:200],
                    "active_window_id": active_window_id,
                    "active_returncode": active_result.returncode,
                    "active_allowed": active_result.allowed,
                    "active_timed_out": active_result.timed_out,
                    "active_stdout_excerpt": active_result.stdout.strip()[:200],
                    "active_stderr_excerpt": active_result.stderr.strip()[:200],
                    "active_match": matched_active,
                }
            )
            if activate_success and matched_active:
                activation_verified = True
                break

        if not activation_verified:
            return {
                "success": False,
                "summary": "Window activation failed or could not be verified.",
                "details": {
                    "window_title": normalized_title if normalized_title else None,
                    "window_class": normalized_class if normalized_class else None,
                    "window_pid": normalized_pid,
                    "window_index": safe_index,
                    "window_match_mode": normalized_mode,
                    "window_id": selected_window_id,
                    "matched_window_ids": matched_window_ids[:10],
                    "search_plan": candidate_details.get("search_plan", []),
                    "selected_strategy": candidate_details.get("selected_strategy"),
                    "activation_attempts": activation_attempts,
                    "active_window_id": active_window_id,
                },
            }

        matched_windows = self._describe_windows(matched_window_ids[:10], dry_run=False)
        return {
            "success": True,
            "summary": "Window focus completed.",
            "details": {
                "window_title": normalized_title if normalized_title else None,
                "window_class": normalized_class if normalized_class else None,
                "window_pid": normalized_pid,
                "window_index": safe_index,
                "window_match_mode": normalized_mode,
                "window_id": selected_window_id,
                "matched_count": len(matched_window_ids),
                "matched_window_ids": matched_window_ids[:10],
                "matched_windows": matched_windows,
                "selected_strategy": candidate_details.get("selected_strategy"),
                "search_plan": candidate_details.get("search_plan", []),
                "activation_attempts": activation_attempts,
                "active_window_id": active_window_id,
            },
        }

    def _launch_app(self, app_name: str, dry_run: bool) -> dict[str, Any]:
        normalized_query = self._normalize_app_query(app_name)
        if not normalized_query:
            return {
                "success": False,
                "summary": "Could not normalize app_name for launch.",
                "details": {"app_name": app_name},
            }

        candidates = self._discover_app_launch_candidates(
            app_name=app_name,
            normalized_query=normalized_query,
        )
        if not candidates:
            if dry_run:
                synthetic_command = self._candidate_command_names_from_label(app_name)
                fallback_command = [synthetic_command[0]] if synthetic_command else [normalized_query]
                return {
                    "success": True,
                    "summary": "Application launch simulated (dry-run).",
                    "details": {
                        "app_name": app_name,
                        "normalized_query": normalized_query,
                        "launched_command": fallback_command,
                        "source": "dry_run_synthetic",
                        "label": app_name,
                        "desktop_file": None,
                        "dry_run": True,
                        "attempts": [],
                    },
                }
            return {
                "success": False,
                "summary": "No launch candidate found for requested app.",
                "details": {
                    "app_name": app_name,
                    "normalized_query": normalized_query,
                    "candidate_count": 0,
                },
            }

        attempts: list[dict[str, Any]] = []
        for index, candidate in enumerate(candidates[:MAX_APP_LAUNCH_ATTEMPTS], start=1):
            command = [str(token) for token in candidate.get("command", []) if str(token).strip()]
            safe, safety_reason = self._is_safe_launch_command(command)
            attempt: dict[str, Any] = {
                "attempt": index,
                "source": str(candidate.get("source", "unknown")),
                "score": int(candidate.get("score", 0)),
                "label": str(candidate.get("label", "")),
                "desktop_file": candidate.get("desktop_file"),
                "command": command,
                "safe": safe,
            }
            if not safe:
                attempt["error"] = safety_reason
                attempts.append(attempt)
                continue

            spawn = self._spawn_launch_command(command=command, dry_run=dry_run)
            attempt.update(spawn)
            attempts.append(attempt)
            if bool(spawn.get("success") is True):
                return {
                    "success": True,
                    "summary": "Application launch command executed.",
                    "details": {
                        "app_name": app_name,
                        "normalized_query": normalized_query,
                        "launched_command": command,
                        "source": attempt["source"],
                        "label": attempt["label"],
                        "desktop_file": attempt.get("desktop_file"),
                        "dry_run": dry_run,
                        "attempts": attempts,
                    },
                }

        return {
            "success": False,
            "summary": "All launch candidates failed for requested app.",
            "details": {
                "app_name": app_name,
                "normalized_query": normalized_query,
                "candidate_count": len(candidates),
                "attempts": attempts,
            },
        }

    def _discover_app_launch_candidates(
        self,
        app_name: str,
        normalized_query: str,
    ) -> list[dict[str, Any]]:
        query_tokens = set(normalized_query.split())
        discovered: list[dict[str, Any]] = []
        seen_commands: set[tuple[str, ...]] = set()

        for directory in DESKTOP_APPLICATION_DIRS:
            if not directory.exists() or not directory.is_dir():
                continue
            for desktop_file in directory.glob("*.desktop"):
                parsed = self._parse_desktop_entry(desktop_file)
                if not parsed:
                    continue

                score = self._score_desktop_entry_candidate(
                    normalized_query=normalized_query,
                    query_tokens=query_tokens,
                    desktop_file=desktop_file,
                    parsed_entry=parsed,
                )
                if score <= 0:
                    continue

                command = self._desktop_exec_to_command(str(parsed.get("exec", "")))
                if not command:
                    continue
                key = tuple(command)
                if key in seen_commands:
                    continue
                seen_commands.add(key)
                discovered.append(
                    {
                        "source": "desktop_entry",
                        "score": score,
                        "label": str(parsed.get("name", desktop_file.stem)),
                        "desktop_file": str(desktop_file),
                        "command": command,
                    }
                )

        for command_name in self._candidate_command_names_from_label(app_name):
            resolved = shutil.which(command_name)
            if not resolved:
                continue
            command = [command_name]
            key = tuple(command)
            if key in seen_commands:
                continue
            seen_commands.add(key)
            base_score = 60 if command_name == app_name.strip().lower() else 50
            discovered.append(
                {
                    "source": "command_name",
                    "score": base_score,
                    "label": command_name,
                    "desktop_file": None,
                    "command": command,
                }
            )

        discovered.sort(
            key=lambda item: (
                -int(item.get("score", 0)),
                0 if item.get("source") == "command_name" else 1,
                str(item.get("label", "")),
            )
        )
        return discovered[:MAX_DESKTOP_ENTRY_CANDIDATES]

    def _parse_desktop_entry(self, desktop_file: Path) -> dict[str, Any]:
        try:
            content = desktop_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return {}

        in_desktop_entry = False
        parsed: dict[str, Any] = {"localized_names": []}
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                in_desktop_entry = line.lower() == "[desktop entry]"
                continue
            if not in_desktop_entry or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key_norm = key.strip()
            value_norm = value.strip()
            if key_norm == "Name":
                parsed["name"] = value_norm
            elif key_norm.startswith("Name["):
                localized = parsed.get("localized_names", [])
                if isinstance(localized, list):
                    localized.append(value_norm)
            elif key_norm == "GenericName":
                parsed["generic_name"] = value_norm
            elif key_norm == "Comment":
                parsed["comment"] = value_norm
            elif key_norm == "Exec":
                parsed["exec"] = value_norm
            elif key_norm == "Type":
                parsed["type"] = value_norm
            elif key_norm == "Hidden":
                parsed["hidden"] = value_norm
            elif key_norm == "NoDisplay":
                parsed["no_display"] = value_norm

        entry_type = str(parsed.get("type", "Application")).strip().lower()
        hidden = str(parsed.get("hidden", "")).strip().lower() in {"1", "true", "yes"}
        if entry_type != "application" or hidden:
            return {}
        if not str(parsed.get("exec", "")).strip():
            return {}
        return parsed

    def _score_desktop_entry_candidate(
        self,
        normalized_query: str,
        query_tokens: set[str],
        desktop_file: Path,
        parsed_entry: dict[str, Any],
    ) -> int:
        best_score = 0
        labels: list[str] = [
            str(parsed_entry.get("name", "")),
            str(parsed_entry.get("generic_name", "")),
            str(parsed_entry.get("comment", "")),
            desktop_file.stem,
        ]
        localized_names = parsed_entry.get("localized_names", [])
        if isinstance(localized_names, list):
            labels.extend(str(item) for item in localized_names if isinstance(item, str))

        for label in labels:
            normalized_label = self._normalize_app_query(label)
            if not normalized_label:
                continue
            if normalized_label == normalized_query:
                best_score = max(best_score, 130)
                continue
            if normalized_query in normalized_label:
                best_score = max(best_score, 105)
                continue
            if normalized_label in normalized_query:
                best_score = max(best_score, 75)
                continue
            label_tokens = set(normalized_label.split())
            overlap = len(query_tokens & label_tokens)
            if overlap > 0:
                best_score = max(best_score, 42 + overlap * 12)

        stem_normalized = self._normalize_app_query(desktop_file.stem)
        if stem_normalized == normalized_query:
            best_score = max(best_score, 125)
        elif stem_normalized.startswith(normalized_query):
            best_score = max(best_score, 92)
        return best_score

    def _desktop_exec_to_command(self, exec_value: str) -> list[str]:
        normalized = DESKTOP_EXEC_PLACEHOLDER_PATTERN.sub("", exec_value).replace("%%", "%").strip()
        normalized = re.sub(r"\s+", " ", normalized)
        if not normalized:
            return []
        try:
            command = [token for token in shlex.split(normalized, posix=True) if token.strip()]
        except ValueError:
            return []
        return command

    def _normalize_app_query(self, value: str) -> str:
        lowered = value.strip().lower()
        lowered = lowered.replace("&", " and ")
        lowered = re.sub(r"[\"'`“”‘’]", "", lowered)
        lowered = re.sub(r"[^\wぁ-んァ-ン一-龥]+", " ", lowered)
        lowered = lowered.replace("_", " ")
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    def _candidate_command_names_from_label(self, app_name: str) -> list[str]:
        cleaned = app_name.strip()
        lowered = cleaned.lower()
        candidates: set[str] = set()
        if re.fullmatch(r"[A-Za-z0-9._+-]+", cleaned):
            candidates.add(cleaned)
        if re.fullmatch(r"[A-Za-z0-9._+-]+", lowered):
            candidates.add(lowered)

        ascii_tokens = re.sub(r"[^a-z0-9]+", " ", lowered).strip().split()
        if ascii_tokens:
            candidates.add("-".join(ascii_tokens))
            candidates.add("_".join(ascii_tokens))
            candidates.add("".join(ascii_tokens))
            candidates.add(ascii_tokens[0])
        return sorted(item for item in candidates if item)

    def _launch_executable_name(self, command: list[str]) -> str:
        if not command:
            return ""
        if command[0] != "env":
            return Path(command[0]).name

        index = 1
        while index < len(command):
            token = command[index]
            if token.startswith("-"):
                index += 1
                continue
            if "=" in token and not token.startswith("/"):
                index += 1
                continue
            return Path(token).name
        return ""

    def _is_safe_launch_command(self, command: list[str]) -> tuple[bool, str]:
        if not command:
            return False, "launch command is empty"

        for token in command:
            if any(marker in token for marker in ("&&", "||", ";", "`")):
                return False, "launch command contains unsafe shell control markers"

        executable = self._launch_executable_name(command).strip().lower().rstrip(".,;:")
        if not executable:
            return False, "launch command executable could not be resolved"
        if executable in BLOCKED_TOKENS:
            return False, f"launch executable '{executable}' is blocked"
        if executable in UNSAFE_LAUNCH_EXECUTABLES:
            return False, f"launch executable '{executable}' is not allowed for app launching"
        return True, ""

    def _spawn_launch_command(self, command: list[str], dry_run: bool) -> dict[str, Any]:
        if dry_run:
            return {"success": True, "dry_run": True, "pid": None, "returncode": 0}

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            return {"success": False, "dry_run": False, "error": str(error)}

        time.sleep(0.15)
        returncode = process.poll()
        if returncode not in {None, 0}:
            return {
                "success": False,
                "dry_run": False,
                "pid": process.pid,
                "returncode": int(returncode),
                "error": "process exited immediately with non-zero status",
            }
        return {
            "success": True,
            "dry_run": False,
            "pid": process.pid,
            "returncode": 0 if returncode is None else int(returncode),
        }

    def _safe_data_path(self, raw_path: Any) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("path must be a non-empty string")

        candidate = Path(raw_path)
        if candidate.is_absolute():
            raise ValueError("absolute paths are not allowed")
        if ".." in candidate.parts:
            raise ValueError("path traversal is not allowed")
        if not candidate.parts or candidate.parts[0] != "data":
            raise ValueError("path must be under data/")

        resolved = (self.workspace_root / candidate).resolve()
        data_root = (self.workspace_root / "data").resolve()
        if not str(resolved).startswith(str(data_root)):
            raise ValueError("resolved path must remain under data/")
        return resolved
