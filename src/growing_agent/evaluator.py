from __future__ import annotations

import re

from .tools.runner import RunResult


SUMMARY_RE = re.compile(
    r"(?P<count>\d+)\s+(?P<label>passed|failed|error|errors)",
    re.IGNORECASE,
)


def score_from_pytest_result(result: RunResult) -> float:
    """Return a numeric score in [0, 1] from pytest output."""

    text = f"{result.stdout}\n{result.stderr}"
    passed = 0
    failed_or_error = 0

    for match in SUMMARY_RE.finditer(text):
        count = int(match.group("count"))
        label = match.group("label").lower()
        if label == "passed":
            passed += count
        else:
            failed_or_error += count

    total = passed + failed_or_error
    if total == 0:
        return 1.0 if result.returncode == 0 else 0.0

    return round(passed / total, 3)
