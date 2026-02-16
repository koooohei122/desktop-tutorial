from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

from growing_agent.tools.runner import CommandRunner


class TestCommandRunner(unittest.TestCase):
    def test_disallowed_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CommandRunner(allowed_commands={"pytest"}, log_path=Path(tmpdir) / "run.log")
            result = runner.run(["python3", "-V"])
            self.assertFalse(result.allowed)
            self.assertEqual(result.returncode, 126)

    def test_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = Path(sys.executable).name
            runner = CommandRunner(
                allowed_commands={executable},
                log_path=Path(tmpdir) / "run.log",
            )
            result = runner.run([sys.executable, "-c", "print('ok')"], dry_run=True)
            self.assertTrue(result.allowed)
            self.assertTrue(result.dry_run)
            self.assertIn("DRY-RUN", result.stdout)

    def test_executes_command_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "run.log"
            executable = Path(sys.executable).name
            runner = CommandRunner(allowed_commands={executable}, log_path=log_path)
            result = runner.run([sys.executable, "-c", "print('ok')"])

            self.assertEqual(result.returncode, 0)
            self.assertIn("ok", result.stdout)
            self.assertTrue(log_path.exists())
            lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn('"command":', lines[0])

    def test_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = Path(sys.executable).name
            runner = CommandRunner(
                allowed_commands={executable},
                log_path=Path(tmpdir) / "run.log",
            )
            result = runner.run(
                [sys.executable, "-c", "import time; time.sleep(0.2)"],
                timeout_seconds=0.01,
            )
            self.assertTrue(result.timed_out)
            self.assertEqual(result.returncode, 124)

    def test_blocked_executable_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CommandRunner(
                allowed_commands={"rm"},
                log_path=Path(tmpdir) / "run.log",
            )
            result = runner.run(["/bin/rm", "--version"])
            self.assertFalse(result.allowed)
            self.assertEqual(result.returncode, 127)

    def test_dangerous_token_in_argument_is_not_executable_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = Path(sys.executable).name
            runner = CommandRunner(
                allowed_commands={executable},
                log_path=Path(tmpdir) / "run.log",
            )
            result = runner.run([sys.executable, "-c", "print('safe')", "rm"])
            self.assertTrue(result.allowed)
            self.assertEqual(result.returncode, 0)

    def test_allowlist_name_does_not_allow_arbitrary_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_executable = Path(tmpdir) / "pytest"
            fake_executable.write_text("#!/bin/sh\necho fake\n", encoding="utf-8")
            fake_executable.chmod(0o755)

            runner = CommandRunner(
                allowed_commands={"pytest"},
                log_path=Path(tmpdir) / "run.log",
            )
            result = runner.run([str(fake_executable), "-q"])
            self.assertFalse(result.allowed)
            self.assertEqual(result.returncode, 126)

    def test_empty_allowlist_rejects_pytest_too(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CommandRunner(
                allowed_commands=set(),
                log_path=Path(tmpdir) / "run.log",
            )
            result = runner.run(["pytest", "-q"], dry_run=True)
            self.assertFalse(result.allowed)
            self.assertEqual(result.returncode, 126)

    def test_invalid_log_size_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                CommandRunner(
                    allowed_commands={"pytest"},
                    log_path=Path(tmpdir) / "run.log",
                    max_log_bytes=0,
                )

    def test_log_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "run.log"
            executable = Path(sys.executable).name
            runner = CommandRunner(
                allowed_commands={executable},
                log_path=log_path,
                max_log_bytes=10,
            )
            runner.run([sys.executable, "-c", "print('first')"])
            runner.run([sys.executable, "-c", "print('second')"])
            rotated = Path(tmpdir) / "run.log.1"
            self.assertTrue(rotated.exists())


if __name__ == "__main__":
    unittest.main()
