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


if __name__ == "__main__":
    unittest.main()
