"""Evaluate test results and produce a numeric score."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from growing_agent.tools.runner import RunResult

logger = logging.getLogger(__name__)

# Matches pytest summary line, e.g. "3 passed, 1 failed"
_PYTEST_SUMMARY_RE = re.compile(
    r"(?P<passed>\d+) passed"
    r"(?:,\s*(?P<failed>\d+) failed)?"
    r"(?:,\s*(?P<errors>\d+) error)?"
)


@dataclass
class EvalResult:
    """Numeric score and metadata from an evaluation."""

    passed: int
    failed: int
    errors: int
    score: float
    raw_output: str


def _parse_pytest_output(output: str) -> tuple[int, int, int]:
    """Extract (passed, failed, errors) from pytest output text."""
    match = _PYTEST_SUMMARY_RE.search(output)
    if not match:
        return 0, 0, 0
    passed = int(match.group("passed") or 0)
    failed = int(match.group("failed") or 0)
    errors = int(match.group("errors") or 0)
    return passed, failed, errors


def score_from_pytest(result: RunResult) -> EvalResult:
    """Compute a 0-100 score from a pytest ``RunResult``.

    Score formula::

        score = (passed / total) * 100   (0 when total == 0)
    """
    combined = result.stdout + "\n" + result.stderr
    passed, failed, errors = _parse_pytest_output(combined)
    total = passed + failed + errors
    score = (passed / total * 100.0) if total > 0 else 0.0
    logger.info(
        "Evaluation: passed=%d failed=%d errors=%d → score=%.1f",
        passed,
        failed,
        errors,
        score,
    )
    return EvalResult(
        passed=passed,
        failed=failed,
        errors=errors,
        score=round(score, 2),
        raw_output=combined,
    )


def score_from_dry_run() -> EvalResult:
    """Return a neutral evaluation for dry-run mode."""
    return EvalResult(
        passed=0,
        failed=0,
        errors=0,
        score=0.0,
        raw_output="(dry-run – no tests executed)",
    )
