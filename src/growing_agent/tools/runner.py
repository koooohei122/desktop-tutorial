"""Safe command runner with allowlist and logging."""

import subprocess
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CommandRunner:
    """Safe command runner with allowlist restrictions."""
    
    # Allowlist of safe commands (no network, no destructive operations)
    ALLOWED_COMMANDS = {
        # Python/testing
        "python",
        "python3",
        "pytest",
        "pip",
        
        # File operations (read-only)
        "ls",
        "cat",
        "head",
        "tail",
        "wc",
        "grep",
        "find",
        "tree",
        
        # System info (read-only)
        "pwd",
        "whoami",
        "date",
        "echo",
        "env",
        
        # Version control (read-only)
        "git status",
        "git log",
        "git diff",
    }
    
    # Blocked dangerous commands
    BLOCKED_COMMANDS = {
        "rm",
        "rmdir",
        "dd",
        "mkfs",
        "format",
        "curl",
        "wget",
        "nc",
        "netcat",
        "ssh",
        "scp",
        "ftp",
        "telnet",
        "sudo",
        "su",
    }
    
    def __init__(self, dry_run: bool = False):
        """Initialize command runner.
        
        Args:
            dry_run: If True, only log commands without executing them
        """
        self.dry_run = dry_run
        self.command_log: List[Dict] = []
    
    def is_allowed(self, command: str) -> Tuple[bool, str]:
        """Check if a command is allowed to run.
        
        Args:
            command: Command string to check
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        if not command or not command.strip():
            return False, "Empty command"
        
        # Get the base command (first word)
        base_cmd = command.strip().split()[0]
        
        # Check if blocked
        if base_cmd in self.BLOCKED_COMMANDS:
            return False, f"Blocked command: {base_cmd}"
        
        # Check if allowed
        if base_cmd in self.ALLOWED_COMMANDS or command in self.ALLOWED_COMMANDS:
            return True, "Command allowed"
        
        return False, f"Command not in allowlist: {base_cmd}"
    
    def run(self, command: str, timeout: int = 30) -> Dict[str, any]:
        """Run a command if it's allowed.
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with execution results
        """
        timestamp = datetime.now().isoformat()
        
        # Check if command is allowed
        allowed, reason = self.is_allowed(command)
        
        result = {
            "timestamp": timestamp,
            "command": command,
            "allowed": allowed,
            "dry_run": self.dry_run,
            "stdout": "",
            "stderr": "",
            "returncode": None,
            "error": None
        }
        
        if not allowed:
            logger.warning(f"Command blocked: {command} - {reason}")
            result["error"] = reason
            self.command_log.append(result)
            return result
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would execute: {command}")
            result["stdout"] = "[DRY RUN] Command not executed"
            result["returncode"] = 0
            self.command_log.append(result)
            return result
        
        # Execute the command
        try:
            logger.info(f"Executing: {command}")
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            result["stdout"] = process.stdout
            result["stderr"] = process.stderr
            result["returncode"] = process.returncode
            
            if process.returncode == 0:
                logger.info(f"Command succeeded: {command}")
            else:
                logger.warning(f"Command failed with code {process.returncode}: {command}")
            
        except subprocess.TimeoutExpired:
            result["error"] = f"Command timed out after {timeout}s"
            logger.error(result["error"])
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error executing command: {e}")
        
        self.command_log.append(result)
        return result
    
    def get_log(self) -> List[Dict]:
        """Get the command execution log.
        
        Returns:
            List of command execution results
        """
        return self.command_log.copy()
    
    def clear_log(self) -> None:
        """Clear the command execution log."""
        self.command_log.clear()
