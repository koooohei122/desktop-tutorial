from __future__ import annotations

import re

from growing_agent.tools.runner import RunResult


_COUNT_RE = re.compile(r"(?P<n>\d+)\s+(?P<kind>passed|failed|error|errors)\b")


def score_from_pytest(result: RunResult) -> float:
    """
    Compute a numeric score from a pytest invocation result.

    - If tests all pass: 1.0
    - If some fail: passed / (passed + failed + errors)
    - If no tests collected (pytest rc=5): 0.0
    - If dry-run or unknown: 0.0
    """

    if result.dry_run:
        return 0.0

    rc = result.returncode
    if rc is None:
        return 0.0
    if rc == 0:
        return 1.0
    if rc == 5:
        return 0.0

    text = (result.stdout or "") + "\n" + (result.stderr or "")
    passed = failed = errors = 0
    for m in _COUNT_RE.finditer(text):
        n = int(m.group("n"))
        kind = m.group("kind")
        if kind == "passed":
            passed += n
        elif kind == "failed":
            failed += n
        else:
            errors += n

    denom = passed + failed + errors
    if denom <= 0:
        return 0.0
    return passed / denom

