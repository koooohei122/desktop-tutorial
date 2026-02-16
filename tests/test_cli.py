from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class TestCli(unittest.TestCase):
    def run_cli(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        root = Path(__file__).resolve().parents[1]
        src_path = str(root / "src")
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = src_path if not existing else f"{src_path}:{existing}"
        return subprocess.run(
            [sys.executable, "-m", "growing_agent", *args],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_run_status_reset_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            run = self.run_cli(
                [
                    "run",
                    "--iterations",
                    "3",
                    "--dry-run",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                ]
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr)
            run_payload = json.loads(run.stdout)
            self.assertEqual(run_payload["iteration"], 3)

            status = self.run_cli(["status", "--state-path", str(state_path)])
            self.assertEqual(status.returncode, 0, msg=status.stderr)
            status_payload = json.loads(status.stdout)
            self.assertEqual(status_payload["iteration"], 3)

            reset = self.run_cli(["reset", "--state-path", str(state_path)])
            self.assertEqual(reset.returncode, 0, msg=reset.stderr)
            reset_payload = json.loads(reset.stdout)
            self.assertEqual(reset_payload["iteration"], 0)

    def test_run_with_stop_on_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            result = self.run_cli(
                [
                    "run",
                    "--iterations",
                    "15",
                    "--dry-run",
                    "--stop-on-target",
                    "--target-score",
                    "1.0",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                ]
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["stop_reason"], "target_score_reached")
            self.assertEqual(payload["iteration"], 1)

    def test_run_with_custom_command_supports_hyphen_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            result = self.run_cli(
                [
                    "run",
                    "--iterations",
                    "1",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                    "--command",
                    sys.executable,
                    "-c",
                    "print('ok')",
                ]
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["iteration"], 1)
            self.assertEqual(payload["history"][0]["command"][0], sys.executable)

    def test_language_can_be_switched(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            run = self.run_cli(
                [
                    "run",
                    "--iterations",
                    "1",
                    "--dry-run",
                    "--language",
                    "en",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                ]
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr)
            run_payload = json.loads(run.stdout)
            self.assertEqual(run_payload["language"], "en")
            self.assertEqual(run_payload["display_language"], "en")
            self.assertEqual(run_payload["message"], "Agent run completed.")

            status = self.run_cli(["status", "--state-path", str(state_path)])
            self.assertEqual(status.returncode, 0, msg=status.stderr)
            status_payload = json.loads(status.stdout)
            self.assertEqual(status_payload["language"], "en")
            self.assertEqual(status_payload["display_language"], "en")
            self.assertEqual(status_payload["message"], "Loaded current state.")

            reset = self.run_cli(
                [
                    "reset",
                    "--language",
                    "ja",
                    "--state-path",
                    str(state_path),
                ]
            )
            self.assertEqual(reset.returncode, 0, msg=reset.stderr)
            reset_payload = json.loads(reset.stdout)
            self.assertEqual(reset_payload["language"], "ja")
            self.assertEqual(reset_payload["display_language"], "ja")
            self.assertEqual(reset_payload["message"], "状態を初期化しました。")

    def test_status_retranslates_stop_message_for_requested_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            run = self.run_cli(
                [
                    "run",
                    "--iterations",
                    "5",
                    "--dry-run",
                    "--stop-on-target",
                    "--target-score",
                    "1.0",
                    "--language",
                    "ja",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                ]
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr)

            status = self.run_cli(
                [
                    "status",
                    "--language",
                    "en",
                    "--state-path",
                    str(state_path),
                ]
            )
            self.assertEqual(status.returncode, 0, msg=status.stderr)
            payload = json.loads(status.stdout)
            self.assertEqual(payload["display_language"], "en")
            self.assertEqual(
                payload["stop_message"],
                "Stopped because target score was reached.",
            )

    def test_set_language_persists_for_next_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            first_run = self.run_cli(
                [
                    "run",
                    "--iterations",
                    "1",
                    "--dry-run",
                    "--language",
                    "ja",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                ]
            )
            self.assertEqual(first_run.returncode, 0, msg=first_run.stderr)

            set_language = self.run_cli(
                [
                    "set-language",
                    "--language",
                    "EN",
                    "--state-path",
                    str(state_path),
                ]
            )
            self.assertEqual(set_language.returncode, 0, msg=set_language.stderr)
            set_payload = json.loads(set_language.stdout)
            self.assertEqual(set_payload["language"], "en")
            self.assertEqual(set_payload["message"], "Language preference updated.")

            second_run = self.run_cli(
                [
                    "run",
                    "--iterations",
                    "1",
                    "--dry-run",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                ]
            )
            self.assertEqual(second_run.returncode, 0, msg=second_run.stderr)
            run_payload = json.loads(second_run.stdout)
            self.assertEqual(run_payload["language"], "en")
            self.assertEqual(run_payload["display_language"], "en")
            self.assertEqual(run_payload["message"], "Agent run completed.")

    def test_run_reports_errors_with_diagnostic_excerpt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            result = self.run_cli(
                [
                    "run",
                    "--iterations",
                    "1",
                    "--language",
                    "en",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                    "--command",
                    sys.executable,
                    "-c",
                    "import sys; print('boom', file=sys.stderr); sys.exit(1)",
                ]
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["message"], "Agent run finished with errors.")
            self.assertEqual(payload["history"][0]["returncode"], 1)
            self.assertIn("boom", payload["history"][0]["stderr_excerpt"])

    def test_autonomy_enqueue_run_status_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            enqueue = self.run_cli(
                [
                    "enqueue-task",
                    "--task-type",
                    "write_note",
                    "--title",
                    "record note",
                    "--priority",
                    "8",
                    "--payload-json",
                    '{"path":"data/autonomy/notes.md","text":"hello"}',
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                    "--language",
                    "en",
                ]
            )
            self.assertEqual(enqueue.returncode, 0, msg=enqueue.stderr)
            enqueue_payload = json.loads(enqueue.stdout)
            self.assertEqual(enqueue_payload["message"], "Autonomy task has been queued.")
            self.assertEqual(enqueue_payload["task"]["task_type"], "write_note")

            run = self.run_cli(
                [
                    "run-autonomy",
                    "--cycles",
                    "1",
                    "--dry-run",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                    "--language",
                    "en",
                ]
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr)
            run_payload = json.loads(run.stdout)
            self.assertEqual(run_payload["message"], "Autonomous work cycle completed.")
            self.assertEqual(run_payload["summary"]["executed_count"], 1)
            self.assertEqual(run_payload["executed"][0]["task_type"], "write_note")

            status = self.run_cli(
                [
                    "autonomy-status",
                    "--state-path",
                    str(state_path),
                    "--language",
                    "en",
                ]
            )
            self.assertEqual(status.returncode, 0, msg=status.stderr)
            status_payload = json.loads(status.stdout)
            self.assertEqual(status_payload["message"], "Loaded autonomous work status.")
            self.assertIn("learning", status_payload["autonomy"])

    def test_additional_languages_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"

            set_language = self.run_cli(
                [
                    "set-language",
                    "--language",
                    "HI",
                    "--state-path",
                    str(state_path),
                ]
            )
            self.assertEqual(set_language.returncode, 0, msg=set_language.stderr)
            payload = json.loads(set_language.stdout)
            self.assertEqual(payload["language"], "hi")

            status = self.run_cli(["status", "--state-path", str(state_path)])
            self.assertEqual(status.returncode, 0, msg=status.stderr)
            status_payload = json.loads(status.stdout)
            self.assertEqual(status_payload["language"], "hi")


if __name__ == "__main__":
    unittest.main()
