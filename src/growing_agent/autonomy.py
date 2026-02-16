from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid

from .i18n import DEFAULT_LANGUAGE, normalize_language
from .memory import MemoryStore
from .tools.runner import CommandRunner

SUPPORTED_AUTONOMY_TASKS = ("command", "write_note", "analyze_state")
DEFAULT_AUTONOMY_ALLOWED_COMMANDS = ("python3", "python", "pytest", "echo")


def build_default_autonomy_state() -> dict[str, Any]:
    return {
        "queue": [],
        "completed": [],
        "learning": {
            "task_type_stats": {},
            "improvement_backlog": [],
        },
    }


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    ) -> None:
        if max_completed < 1:
            raise ValueError("max_completed must be >= 1")
        if max_improvements < 1:
            raise ValueError("max_improvements must be >= 1")
        self.memory = memory
        self.runner = runner
        self.language = normalize_language(language or DEFAULT_LANGUAGE)
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.max_completed = max_completed
        self.max_improvements = max_improvements

    def enqueue(
        self,
        task_type: str,
        title: str,
        payload: dict[str, Any] | None = None,
        priority: int = 5,
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

        state = self.memory.read_state()
        autonomy = self._ensure_autonomy_state(state)

        task = {
            "task_id": uuid.uuid4().hex[:12],
            "task_type": normalized_task_type,
            "title": title.strip(),
            "payload": payload,
            "priority": safe_priority,
            "attempts": 0,
            "created_at_utc": _utcnow(),
        }
        autonomy["queue"].append(task)
        state["language"] = normalize_language(self.language)
        self.memory.write_state(state)
        return task

    def run(self, cycles: int = 1, dry_run: bool = False) -> dict[str, Any]:
        if cycles < 1:
            raise ValueError("cycles must be >= 1")

        state = self.memory.read_state()
        autonomy = self._ensure_autonomy_state(state)
        state["language"] = normalize_language(self.language)

        executed: list[dict[str, Any]] = []
        for _ in range(cycles):
            task = self._select_next_task(autonomy)
            if task is None:
                break

            result = self._execute_task(task, state, dry_run=dry_run)
            self._update_learning(autonomy, task, result)
            self._record_completion(autonomy, task, result)
            self._maybe_enqueue_follow_up(autonomy, task, result)
            executed.append(result)

        summary = self._build_summary(autonomy, executed, dry_run)
        autonomy["last_run"] = summary
        state["autonomy"] = autonomy
        self.memory.write_state(state)
        return {"state": state, "executed": executed, "summary": summary}

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
        state["autonomy"] = normalized
        return normalized

    def _select_next_task(self, autonomy: dict[str, Any]) -> dict[str, Any] | None:
        queue = autonomy["queue"]
        if not queue:
            return None

        learning = autonomy.get("learning", {})
        stats = learning.get("task_type_stats", {})
        if not isinstance(stats, dict):
            stats = {}

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

            return priority + avg_reward - (0.1 * attempts)

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
    ) -> dict[str, Any]:
        task_type = str(task.get("task_type", ""))
        if task_type == "command":
            return self._execute_command_task(task, dry_run=dry_run)
        if task_type == "write_note":
            return self._execute_write_note_task(task, dry_run=dry_run)
        if task_type == "analyze_state":
            return self._execute_analyze_state_task(task, state=state, dry_run=dry_run)

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
        for queued in queue:
            if not isinstance(queued, dict):
                continue
            if str(queued.get("task_type")) != "analyze_state":
                continue
            payload = queued.get("payload", {})
            if isinstance(payload, dict) and str(payload.get("source_task_id")) == source_task_id:
                return

        follow_up = {
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
        queue.append(follow_up)

    def _build_summary(
        self,
        autonomy: dict[str, Any],
        executed: list[dict[str, Any]],
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
        return {
            "timestamp_utc": _utcnow(),
            "executed_count": len(executed),
            "success_count": success_count,
            "failure_count": failure_count,
            "average_reward": avg_reward,
            "queue_size": queue_size,
            "dry_run": dry_run,
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
