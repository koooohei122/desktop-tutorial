"""Safe command runner with an allowlist and logging."""

from __future__ import annotations

import logging
import shlex
import subprocess
from dataclasses import dataclass, field
from typing import Sequence

logger = logging.getLogger(__name__)

ALLOWED_COMMANDS: set[str] = {
    "python",
    "python3",
    "pytest",
    "echo",
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "date",
    "true",
    "false",
}

BLOCKED_SUBSTRINGS: list[str] = [
    "rm -rf",
    "mkfs",
    "dd ",
    ":(){",
    "fork",
    "> /dev/sd",
    "curl ",
    "wget ",
    "ssh ",
    "scp ",
    "nc ",
    "ncat ",
]


@dataclass
class RunResult:
    """Outcome of a single command execution."""

    command: str
    returncode: int
    stdout: str
    stderr: str
    blocked: bool = False
    dry_run: bool = False
    logs: list[str] = field(default_factory=list)


def _is_allowed(cmd_parts: Sequence[str]) -> bool:
    """Return True when the base command is in the allowlist."""
    if not cmd_parts:
        return False
    base = cmd_parts[0].split("/")[-1]
    return base in ALLOWED_COMMANDS


def _contains_blocked(raw: str) -> bool:
    lower = raw.lower()
    return any(sub in lower for sub in BLOCKED_SUBSTRINGS)


def run_command(
    command: str,
    *,
    dry_run: bool = False,
    timeout: int = 30,
) -> RunResult:
    """Run *command* if it passes safety checks.

    Parameters
    ----------
    command:
        Shell command string.
    dry_run:
        When ``True`` the command is **not** executed; only validation runs.
    timeout:
        Max seconds before the process is killed.
    """
    logs: list[str] = []
    parts = shlex.split(command)

    if _contains_blocked(command):
        msg = f"BLOCKED (dangerous substring): {command}"
        logs.append(msg)
        logger.warning(msg)
        return RunResult(
            command=command,
            returncode=-1,
            stdout="",
            stderr=msg,
            blocked=True,
            dry_run=dry_run,
            logs=logs,
        )

    if not _is_allowed(parts):
        msg = f"BLOCKED (not in allowlist): {parts[0] if parts else command}"
        logs.append(msg)
        logger.warning(msg)
        return RunResult(
            command=command,
            returncode=-1,
            stdout="",
            stderr=msg,
            blocked=True,
            dry_run=dry_run,
            logs=logs,
        )

    if dry_run:
        msg = f"DRY-RUN (skipped): {command}"
        logs.append(msg)
        logger.info(msg)
        return RunResult(
            command=command,
            returncode=0,
            stdout="",
            stderr="",
            blocked=False,
            dry_run=True,
            logs=logs,
        )

    logs.append(f"EXEC: {command}")
    logger.info("Running: %s", command)
    try:
        proc = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        logs.append(f"returncode={proc.returncode}")
        return RunResult(
            command=command,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            blocked=False,
            dry_run=False,
            logs=logs,
        )
    except subprocess.TimeoutExpired:
        msg = f"TIMEOUT after {timeout}s: {command}"
        logs.append(msg)
        logger.error(msg)
        return RunResult(
            command=command,
            returncode=-2,
            stdout="",
            stderr=msg,
            blocked=False,
            dry_run=False,
            logs=logs,
        )
