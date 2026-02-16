from __future__ import annotations

from typing import Any

from .evaluator import score_from_pytest_result
from .memory import MemoryStore
from .tools.runner import CommandRunner, RunResult


class GrowingAgentOrchestrator:
    """Minimal observe -> plan -> act -> evaluate -> update loop."""

    def __init__(
        self,
        memory: MemoryStore | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        self.memory = memory or MemoryStore()
        self.runner = runner or CommandRunner(allowed_commands={"pytest"})

    def observe(self) -> dict[str, Any]:
        return self.memory.read_state()

    def plan(self, observation: dict[str, Any]) -> dict[str, Any]:
        next_iteration = int(observation.get("iteration", 0)) + 1
        return {
            "iteration": next_iteration,
            "command": ["pytest", "-q"],
        }

    def act(self, plan: dict[str, Any], dry_run: bool) -> RunResult:
        command = plan["command"]
        return self.runner.run(command, dry_run=dry_run)

    def evaluate(self, result: RunResult) -> float:
        return score_from_pytest_result(result)

    def update(
        self,
        observation: dict[str, Any],
        plan: dict[str, Any],
        result: RunResult,
        score: float,
    ) -> dict[str, Any]:
        history = list(observation.get("history", []))
        history.append(
            {
                "iteration": plan["iteration"],
                "command": result.command,
                "returncode": result.returncode,
                "score": score,
                "dry_run": result.dry_run,
            }
        )

        new_state: dict[str, Any] = {
            "iteration": plan["iteration"],
            "last_score": score,
            "history": history,
        }
        self.memory.write_state(new_state)
        return new_state

    def run(self, iterations: int, dry_run: bool = False) -> dict[str, Any]:
        if iterations < 1:
            raise ValueError("iterations must be >= 1")

        state = self.observe()
        for _ in range(iterations):
            observation = state
            plan = self.plan(observation)
            result = self.act(plan, dry_run=dry_run)
            score = self.evaluate(result)
            state = self.update(observation, plan, result, score)
        return state
