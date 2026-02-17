from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

from growing_agent.autonomy import AutonomousWorker, build_default_autonomy_state
from growing_agent.memory import MemoryStore
from growing_agent.tools.runner import CommandRunner


class TestAutonomyWorker(unittest.TestCase):
    def test_write_note_task_executes_and_updates_learning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            memory = MemoryStore(state_path)
            runner = CommandRunner(allowed_commands={"python3"}, log_path=log_path)
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="en",
                workspace_root=tmpdir,
            )

            worker.enqueue(
                task_type="write_note",
                title="append note",
                payload={"path": "data/autonomy/notes.md", "text": "hello autonomy"},
                priority=7,
            )
            result = worker.run(cycles=1, dry_run=False)

            self.assertEqual(result["summary"]["executed_count"], 1)
            self.assertEqual(result["summary"]["failure_count"], 0)
            self.assertEqual(len(result["executed"]), 1)
            self.assertTrue(result["executed"][0]["success"])
            self.assertIn("fun", result["executed"][0])
            self.assertGreater(result["executed"][0]["fun"]["xp_gained"], 0)

            notes_path = Path(tmpdir) / "data" / "autonomy" / "notes.md"
            self.assertTrue(notes_path.exists())
            self.assertIn("hello autonomy", notes_path.read_text(encoding="utf-8"))

            state = memory.read_state()
            autonomy = state.get("autonomy", build_default_autonomy_state())
            learning = autonomy.get("learning", {})
            stats = learning.get("task_type_stats", {})
            write_note_stats = stats.get("write_note", {})
            self.assertEqual(write_note_stats.get("attempts"), 1)
            self.assertEqual(write_note_stats.get("successes"), 1)
            self.assertGreaterEqual(float(write_note_stats.get("avg_reward", 0.0)), 1.0)
            game = autonomy.get("game", {})
            self.assertIsInstance(game, dict)
            self.assertGreater(int(game.get("xp", 0)), 0)
            self.assertIn("first_steps", game.get("badges", []))

    def test_failure_adds_improvement_and_followup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            memory = MemoryStore(state_path)
            runner = CommandRunner(
                allowed_commands={sys.executable, Path(sys.executable).name},
                log_path=log_path,
            )
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="ja",
                workspace_root=tmpdir,
            )

            worker.enqueue(
                task_type="command",
                title="failing command",
                payload={"command": [sys.executable, "-c", "import sys; sys.exit(2)"]},
                priority=5,
            )
            result = worker.run(cycles=1, dry_run=False)
            self.assertEqual(result["summary"]["failure_count"], 1)

            state = memory.read_state()
            autonomy = state["autonomy"]
            backlog = autonomy["learning"]["improvement_backlog"]
            self.assertGreaterEqual(len(backlog), 1)
            self.assertEqual(backlog[-1]["task_type"], "command")

            queued = autonomy["queue"]
            follow_ups = [item for item in queued if item.get("task_type") == "analyze_state"]
            self.assertGreaterEqual(len(follow_ups), 1)

    def test_learning_scores_affect_task_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            memory = MemoryStore(state_path)
            runner = CommandRunner(
                allowed_commands={sys.executable, Path(sys.executable).name},
                log_path=log_path,
            )
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="en",
                workspace_root=tmpdir,
            )

            worker.enqueue(
                task_type="write_note",
                title="note task",
                payload={"path": "data/autonomy/notes.md", "text": "note"},
                priority=5,
            )
            worker.enqueue(
                task_type="command",
                title="command task",
                payload={"command": [sys.executable, "-c", "print('ok')"]},
                priority=5,
            )

            seeded = memory.read_state()
            autonomy = seeded["autonomy"]
            autonomy["learning"]["task_type_stats"] = {
                "write_note": {"attempts": 5, "successes": 4, "avg_reward": 0.2},
                "command": {"attempts": 5, "successes": 5, "avg_reward": 0.95},
            }
            seeded["autonomy"] = autonomy
            memory.write_state(seeded)

            result = worker.run(cycles=1, dry_run=True)
            self.assertEqual(len(result["executed"]), 1)
            self.assertEqual(result["executed"][0]["task_type"], "command")

    def test_spawn_challenges_and_fun_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            memory = MemoryStore(state_path)
            runner = CommandRunner(
                allowed_commands={sys.executable, Path(sys.executable).name, "echo"},
                log_path=log_path,
            )
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="en",
                workspace_root=tmpdir,
            )

            tasks = worker.spawn_challenges(count=3, base_priority=6)
            self.assertEqual(len(tasks), 3)
            self.assertTrue(all(task.get("is_challenge") is True for task in tasks))

            result = worker.run(cycles=3, dry_run=True)
            self.assertEqual(result["summary"]["executed_count"], 3)
            self.assertGreaterEqual(result["summary"]["xp_gained"], 1)

            fun = worker.fun_status()
            self.assertIn("game", fun)
            self.assertGreaterEqual(int(fun["game"]["xp"]), 1)

    def test_desktop_action_wait_and_mission(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            memory = MemoryStore(state_path)
            runner = CommandRunner(
                allowed_commands={"echo", "xdotool", "python3"},
                log_path=log_path,
            )
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="en",
                workspace_root=tmpdir,
            )

            worker.enqueue(
                task_type="desktop_action",
                title="wait a bit",
                payload={"action": "wait", "seconds": 0.01},
                priority=5,
            )
            worker.enqueue(
                task_type="mission",
                title="mixed mission",
                payload={
                    "max_step_failures": 0,
                    "steps": [
                        {"task_type": "desktop_action", "payload": {"action": "wait", "seconds": 0.01}},
                        {"task_type": "command", "payload": {"command": ["echo", "ok"]}},
                    ],
                },
                priority=6,
            )

            result = worker.run(cycles=2, dry_run=True)
            self.assertEqual(result["summary"]["executed_count"], 2)
            task_types = [item["task_type"] for item in result["executed"]]
            self.assertIn("desktop_action", task_types)
            self.assertIn("mission", task_types)

            mission_result = next(item for item in result["executed"] if item["task_type"] == "mission")
            self.assertTrue(mission_result["success"])
            self.assertEqual(mission_result["details"]["total_steps"], 2)

    def test_desktop_action_focus_window_requires_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            memory = MemoryStore(state_path)
            runner = CommandRunner(
                allowed_commands={"xdotool"},
                log_path=log_path,
            )
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="en",
                workspace_root=tmpdir,
            )

            worker.enqueue(
                task_type="desktop_action",
                title="focus missing title",
                payload={"action": "focus_window"},
                priority=6,
            )
            result = worker.run(cycles=1, dry_run=True)
            self.assertEqual(result["summary"]["executed_count"], 1)
            action_result = result["executed"][0]
            self.assertFalse(action_result["success"])
            self.assertIn("window_title", action_result["summary"])

    def test_desktop_action_type_text_with_window_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            memory = MemoryStore(state_path)
            runner = CommandRunner(
                allowed_commands={"xdotool"},
                log_path=log_path,
            )
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="en",
                workspace_root=tmpdir,
            )

            worker.enqueue(
                task_type="desktop_action",
                title="type text into target window",
                payload={
                    "action": "type_text",
                    "text": "hello",
                    "window_title": "Terminal",
                    "window_index": 1,
                    "window_match_mode": "exact",
                    "focus_settle_seconds": 0.25,
                },
                priority=6,
            )
            result = worker.run(cycles=1, dry_run=True)
            self.assertEqual(result["summary"]["executed_count"], 1)
            action_result = result["executed"][0]
            self.assertTrue(action_result["success"])
            self.assertEqual(action_result["details"]["window_title"], "Terminal")
            self.assertEqual(action_result["details"]["window_index"], 1)
            self.assertEqual(action_result["details"]["window_match_mode"], "exact")
            self.assertIn("focus", action_result["details"])
            self.assertTrue(action_result["details"]["focus"]["dry_run"])
            self.assertAlmostEqual(float(action_result["details"]["focus_settle_seconds"]), 0.25, places=3)

    def test_desktop_action_open_url_rejects_window_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            memory = MemoryStore(state_path)
            runner = CommandRunner(
                allowed_commands={"xdg-open", "xdotool"},
                log_path=log_path,
            )
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="en",
                workspace_root=tmpdir,
            )

            worker.enqueue(
                task_type="desktop_action",
                title="open url with invalid target",
                payload={
                    "action": "open_url",
                    "url": "https://example.com",
                    "window_title": "Terminal",
                },
                priority=6,
            )
            result = worker.run(cycles=1, dry_run=True)
            action_result = result["executed"][0]
            self.assertFalse(action_result["success"])
            self.assertIn("not supported", action_result["summary"])
            self.assertEqual(action_result["details"]["action"], "open_url")

    def test_inspect_windows_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            memory = MemoryStore(state_path)
            runner = CommandRunner(
                allowed_commands={"xdotool"},
                log_path=log_path,
            )
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="en",
                workspace_root=tmpdir,
            )

            inspected = worker.inspect_windows(
                title="Terminal",
                match_mode="smart",
                limit=25,
                dry_run=True,
            )
            self.assertTrue(inspected["success"])
            self.assertTrue(inspected["dry_run"])
            self.assertEqual(inspected["match_mode"], "smart")
            self.assertEqual(inspected["window_title"], "Terminal")
            self.assertEqual(inspected["windows"], [])
            self.assertGreaterEqual(len(inspected["search_plan"]), 1)

    def test_desktop_perception_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            memory = MemoryStore(state_path)
            runner = CommandRunner(
                allowed_commands={"scrot", "tesseract"},
                log_path=log_path,
            )
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="en",
                workspace_root=tmpdir,
            )

            worker.enqueue(
                task_type="desktop_perception",
                title="screen snapshot",
                payload={"capture_path": "data/autonomy/perception.png", "ocr": True},
                priority=6,
            )
            result = worker.run(cycles=1, dry_run=True)
            self.assertEqual(result["summary"]["executed_count"], 1)
            perception = result["executed"][0]
            self.assertEqual(perception["task_type"], "desktop_perception")
            self.assertTrue(perception["success"])
            self.assertIn(
                perception["details"]["ocr_status"],
                {"ok", "failed", "skipped"},
            )

    def test_mission_on_failure_recovery_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            memory = MemoryStore(state_path)
            runner = CommandRunner(
                allowed_commands={"echo"},
                log_path=log_path,
            )
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="en",
                workspace_root=tmpdir,
            )

            worker.enqueue(
                task_type="mission",
                title="recoverable",
                payload={
                    "max_step_failures": 0,
                    "auto_recovery": False,
                    "steps": [
                        {
                            "task_type": "command",
                            "payload": {"command": ["not-allowed-cmd"]},
                            "continue_on_failure": True,
                            "on_failure": [
                                {
                                    "task_type": "command",
                                    "payload": {"command": ["echo", "recovered"]},
                                }
                            ],
                        }
                    ],
                },
                priority=7,
            )

            result = worker.run(cycles=1, dry_run=True)
            mission = result["executed"][0]
            self.assertEqual(mission["task_type"], "mission")
            self.assertTrue(mission["success"])
            step = mission["details"]["step_results"][0]
            self.assertTrue(step.get("recovered"))
            self.assertIn("on_failure_results", step)


if __name__ == "__main__":
    unittest.main()
