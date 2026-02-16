from __future__ import annotations

import re

from .tools.runner import RunResult


SUMMARY_RE = re.compile(
    r"(?P<count>\d+)\s+(?P<label>passed|failed|error|errors|skipped|xfailed|xpassed)",
    re.IGNORECASE,
)


def parse_pytest_summary(output_text: str) -> dict[str, int]:
    counts = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
    }

    for match in SUMMARY_RE.finditer(output_text):
        count = int(match.group("count"))
        label = match.group("label").lower()
        if label in {"error", "errors"}:
            counts["errors"] += count
        else:
            counts[label] += count
    return counts


def evaluate_pytest_result(result: RunResult) -> dict[str, float | int | bool]:
    """Build score and summary fields from a pytest-like result."""

    text = f"{result.stdout}\n{result.stderr}"
    counts = parse_pytest_summary(text)

    passed = counts["passed"]
    failed = counts["failed"]
    errors = counts["errors"]
    skipped = counts["skipped"]
    xfailed = counts["xfailed"]
    xpassed = counts["xpassed"]

    weighted_total = (
        passed
        + failed
        + errors
        + xpassed
        + (0.25 * skipped)
        + (0.1 * xfailed)
    )
    weighted_positive = passed + (0.05 * xfailed)

    if weighted_total == 0:
        score = 1.0 if result.returncode == 0 else 0.0
    else:
        score = weighted_positive / weighted_total
        if result.returncode != 0 and (failed + errors) == 0:
            score = min(score, 0.5)

    return {
        **counts,
        "score": round(score, 3),
        "success": result.returncode == 0,
    }


def score_from_pytest_result(result: RunResult) -> float:
    """Return a numeric score in [0, 1] from pytest output."""
    details = evaluate_pytest_result(result)
    return float(details["score"])
