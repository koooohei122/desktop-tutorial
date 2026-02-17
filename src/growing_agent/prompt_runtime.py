from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
import uuid

from .autonomy import AutonomousWorker


@dataclass(frozen=True)
class RuntimeStep:
    task_type: str
    title: str
    payload: dict[str, Any]
    continue_on_failure: bool = True


class RuntimeAdapter(Protocol):
    def execute_step(self, step: RuntimeStep, dry_run: bool) -> dict[str, Any]:
        ...


class MockRuntimeAdapter:
    """Deterministic runtime for fast planner tests."""

    def __init__(
        self,
        responses: dict[str, dict[str, Any]] | None = None,
        default_success: bool = True,
    ) -> None:
        self.responses = responses or {}
        self.default_success = bool(default_success)

    def execute_step(self, step: RuntimeStep, dry_run: bool) -> dict[str, Any]:
        action = str(step.payload.get("action", "")).strip()
        key = f"{step.task_type}:{action}" if action else step.task_type
        preset = self.responses.get(key)
        if isinstance(preset, dict):
            response = dict(preset)
        else:
            response = {
                "success": self.default_success,
                "reward": 1.0 if self.default_success else 0.0,
                "summary": "Mock runtime executed step.",
                "details": {"task_type": step.task_type, "payload": step.payload, "dry_run": dry_run},
            }
        response.setdefault("task_type", step.task_type)
        response.setdefault("title", step.title)
        return response


class AutonomousWorkerRuntimeAdapter:
    """Runtime backed by AutonomousWorker task execution."""

    def __init__(self, worker: AutonomousWorker) -> None:
        self.worker = worker

    def execute_step(self, step: RuntimeStep, dry_run: bool) -> dict[str, Any]:
        task = {
            "task_id": uuid.uuid4().hex[:12],
            "task_type": step.task_type,
            "title": step.title,
            "payload": step.payload,
            "priority": 6,
            "attempts": 0,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        state = self.worker.memory.read_state()
        return self.worker._execute_task(task=task, state=state, dry_run=dry_run, depth=0)


def execute_steps(steps: list[RuntimeStep], runtime: RuntimeAdapter, dry_run: bool) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    overall_success = True
    for index, step in enumerate(steps, start=1):
        result = runtime.execute_step(step=step, dry_run=dry_run)
        result["step_index"] = index
        results.append(result)
        if not bool(result.get("success") is True):
            overall_success = False
            if not step.continue_on_failure:
                break

    return {
        "overall_success": overall_success,
        "executed_steps": len(results),
        "step_results": results,
    }
