from __future__ import annotations

from dataclasses import dataclass, field

from .i18n import SUPPORTED_LANGUAGES


@dataclass
class AgentConfig:
    """Runtime configuration for the growing agent."""

    iterations: int = 3
    dry_run: bool = False
    command: list[str] = field(default_factory=lambda: ["pytest", "-q"])
    target_score: float = 1.0
    stop_on_target: bool = False
    max_history: int = 200
    timeout_seconds: float = 30.0
    halt_on_error: bool = False
    language: str = "ja"

    def __post_init__(self) -> None:
        if self.iterations < 1:
            raise ValueError("iterations must be >= 1")
        if not self.command:
            raise ValueError("command must not be empty")
        if self.max_history < 1:
            raise ValueError("max_history must be >= 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if not 0.0 <= self.target_score <= 1.0:
            raise ValueError("target_score must be between 0.0 and 1.0")
        if not isinstance(self.language, str):
            raise ValueError("language must be a string")
        self.language = self.language.strip().lower()
        if self.language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"language must be one of: {', '.join(SUPPORTED_LANGUAGES)}")
