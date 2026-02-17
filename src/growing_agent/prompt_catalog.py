from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any


PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _normalize_alias(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def _render_template(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            key = str(match.group(1))
            if key not in variables:
                return match.group(0)
            return str(variables[key])

        return PLACEHOLDER_PATTERN.sub(replace, value)

    if isinstance(value, list):
        return [_render_template(item, variables) for item in value]

    if isinstance(value, dict):
        return {str(key): _render_template(item, variables) for key, item in value.items()}

    return value


@dataclass(frozen=True)
class PromptCatalog:
    app_aliases: dict[str, str]
    browser_aliases: set[str]
    browser_launch_profiles: tuple[tuple[set[str], tuple[str, ...]], ...]
    default_browser_commands: tuple[str, ...]
    platform_aliases: dict[str, tuple[str, ...]]
    platform_url_templates: dict[str, str]
    workflows: dict[str, list[dict[str, Any]]]
    handler_order: tuple[str, ...]

    def resolve_app(self, app_name: str) -> tuple[str, bool]:
        normalized = _normalize_alias(app_name)
        resolved = self.app_aliases.get(normalized, app_name.strip())
        resolved_normalized = _normalize_alias(resolved)
        is_browser = bool(
            normalized in self.browser_aliases
            or resolved_normalized in self.browser_aliases
            or "browser" in normalized
            or "ブラウザ" in app_name
        )
        return resolved, is_browser

    def browser_commands_for_prompt(self, normalized_prompt: str) -> list[str]:
        for aliases, commands in self.browser_launch_profiles:
            if any(alias in normalized_prompt for alias in aliases):
                return list(commands)
        if self.default_browser_commands:
            return list(self.default_browser_commands)
        for _aliases, commands in self.browser_launch_profiles:
            if commands:
                return list(commands)
        return ["google-chrome", "chromium-browser", "chromium"]

    def canonical_platform(self, value: str) -> str | None:
        normalized = _normalize_alias(value)
        for platform, aliases in self.platform_aliases.items():
            if normalized in aliases:
                return platform
        return None

    def platform_alias_tokens(self) -> list[str]:
        tokens: list[str] = []
        for aliases in self.platform_aliases.values():
            tokens.extend(list(aliases))
        return tokens

    def render_workflow(self, workflow_id: str, variables: dict[str, Any]) -> list[dict[str, Any]]:
        templates = self.workflows.get(workflow_id, [])
        rendered = _render_template(templates, variables)
        if not isinstance(rendered, list):
            return []
        normalized_steps: list[dict[str, Any]] = []
        for item in rendered:
            if isinstance(item, dict):
                normalized_steps.append(item)
        return normalized_steps


def _load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid catalog file: {path} ({error})") from error
    if not isinstance(payload, dict):
        raise ValueError(f"catalog file must contain a JSON object: {path}")
    return payload


def _default_catalog_dir() -> Path:
    configured = os.environ.get("GROWING_AGENT_PROMPT_CONFIG_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    return (Path(__file__).resolve().parent / "prompt_catalog").resolve()


def load_prompt_catalog(config_dir: str | Path | None = None) -> PromptCatalog:
    base_dir = Path(config_dir).expanduser().resolve() if config_dir else _default_catalog_dir()
    apps_payload = _load_json(base_dir / "apps.json", fallback={"apps": []})
    workflows_payload = _load_json(base_dir / "workflows.json", fallback={"workflows": {}})
    planner_payload = _load_json(base_dir / "planner.json", fallback={})
    platforms_payload = _load_json(base_dir / "platforms.json", fallback={})

    app_aliases: dict[str, str] = {}
    browser_aliases: set[str] = set()
    browser_profiles: list[tuple[set[str], tuple[str, ...]]] = []

    raw_apps = apps_payload.get("apps", [])
    if isinstance(raw_apps, list):
        for raw_app in raw_apps:
            if not isinstance(raw_app, dict):
                continue
            canonical = str(raw_app.get("canonical", "")).strip()
            if not canonical:
                continue
            aliases_raw = raw_app.get("aliases", [])
            aliases = {canonical}
            if isinstance(aliases_raw, list):
                aliases.update(str(item).strip() for item in aliases_raw if str(item).strip())

            normalized_aliases = {_normalize_alias(alias) for alias in aliases if _normalize_alias(alias)}
            for alias in normalized_aliases:
                app_aliases[alias] = canonical

            is_browser = bool(raw_app.get("is_browser") is True)
            if is_browser:
                browser_aliases.update(normalized_aliases)
                launch_candidates_raw = raw_app.get("launch_candidates", [])
                launch_candidates = tuple(
                    str(item).strip()
                    for item in launch_candidates_raw
                    if isinstance(item, str) and item.strip()
                )
                if launch_candidates:
                    browser_profiles.append((normalized_aliases, launch_candidates))

    workflows: dict[str, list[dict[str, Any]]] = {}
    raw_workflows = workflows_payload.get("workflows", {})
    if isinstance(raw_workflows, dict):
        for key, value in raw_workflows.items():
            workflow_key = str(key).strip()
            if not workflow_key or not isinstance(value, list):
                continue
            steps = [item for item in value if isinstance(item, dict)]
            workflows[workflow_key] = steps

    handler_order_raw = planner_payload.get("handler_order", [])
    handler_order = tuple(
        str(item).strip()
        for item in handler_order_raw
        if isinstance(item, str) and str(item).strip()
    )
    if not handler_order:
        handler_order = (
            "open_app",
            "open_url",
            "platform_search",
            "generic_search",
            "type_or_diary",
            "hotkey",
            "wait_seconds",
        )

    default_browser_commands_raw = planner_payload.get("default_browser_commands", [])
    default_browser_commands = tuple(
        str(item).strip()
        for item in default_browser_commands_raw
        if isinstance(item, str) and item.strip()
    )

    platform_aliases: dict[str, tuple[str, ...]] = {}
    raw_aliases = platforms_payload.get("aliases", {})
    if isinstance(raw_aliases, dict):
        for platform, aliases_raw in raw_aliases.items():
            key = str(platform).strip().lower()
            if not key or not isinstance(aliases_raw, list):
                continue
            aliases = tuple(
                _normalize_alias(str(item))
                for item in aliases_raw
                if isinstance(item, str) and _normalize_alias(str(item))
            )
            if aliases:
                platform_aliases[key] = aliases

    platform_url_templates: dict[str, str] = {}
    raw_templates = platforms_payload.get("search_url_templates", {})
    if isinstance(raw_templates, dict):
        for platform, template in raw_templates.items():
            key = str(platform).strip().lower()
            value = str(template).strip()
            if key and value:
                platform_url_templates[key] = value

    return PromptCatalog(
        app_aliases=app_aliases,
        browser_aliases=browser_aliases,
        browser_launch_profiles=tuple(browser_profiles),
        default_browser_commands=default_browser_commands,
        platform_aliases=platform_aliases,
        platform_url_templates=platform_url_templates,
        workflows=workflows,
        handler_order=handler_order,
    )
