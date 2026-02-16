"""Numeric score derived from pytest result."""

import re


def score_from_pytest_output(stdout: str, stderr: str) -> float:
    """
    Parse pytest output and return a numeric score.
    Score = passed / (passed + failed + error) if any tests, else 0.0
    """
    text = stdout + "\n" + stderr
    # Match "X passed" or "X failed" or "X error"
    passed = _extract_count(text, r"(\d+)\s+passed")
    failed = _extract_count(text, r"(\d+)\s+failed")
    error = _extract_count(text, r"(\d+)\s+error")
    total = passed + failed + error
    if total == 0:
        return 0.0
    return passed / total


def _extract_count(text: str, pattern: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0
