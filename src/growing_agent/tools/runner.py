from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Sequence


@dataclass
class RunResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    allowed: bool
    dry_run: bool


class CommandRunner:
    """Runs allowlisted commands and appends JSON-line logs."""

    def __init__(
        self,
        allowed_commands: set[str] | None = None,
        log_path: str | Path = "data/runner.log",
    ) -> None:
        self.allowed_commands = allowed_commands or {"pytest"}
        self.log_path = Path(log_path)

    def run(self, command: Sequence[str], dry_run: bool = False) -> RunResult:
        if not command:
            raise ValueError("command must not be empty")

        executable = command[0]
        if executable not in self.allowed_commands:
            result = RunResult(
                command=list(command),
                returncode=126,
                stdout="",
                stderr=f"Command '{executable}' is not in the allowlist.",
                allowed=False,
                dry_run=dry_run,
            )
            self._append_log(result)
            return result

        if dry_run:
            result = RunResult(
                command=list(command),
                returncode=0,
                stdout="DRY-RUN: command was not executed.",
                stderr="",
                allowed=True,
                dry_run=True,
            )
            self._append_log(result)
            return result

        completed = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
        )
        result = RunResult(
            command=list(command),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            allowed=True,
            dry_run=False,
        )
        self._append_log(result)
        return result

    def _append_log(self, result: RunResult) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            **asdict(result),
        }
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=True) + "\n")
