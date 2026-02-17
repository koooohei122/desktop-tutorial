from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from growing_agent.autonomy import AutonomousWorker
from growing_agent.memory import MemoryStore
from growing_agent.prompt_runtime import (
    AutonomousWorkerRuntimeAdapter,
    MockRuntimeAdapter,
    RuntimeStep,
    execute_steps,
)
from growing_agent.tools.runner import CommandRunner


class TestPromptRuntime(unittest.TestCase):
    def test_mock_and_worker_runtime_share_interface(self) -> None:
        steps = [
            RuntimeStep(
                task_type="desktop_action",
                title="Wait",
                payload={"action": "wait", "seconds": 0.1},
                continue_on_failure=True,
            )
        ]

        mock_result = execute_steps(steps=steps, runtime=MockRuntimeAdapter(), dry_run=True)
        self.assertTrue(mock_result["overall_success"])
        self.assertEqual(mock_result["executed_steps"], 1)

        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryStore(Path(tmpdir) / "state.json")
            runner = CommandRunner(
                allowed_commands={"xdotool"},
                log_path=Path(tmpdir) / "runner.log",
            )
            worker = AutonomousWorker(
                memory=memory,
                runner=runner,
                language="en",
                workspace_root=tmpdir,
            )
            runtime = AutonomousWorkerRuntimeAdapter(worker)
            worker_result = execute_steps(steps=steps, runtime=runtime, dry_run=True)
            self.assertTrue(worker_result["overall_success"])
            self.assertEqual(worker_result["executed_steps"], 1)
            self.assertTrue(worker_result["step_results"][0]["success"])


if __name__ == "__main__":
    unittest.main()
