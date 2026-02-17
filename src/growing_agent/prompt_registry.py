from __future__ import annotations

from collections.abc import Callable
import importlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


PromptClauseHandler = Callable[[Any, str, str, int], None]


class PromptHandlerRegistry:
    def __init__(self, preferred_order: list[str] | tuple[str, ...] | None = None) -> None:
        self._handlers: dict[str, PromptClauseHandler] = {}
        self._preferred_order = [
            str(item).strip()
            for item in (preferred_order or [])
            if str(item).strip()
        ]

    def register(self, name: str, handler: PromptClauseHandler, replace: bool = False) -> None:
        key = str(name).strip()
        if not key:
            raise ValueError("handler name must be non-empty")
        if key in self._handlers and not replace:
            raise ValueError(f"handler '{key}' is already registered")
        self._handlers[key] = handler

    def has(self, name: str) -> bool:
        return str(name).strip() in self._handlers

    def get(self, name: str) -> PromptClauseHandler:
        key = str(name).strip()
        if key not in self._handlers:
            raise KeyError(f"handler '{key}' is not registered")
        return self._handlers[key]

    def ordered_names(self) -> list[str]:
        ordered: list[str] = []
        for item in self._preferred_order:
            if item in self._handlers and item not in ordered:
                ordered.append(item)
        for key in sorted(self._handlers.keys()):
            if key not in ordered:
                ordered.append(key)
        return ordered


def _load_module_from_file(path: Path) -> ModuleType:
    module_name = f"growing_agent_prompt_plugin_{path.stem}_{abs(hash(str(path.resolve())))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not create module spec for plugin file: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_plugin_files(plugin_path: Path) -> list[Path]:
    if plugin_path.is_file():
        return [plugin_path] if plugin_path.suffix == ".py" else []
    if not plugin_path.is_dir():
        return []
    return sorted(
        candidate
        for candidate in plugin_path.glob("*.py")
        if candidate.is_file() and candidate.name != "__init__.py"
    )


def load_prompt_plugins(registry: PromptHandlerRegistry, plugin_paths: list[str] | None) -> list[str]:
    if not plugin_paths:
        return []

    loaded: list[str] = []
    for raw in plugin_paths:
        entry = str(raw).strip()
        if not entry:
            continue
        path = Path(entry).expanduser()
        modules: list[ModuleType] = []
        if path.exists():
            for file_path in _iter_plugin_files(path):
                modules.append(_load_module_from_file(file_path))
        else:
            modules.append(importlib.import_module(entry))

        for module in modules:
            register = getattr(module, "register_prompt_handlers", None)
            if not callable(register):
                raise ValueError(
                    f"prompt plugin module '{module.__name__}' must define register_prompt_handlers(registry)"
                )
            register(registry)
            loaded.append(module.__name__)
    return loaded
