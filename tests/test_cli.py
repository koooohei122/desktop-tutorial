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
            self.assertIn("moment", run_payload)
            self.assertIn("fun", run_payload)

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
            self.assertIn("fun", status_payload)

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

    def test_spawn_challenges_and_fun_status_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            spawn = self.run_cli(
                [
                    "spawn-challenges",
                    "--count",
                    "2",
                    "--base-priority",
                    "6",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                    "--language",
                    "en",
                ]
            )
            self.assertEqual(spawn.returncode, 0, msg=spawn.stderr)
            spawn_payload = json.loads(spawn.stdout)
            self.assertEqual(spawn_payload["message"], "Challenge pack generated.")
            self.assertEqual(spawn_payload["added_count"], 2)

            run = self.run_cli(
                [
                    "run-autonomy",
                    "--cycles",
                    "2",
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
            self.assertEqual(run_payload["summary"]["executed_count"], 2)
            self.assertGreaterEqual(int(run_payload["summary"]["xp_gained"]), 1)
            self.assertTrue(isinstance(run_payload["moment"], str) and run_payload["moment"])

            fun_status = self.run_cli(
                [
                    "fun-status",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                    "--language",
                    "en",
                ]
            )
            self.assertEqual(fun_status.returncode, 0, msg=fun_status.stderr)
            fun_payload = json.loads(fun_status.stdout)
            self.assertEqual(fun_payload["message"], "Loaded fun progression status.")
            self.assertIn("game", fun_payload["fun"])

    def test_enqueue_desktop_action_and_mission_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            desktop = self.run_cli(
                [
                    "enqueue-desktop-action",
                    "--action",
                    "focus_window",
                    "--window-title",
                    "Terminal",
                    "--window-index",
                    "0",
                    "--window-match-mode",
                    "exact",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                    "--language",
                    "en",
                ]
            )
            self.assertEqual(desktop.returncode, 0, msg=desktop.stderr)
            desktop_payload = json.loads(desktop.stdout)
            self.assertEqual(desktop_payload["task"]["task_type"], "desktop_action")
            self.assertEqual(desktop_payload["task"]["payload"]["action"], "focus_window")
            self.assertEqual(desktop_payload["task"]["payload"]["window_title"], "Terminal")
            self.assertEqual(desktop_payload["task"]["payload"]["window_match_mode"], "exact")

            mission = self.run_cli(
                [
                    "enqueue-mission",
                    "--title",
                    "test mission",
                    "--steps-json",
                    '[{"task_type":"desktop_action","payload":{"action":"wait","seconds":0.01}},{"task_type":"command","payload":{"command":["echo","ok"]}}]',
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                    "--language",
                    "en",
                ]
            )
            self.assertEqual(mission.returncode, 0, msg=mission.stderr)
            mission_payload = json.loads(mission.stdout)
            self.assertEqual(mission_payload["task"]["task_type"], "mission")

            perception = self.run_cli(
                [
                    "enqueue-desktop-perception",
                    "--path",
                    "data/autonomy/perception.png",
                    "--ocr-lang",
                    "eng",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                    "--language",
                    "en",
                ]
            )
            self.assertEqual(perception.returncode, 0, msg=perception.stderr)
            perception_payload = json.loads(perception.stdout)
            self.assertEqual(perception_payload["task"]["task_type"], "desktop_perception")

            run = self.run_cli(
                [
                    "run-autonomy",
                    "--until-empty",
                    "--max-cycles",
                    "10",
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
            self.assertEqual(run_payload["summary"]["queue_size"], 0)
            self.assertGreaterEqual(run_payload["summary"]["executed_count"], 3)

    def test_enqueue_desktop_action_rejects_invalid_window_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            unsupported = self.run_cli(
                [
                    "enqueue-desktop-action",
                    "--action",
                    "wait",
                    "--seconds",
                    "0.1",
                    "--window-title",
                    "Terminal",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                ]
            )
            self.assertNotEqual(unsupported.returncode, 0)
            self.assertIn("Window selectors are only supported", unsupported.stderr)

            missing_title = self.run_cli(
                [
                    "enqueue-desktop-action",
                    "--action",
                    "click",
                    "--x",
                    "100",
                    "--y",
                    "200",
                    "--window-index",
                    "1",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                ]
            )
            self.assertNotEqual(missing_title.returncode, 0)
            self.assertIn("--window-index requires --window-title or --window-class or --window-pid", missing_title.stderr)

            invalid_relative = self.run_cli(
                [
                    "enqueue-desktop-action",
                    "--action",
                    "type_text",
                    "--text",
                    "hello",
                    "--relative-to-window",
                    "--window-class",
                    "gnome-terminal",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                ]
            )
            self.assertNotEqual(invalid_relative.returncode, 0)
            self.assertIn("--relative-to-window is only supported for click/move actions", invalid_relative.stderr)

    def test_enqueue_desktop_action_with_class_pid_and_relative_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            result = self.run_cli(
                [
                    "enqueue-desktop-action",
                    "--action",
                    "click",
                    "--x",
                    "120",
                    "--y",
                    "40",
                    "--button",
                    "1",
                    "--window-class",
                    "gnome-terminal",
                    "--window-pid",
                    "12345",
                    "--relative-to-window",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                    "--language",
                    "en",
                ]
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            task_payload = payload["task"]["payload"]
            self.assertEqual(task_payload["window_class"], "gnome-terminal")
            self.assertEqual(task_payload["window_pid"], 12345)
            self.assertTrue(task_payload["relative_to_window"])

    def test_list_windows_command_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            result = self.run_cli(
                [
                    "list-windows",
                    "--title",
                    "Terminal",
                    "--window-class",
                    "gnome-terminal",
                    "--window-pid",
                    "12345",
                    "--match-mode",
                    "smart",
                    "--limit",
                    "10",
                    "--dry-run",
                    "--state-path",
                    str(state_path),
                    "--log-path",
                    str(log_path),
                    "--language",
                    "en",
                ]
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["message"], "Window candidates listed.")
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["window_title"], "Terminal")
            self.assertEqual(payload["window_class"], "gnome-terminal")
            self.assertEqual(payload["window_pid"], 12345)
            self.assertEqual(payload["match_mode"], "smart")
            self.assertEqual(payload["windows"], [])


if __name__ == "__main__":
    unittest.main()
