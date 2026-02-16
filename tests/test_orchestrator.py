from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

from growing_agent.config import AgentConfig
from growing_agent.memory import MemoryStore
from growing_agent.orchestrator import GrowingAgentOrchestrator
from growing_agent.tools.runner import CommandRunner


class TestOrchestrator(unittest.TestCase):
    def test_default_runner_allowlist_contains_configured_command_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            config = AgentConfig(
                iterations=1,
                dry_run=True,
                command=[sys.executable, "-c", "print('ok')"],
            )
            orch = GrowingAgentOrchestrator(
                memory=MemoryStore(state_path),
                runner=None,
                config=config,
            )
            self.assertIn(sys.executable, orch.runner.allowed_commands)

    def test_history_is_trimmed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            config = AgentConfig(
                iterations=5,
                dry_run=True,
                command=["pytest", "-q"],
                max_history=2,
            )
            orch = GrowingAgentOrchestrator(
                memory=MemoryStore(state_path),
                runner=CommandRunner(allowed_commands={"pytest"}, log_path=log_path),
                config=config,
            )
            state = orch.run()
            self.assertEqual(state["iteration"], 5)
            self.assertEqual(len(state["history"]), 2)
            self.assertEqual(state["metrics"]["iterations_recorded"], 2)

    def test_run_preserves_autonomy_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"

            memory = MemoryStore(state_path)
            seed = memory.read_state()
            autonomy = seed.get("autonomy", {})
            if not isinstance(autonomy, dict):
                autonomy = {}
            queue = autonomy.get("queue", [])
            if not isinstance(queue, list):
                queue = []
            queue.append(
                {
                    "task_id": "abc123",
                    "task_type": "write_note",
                    "title": "keep-me",
                    "payload": {"path": "data/autonomy/notes.md", "text": "x"},
                    "priority": 5,
                    "attempts": 0,
                    "created_at_utc": "2026-01-01T00:00:00+00:00",
                }
            )
            autonomy["queue"] = queue
            seed["autonomy"] = autonomy
            memory.write_state(seed)

            config = AgentConfig(
                iterations=1,
                dry_run=True,
                command=["pytest", "-q"],
            )
            orch = GrowingAgentOrchestrator(
                memory=memory,
                runner=CommandRunner(allowed_commands={"pytest"}, log_path=log_path),
                config=config,
            )
            orch.run()

            persisted = memory.read_state()
            persisted_autonomy = persisted.get("autonomy", {})
            self.assertIsInstance(persisted_autonomy, dict)
            persisted_queue = persisted_autonomy.get("queue", [])
            self.assertIsInstance(persisted_queue, list)
            self.assertEqual(len(persisted_queue), 1)
            self.assertEqual(persisted_queue[0]["task_id"], "abc123")

    def test_stop_on_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            config = AgentConfig(
                iterations=10,
                dry_run=True,
                command=["pytest", "-q"],
                stop_on_target=True,
                target_score=1.0,
                language="en",
            )
            orch = GrowingAgentOrchestrator(
                memory=MemoryStore(state_path),
                runner=CommandRunner(allowed_commands={"pytest"}, log_path=log_path),
                config=config,
            )
            state = orch.run()
            self.assertEqual(state["iteration"], 1)
            self.assertEqual(state["stop_reason"], "target_score_reached")
            self.assertEqual(state["stop_message"], "Stopped because target score was reached.")
            self.assertEqual(state["language"], "en")

    def test_halt_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            log_path = Path(tmpdir) / "runner.log"
            executable = Path(sys.executable).name
            config = AgentConfig(
                iterations=5,
                dry_run=False,
                command=[sys.executable, "-c", "import sys; sys.exit(1)"],
                halt_on_error=True,
            )
            orch = GrowingAgentOrchestrator(
                memory=MemoryStore(state_path),
                runner=CommandRunner(allowed_commands={executable}, log_path=log_path),
                config=config,
            )
            state = orch.run()
            self.assertEqual(state["iteration"], 1)
            self.assertEqual(state["stop_reason"], "command_error")


if __name__ == "__main__":
    unittest.main()
