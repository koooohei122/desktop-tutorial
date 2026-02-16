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


if __name__ == "__main__":
    unittest.main()
