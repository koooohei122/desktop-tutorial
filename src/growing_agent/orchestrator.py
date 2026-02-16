"""Core orchestration loop: observe → plan → act → evaluate → update."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from growing_agent.evaluator import EvalResult, score_from_dry_run, score_from_pytest
from growing_agent.memory import read_state, write_state
from growing_agent.tools.runner import run_command

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual phases
# ---------------------------------------------------------------------------

def observe(state: dict[str, Any]) -> dict[str, Any]:
    """Gather observations about the current environment.

    For now we simply record the current iteration counter and score.
    """
    obs: dict[str, Any] = {
        "iteration": state.get("iteration", 0),
        "current_score": state.get("score", 0.0),
    }
    logger.info("Observe: %s", obs)
    return obs


def plan(observation: dict[str, Any]) -> list[str]:
    """Decide what commands to run next.

    The default strategy is to run pytest to measure the project health.
    """
    commands = ["python3 -m pytest --tb=short -q"]
    logger.info("Plan: %s", commands)
    return commands


def act(
    commands: list[str],
    *,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Execute the planned commands and return a list of result dicts."""
    results: list[dict[str, Any]] = []
    for cmd in commands:
        res = run_command(cmd, dry_run=dry_run)
        results.append(
            {
                "command": res.command,
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "blocked": res.blocked,
                "dry_run": res.dry_run,
                "logs": res.logs,
            }
        )
    return results


def evaluate(
    act_results: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> EvalResult:
    """Score the most recent action results."""
    if dry_run:
        return score_from_dry_run()

    from growing_agent.tools.runner import RunResult

    for r in act_results:
        if "pytest" in r.get("command", ""):
            result = RunResult(
                command=r["command"],
                returncode=r["returncode"],
                stdout=r["stdout"],
                stderr=r["stderr"],
                blocked=r["blocked"],
                dry_run=r["dry_run"],
                logs=r["logs"],
            )
            return score_from_pytest(result)

    return score_from_dry_run()


def update(
    state: dict[str, Any],
    eval_result: EvalResult,
    act_results: list[dict[str, Any]],
    state_path: Path | None = None,
) -> dict[str, Any]:
    """Persist results into state and write to disk."""
    state["iteration"] = state.get("iteration", 0) + 1
    state["score"] = eval_result.score
    state["history"].append(
        {
            "iteration": state["iteration"],
            "score": eval_result.score,
            "passed": eval_result.passed,
            "failed": eval_result.failed,
            "errors": eval_result.errors,
            "actions": [r["command"] for r in act_results],
        }
    )
    write_state(state, state_path)
    logger.info(
        "Update: iteration=%d score=%.1f",
        state["iteration"],
        state["score"],
    )
    return state


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_loop(
    iterations: int = 1,
    dry_run: bool = False,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """Execute the full observe→plan→act→evaluate→update loop.

    Parameters
    ----------
    iterations:
        How many full cycles to run.
    dry_run:
        Skip actual command execution when ``True``.
    state_path:
        Override the default ``data/state.json`` location.
    """
    state = read_state(state_path)
    logger.info(
        "Starting orchestrator – %d iteration(s), dry_run=%s",
        iterations,
        dry_run,
    )

    for i in range(iterations):
        logger.info("──── Iteration %d/%d ────", i + 1, iterations)

        obs = observe(state)
        commands = plan(obs)
        results = act(commands, dry_run=dry_run)
        eval_result = evaluate(results, dry_run=dry_run)
        state = update(state, eval_result, results, state_path)

    logger.info("Orchestrator finished. Final score: %.1f", state["score"])
    return state
