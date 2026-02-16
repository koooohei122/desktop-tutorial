from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import AgentConfig
from .evaluator import evaluate_pytest_result
from .memory import MemoryStore
from .tools.runner import CommandRunner, RunResult


class GrowingAgentOrchestrator:
    """Minimal observe -> plan -> act -> evaluate -> update loop."""

    def __init__(
        self,
        memory: MemoryStore | None = None,
        runner: CommandRunner | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        self.config = config or AgentConfig()
        self.memory = memory or MemoryStore()
        command_token = self.config.command[0]
        allowed = {command_token, Path(command_token).name}
        self.runner = runner or CommandRunner(allowed_commands=allowed)

    def observe(self) -> dict[str, Any]:
        return self.memory.read_state()

    def plan(self, observation: dict[str, Any]) -> dict[str, Any]:
        raw_iteration = observation.get("iteration", 0)
        try:
            next_iteration = int(raw_iteration) + 1
        except (TypeError, ValueError):
            next_iteration = 1
        return {
            "iteration": next_iteration,
            "command": list(self.config.command),
        }

    def act(self, plan: dict[str, Any], dry_run: bool) -> RunResult:
        command = plan["command"]
        return self.runner.run(
            command,
            dry_run=dry_run,
            timeout_seconds=self.config.timeout_seconds,
        )

    def evaluate(self, result: RunResult) -> dict[str, float | int | bool]:
        return evaluate_pytest_result(result)

    def update(
        self,
        observation: dict[str, Any],
        plan: dict[str, Any],
        result: RunResult,
        evaluation: dict[str, float | int | bool],
    ) -> dict[str, Any]:
        raw_history = observation.get("history", [])
        history = list(raw_history) if isinstance(raw_history, list) else []
        score = float(evaluation["score"])
        history.append(
            {
                "iteration": plan["iteration"],
                "command": result.command,
                "returncode": result.returncode,
                "score": score,
                "passed": int(evaluation["passed"]),
                "failed": int(evaluation["failed"]),
                "errors": int(evaluation["errors"]),
                "skipped": int(evaluation["skipped"]),
                "xfailed": int(evaluation["xfailed"]),
                "xpassed": int(evaluation["xpassed"]),
                "dry_run": result.dry_run,
                "allowed": result.allowed,
                "timed_out": result.timed_out,
                "duration_seconds": result.duration_seconds,
            }
        )
        if len(history) > self.config.max_history:
            history = history[-self.config.max_history :]

        scores = [
            float(item["score"])
            for item in history
            if isinstance(item, dict) and isinstance(item.get("score"), (int, float))
        ]
        average_score = round(sum(scores) / len(scores), 3) if scores else 0.0
        best_score = round(max(scores), 3) if scores else 0.0

        new_state: dict[str, Any] = {
            "iteration": plan["iteration"],
            "last_score": score,
            "history": history,
            "metrics": {
                "iterations_recorded": len(history),
                "average_score": average_score,
                "best_score": best_score,
            },
        }
        self.memory.write_state(new_state)
        return new_state

    def run(self, iterations: int | None = None, dry_run: bool | None = None) -> dict[str, Any]:
        loop_iterations = iterations if iterations is not None else self.config.iterations
        if loop_iterations < 1:
            raise ValueError("iterations must be >= 1")
        runtime_dry_run = self.config.dry_run if dry_run is None else dry_run

        state = self.observe()
        for _ in range(loop_iterations):
            observation = state
            plan = self.plan(observation)
            result = self.act(plan, dry_run=runtime_dry_run)
            evaluation = self.evaluate(result)
            state = self.update(observation, plan, result, evaluation)

            score = float(evaluation["score"])
            if self.config.stop_on_target and score >= self.config.target_score:
                state["stop_reason"] = "target_score_reached"
                self.memory.write_state(state)
                break
            if self.config.halt_on_error and result.returncode != 0:
                state["stop_reason"] = "command_error"
                self.memory.write_state(state)
                break
        return state
