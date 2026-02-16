from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from growing_agent.evaluator import score_from_pytest
from growing_agent.memory import StateStore
from growing_agent.tools.runner import AllowedCommandRunner, RunResult


def _truncate(s: str, limit: int = 2000) -> str:
    if len(s) <= limit:
        return s
    return s[:limit] + "\n...<truncated>...\n"


@dataclass(frozen=True)
class Plan:
    commands: list[list[str]]


class Orchestrator:
    """
    Minimal loop: observe -> plan -> act -> evaluate -> update
    """

    def __init__(self, *, store: StateStore | None = None, runner: AllowedCommandRunner | None = None) -> None:
        self.store = store or StateStore()
        python_name = Path(sys.executable).name
        self.runner = runner or AllowedCommandRunner(allowed_commands=(python_name, "pytest"))
        self.python_executable = sys.executable

    def observe(self, state: dict[str, Any], iteration: int) -> dict[str, Any]:
        return {
            "iteration": iteration,
            "last_score": state.get("last_score"),
            "history_len": len(state.get("history", [])),
        }

    def plan(self, observation: dict[str, Any]) -> Plan:
        # Minimal plan: run pytest quietly (via current interpreter).
        return Plan(commands=[[self.python_executable, "-m", "pytest", "-q"]])

    def act(self, plan: Plan, *, dry_run: bool) -> list[RunResult]:
        results: list[RunResult] = []
        for argv in plan.commands:
            results.append(self.runner.run(argv, dry_run=dry_run))
        return results

    def evaluate(self, results: list[RunResult]) -> float:
        if not results:
            return 0.0
        # We assume the last command is pytest.
        return score_from_pytest(results[-1])

    def update(
        self,
        state: dict[str, Any],
        observation: dict[str, Any],
        plan: Plan,
        results: list[RunResult],
        score: float,
        *,
        dry_run: bool,
    ) -> dict[str, Any]:
        record = {
            "iteration": observation.get("iteration"),
            "dry_run": dry_run,
            "plan": {"commands": [r.command_str() for r in results] if results else [*map(" ".join, plan.commands)]},
            "results": [
                {
                    "argv": r.argv,
                    "returncode": r.returncode,
                    "duration_ms": r.duration_ms,
                    "stdout": _truncate(r.stdout),
                    "stderr": _truncate(r.stderr),
                }
                for r in results
            ],
            "score": score,
        }

        state = dict(state)
        hist = list(state.get("history", []))
        hist.append(record)
        state["history"] = hist
        state["last_score"] = score
        return state

    def run(self, *, iterations: int, dry_run: bool = False) -> None:
        if iterations < 1:
            return

        state = self.store.load()

        for i in range(iterations):
            obs = self.observe(state, i)
            plan = self.plan(obs)
            results = self.act(plan, dry_run=dry_run)
            score = self.evaluate(results)
            state = self.update(state, obs, plan, results, score, dry_run=dry_run)
            self.store.save(state)

            cmd_list = [r.command_str() for r in results] if results else [" ".join(cmd) for cmd in plan.commands]
            print(f"[growing_agent] iteration={i} dry_run={dry_run} commands={cmd_list} score={score}")

