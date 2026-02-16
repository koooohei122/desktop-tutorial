from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Sequence


BLOCKED_TOKENS = {
    "rm",
    "mkfs",
    "dd",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "init",
    "chmod",
    "chown",
}


@dataclass
class RunResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    allowed: bool
    dry_run: bool
    duration_seconds: float
    timed_out: bool


class CommandRunner:
    """Runs allowlisted commands and appends JSON-line logs."""

    def __init__(
        self,
        allowed_commands: set[str] | None = None,
        log_path: str | Path = "data/runner.log",
        max_log_bytes: int = 1_000_000,
    ) -> None:
        if allowed_commands is None:
            self.allowed_commands = {"pytest"}
        else:
            self.allowed_commands = {str(item) for item in allowed_commands}
        self.log_path = Path(log_path)
        if max_log_bytes < 1:
            raise ValueError("max_log_bytes must be >= 1")
        self.max_log_bytes = max_log_bytes

    def run(
        self,
        command: Sequence[str],
        dry_run: bool = False,
        timeout_seconds: float = 30.0,
    ) -> RunResult:
        if not command:
            raise ValueError("command must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")

        normalized_command = list(command)
        executable_token = normalized_command[0]
        executable = Path(executable_token).name
        if not self._is_allowlisted_executable(executable_token):
            result = RunResult(
                command=normalized_command,
                returncode=126,
                stdout="",
                stderr=f"Command '{executable}' is not in the allowlist.",
                allowed=False,
                dry_run=dry_run,
                duration_seconds=0.0,
                timed_out=False,
            )
            self._append_log(result)
            return result

        blocked = self._blocked_executable(executable_token)
        if blocked is not None:
            result = RunResult(
                command=normalized_command,
                returncode=127,
                stdout="",
                stderr=f"Command token '{blocked}' is blocked for safety.",
                allowed=False,
                dry_run=dry_run,
                duration_seconds=0.0,
                timed_out=False,
            )
            self._append_log(result)
            return result

        if dry_run:
            result = RunResult(
                command=normalized_command,
                returncode=0,
                stdout="DRY-RUN: command was not executed.",
                stderr="",
                allowed=True,
                dry_run=True,
                duration_seconds=0.0,
                timed_out=False,
            )
            self._append_log(result)
            return result

        started = time.monotonic()
        try:
            completed = subprocess.run(
                normalized_command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            duration = round(time.monotonic() - started, 4)
            result = RunResult(
                command=normalized_command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                allowed=True,
                dry_run=False,
                duration_seconds=duration,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as error:
            duration = round(time.monotonic() - started, 4)
            result = RunResult(
                command=normalized_command,
                returncode=124,
                stdout=error.stdout or "",
                stderr=(error.stderr or "")
                + f"\nExecution timed out after {timeout_seconds} seconds.",
                allowed=True,
                dry_run=False,
                duration_seconds=duration,
                timed_out=True,
            )
        except OSError as error:
            duration = round(time.monotonic() - started, 4)
            result = RunResult(
                command=normalized_command,
                returncode=127,
                stdout="",
                stderr=f"Execution failed: {error}",
                allowed=True,
                dry_run=False,
                duration_seconds=duration,
                timed_out=False,
            )

        self._append_log(result)
        return result

    def _append_log(self, result: RunResult) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._maybe_rotate_log()
        payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            **asdict(result),
        }
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def _maybe_rotate_log(self) -> None:
        if not self.log_path.exists():
            return
        if self.log_path.stat().st_size < self.max_log_bytes:
            return

        rotated_path = self.log_path.with_suffix(self.log_path.suffix + ".1")
        if rotated_path.exists():
            rotated_path.unlink()
        self.log_path.replace(rotated_path)

    def _blocked_executable(self, executable_token: str) -> str | None:
        lowered = Path(executable_token).name.strip().lower().rstrip(".,;:")
        if lowered in BLOCKED_TOKENS:
            return lowered
        return None

    def _is_allowlisted_executable(self, executable_token: str) -> bool:
        if executable_token in self.allowed_commands:
            return True

        executable_name = Path(executable_token).name
        if executable_name not in self.allowed_commands:
            return False

        # If the user passed a bare command name, allow by name.
        if executable_token == executable_name:
            return True

        # If a path was passed, only allow it when it resolves to the same
        # executable that would be chosen from PATH for that command name.
        on_path = shutil.which(executable_name)
        if not on_path:
            return False

        return os.path.realpath(executable_token) == os.path.realpath(on_path)
