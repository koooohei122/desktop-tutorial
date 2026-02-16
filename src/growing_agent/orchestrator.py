"""Orchestrator: observe -> plan -> act -> evaluate -> update loop."""

import sys
from pathlib import Path

from .memory import read_state, write_state
from .tools.runner import run_and_log
from .evaluator import score_from_pytest_output


def observe(state: dict) -> dict:
    """Observe current state and context."""
    return {"observed": state.copy(), "iteration": state.get("iteration", 0)}


def plan(observed: dict) -> dict:
    """Plan next action based on observation."""
    iteration = observed.get("iteration", 0)
    return {"action": "run_pytest", "iteration": iteration}


def act(plan_result: dict, cwd: Path, dry_run: bool, log_path: Path | None) -> dict:
    """Execute the planned action."""
    if dry_run:
        return {"dry_run": True, "action": plan_result.get("action", "")}
    action = plan_result.get("action", "run_pytest")
    if action == "run_pytest":
        code, out, err = run_and_log(
            [sys.executable, "-m", "pytest", "-v", "--tb=short"],
            cwd=cwd,
            log_path=log_path,
        )
        return {"exit_code": code, "stdout": out, "stderr": err}
    return {"exit_code": 0, "stdout": "", "stderr": ""}


def evaluate(act_result: dict) -> float:
    """Evaluate action result and return numeric score."""
    if act_result.get("dry_run"):
        return 0.0
    return score_from_pytest_output(
        act_result.get("stdout", ""),
        act_result.get("stderr", ""),
    )


def update(state: dict, observed: dict, plan_result: dict, act_result: dict, score: float) -> dict:
    """Update state with results."""
    iteration = state.get("iteration", 0)
    new_state = {
        **state,
        "iteration": iteration + 1,
        "last_score": score,
        "last_action": plan_result.get("action", ""),
    }
    if "scores" not in new_state:
        new_state["scores"] = []
    new_state["scores"].append(score)
    return new_state


def run_loop(iterations: int, cwd: Path | None = None, dry_run: bool = False) -> dict:
    """
    Run observe -> plan -> act -> evaluate -> update for `iterations` times.
    """
    cwd = cwd or Path.cwd()
    log_path = cwd / "data" / "runner.log"
    state = read_state(cwd)
    state["iteration"] = 0

    for i in range(iterations):
        observed = observe(state)
        plan_result = plan(observed)
        act_result = act(plan_result, cwd, dry_run, log_path)
        score = evaluate(act_result)
        state = update(state, observed, plan_result, act_result, score)
        write_state(state, cwd)

    return state
