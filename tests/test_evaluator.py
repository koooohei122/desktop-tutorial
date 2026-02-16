from __future__ import annotations

import unittest

from growing_agent.evaluator import evaluate_pytest_result, parse_pytest_summary, score_from_pytest_result
from growing_agent.tools.runner import RunResult


class TestEvaluator(unittest.TestCase):
    def build_result(self, stdout: str, returncode: int = 0) -> RunResult:
        return RunResult(
            command=["pytest", "-q"],
            returncode=returncode,
            stdout=stdout,
            stderr="",
            allowed=True,
            dry_run=False,
            duration_seconds=0.1,
            timed_out=False,
        )

    def test_all_pass_score(self) -> None:
        result = self.build_result("4 passed in 0.10s", returncode=0)
        self.assertEqual(score_from_pytest_result(result), 1.0)

    def test_failures_reduce_score(self) -> None:
        result = self.build_result("6 passed, 2 failed in 0.30s", returncode=1)
        self.assertEqual(score_from_pytest_result(result), 0.75)

    def test_extended_labels_are_parsed(self) -> None:
        summary = parse_pytest_summary("3 passed, 1 skipped, 2 xfailed, 1 xpassed, 1 error")
        self.assertEqual(summary["passed"], 3)
        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(summary["xfailed"], 2)
        self.assertEqual(summary["xpassed"], 1)
        self.assertEqual(summary["errors"], 1)

    def test_nonzero_without_summary_penalized(self) -> None:
        result = self.build_result("", returncode=2)
        details = evaluate_pytest_result(result)
        self.assertEqual(details["score"], 0.0)
        self.assertFalse(details["success"])


if __name__ == "__main__":
    unittest.main()
