from __future__ import annotations

import json
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RunResult:
    argv: list[str]
    cwd: str
    dry_run: bool
    returncode: int | None
    stdout: str
    stderr: str
    duration_ms: int

    def command_str(self) -> str:
        return shlex.join(self.argv)


class CommandNotAllowedError(RuntimeError):
    pass


class AllowedCommandRunner:
    """
    Runs only explicitly allowlisted commands (no shell).

    Also writes JSONL logs to `logs/runner.log` (relative to CWD).
    """

    def __init__(
        self,
        *,
        allowed_commands: Sequence[str] | None = None,
        log_path: Path | None = None,
    ) -> None:
        default_python = Path(sys.executable).name
        self.allowed_commands = set(allowed_commands or ("pytest", default_python))
        self.log_path = log_path or (Path.cwd() / "logs" / "runner.log")

    def _ensure_allowed(self, argv: Sequence[str]) -> None:
        if not argv:
            raise CommandNotAllowedError("Empty command is not allowed")

        cmd0 = argv[0]
        cmd_name = Path(cmd0).name
        if cmd0 not in self.allowed_commands and cmd_name not in self.allowed_commands:
            raise CommandNotAllowedError(f"Command not allowlisted: {cmd0!r}")

        # Extra safety: if python is allowlisted, forbid using pip/ensurepip modules.
        if cmd_name.startswith("python"):
            for i, tok in enumerate(argv):
                if tok == "-m" and i + 1 < len(argv) and argv[i + 1] in {"pip", "ensurepip"}:
                    raise CommandNotAllowedError("python -m pip/ensurepip is not allowed")

    def _append_log(self, entry: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout_s: int = 600,
        dry_run: bool = False,
    ) -> RunResult:
        self._ensure_allowed(argv)

        cwd_path = (cwd or Path.cwd()).resolve()
        start = time.monotonic()

        if dry_run:
            result = RunResult(
                argv=list(argv),
                cwd=str(cwd_path),
                dry_run=True,
                returncode=None,
                stdout="",
                stderr="",
                duration_ms=0,
            )
            self._append_log(
                {
                    "ts": _utc_now_iso(),
                    "argv": result.argv,
                    "cwd": result.cwd,
                    "dry_run": True,
                    "returncode": None,
                    "duration_ms": 0,
                }
            )
            return result

        cp = subprocess.run(
            list(argv),
            cwd=str(cwd_path),
            env=dict(env) if env is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            shell=False,
        )

        duration_ms = int((time.monotonic() - start) * 1000)
        result = RunResult(
            argv=list(argv),
            cwd=str(cwd_path),
            dry_run=False,
            returncode=cp.returncode,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
            duration_ms=duration_ms,
        )

        self._append_log(
            {
                "ts": _utc_now_iso(),
                "argv": result.argv,
                "cwd": result.cwd,
                "dry_run": False,
                "returncode": result.returncode,
                "duration_ms": result.duration_ms,
            }
        )
        return result

