"""Allowlist command runner with logs. No network, no destructive commands."""

import subprocess
from pathlib import Path

# Commands allowed to run (whitelist). Destructive commands excluded.
ALLOWED_COMMANDS = frozenset({
    "pytest",
    "python",
    "python3",
    "ls",
    "cat",
    "echo",
    "head",
    "tail",
    "wc",
    "grep",
    "find",
    "mkdir",
    "touch",
    "cp",
    "mv",
    "diff",
    "true",
    "false",
})

# Destructive patterns to reject
FORBIDDEN_PATTERNS = (
    "rm ",
    "rm -",
    "rm -rf",
    "rm -fr",
    "> /dev",
    "dd ",
    "mkfs",
    "format",
    "shutdown",
    "reboot",
    "curl",
    "wget",
    "nc ",
    "netcat",
)


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """
    Run a command if it passes the allowlist. Returns (exit_code, stdout, stderr).
    """
    if not cmd:
        return 1, "", "Empty command"
    base = Path(cmd[0]).name if cmd[0] else ""
    if base not in ALLOWED_COMMANDS:
        return 1, "", f"Command not allowed: {base}"
    full_cmd = " ".join(cmd)
    for pat in FORBIDDEN_PATTERNS:
        if pat in full_cmd:
            return 1, "", f"Forbidden pattern: {pat}"
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def run_and_log(cmd: list[str], cwd: Path | None = None, log_path: Path | None = None) -> tuple[int, str, str]:
    """
    Run command and append to log file if log_path given.
    """
    code, out, err = run_command(cmd, cwd=cwd)
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f">>> {' '.join(cmd)}\n")
            f.write(f"exit={code}\n")
            if out:
                f.write(out)
            if err:
                f.write(err)
            f.write("\n")
    return code, out, err
