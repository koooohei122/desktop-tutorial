"""Memory management for the growing agent."""

import json
import os
from pathlib import Path
from typing import Any, Dict


class Memory:
    """Manages persistent state storage for the agent."""
    
    def __init__(self, state_file: str = "data/state.json"):
        """Initialize memory with state file path.
        
        Args:
            state_file: Path to the JSON state file
        """
        self.state_file = Path(state_file)
        self._ensure_state_file()
    
    def _ensure_state_file(self) -> None:
        """Ensure state file and directory exist."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_file.exists():
            self._write_state({
                "iteration": 0,
                "history": [],
                "best_score": 0.0
            })
    
    def read_state(self) -> Dict[str, Any]:
        """Read current state from file.
        
        Returns:
            Dictionary containing the current state
        """
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not read state file: {e}")
            return {
                "iteration": 0,
                "history": [],
                "best_score": 0.0
            }
    
    def write_state(self, state: Dict[str, Any]) -> None:
        """Write state to file.
        
        Args:
            state: Dictionary containing the state to save
        """
        self._write_state(state)
    
    def _write_state(self, state: Dict[str, Any]) -> None:
        """Internal method to write state with formatting."""
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def update_state(self, **kwargs) -> None:
        """Update specific fields in the state.
        
        Args:
            **kwargs: Key-value pairs to update in the state
        """
        state = self.read_state()
        state.update(kwargs)
        self.write_state(state)
    
    def add_history_entry(self, entry: Dict[str, Any]) -> None:
        """Add an entry to the history.
        
        Args:
            entry: Dictionary containing history entry data
        """
        state = self.read_state()
        if "history" not in state:
            state["history"] = []
        state["history"].append(entry)
        self.write_state(state)
    
    def get_iteration(self) -> int:
        """Get current iteration number.
        
        Returns:
            Current iteration number
        """
        return self.read_state().get("iteration", 0)
    
    def increment_iteration(self) -> int:
        """Increment and return the new iteration number.
        
        Returns:
            New iteration number
        """
        state = self.read_state()
        state["iteration"] = state.get("iteration", 0) + 1
        self.write_state(state)
        return state["iteration"]
