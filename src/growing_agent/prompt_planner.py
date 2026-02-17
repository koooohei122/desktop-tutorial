from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import quote_plus


YOUTUBE_KEYWORDS = ("youtube", "ユーチューブ", "ようつべ", "yt")
MUSIC_KEYWORDS = (
    "music",
    "song",
    "songs",
    "playlist",
    "play",
    "流して",
    "再生",
    "曲",
    "音楽",
    "おすすめ",
    "recommend",
)

BROWSER_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("google chrome", "chrome", "クローム", "グーグルクローム"), ("google-chrome", "chromium-browser", "chromium")),
    (("microsoft edge", "edge", "エッジ"), ("microsoft-edge", "google-chrome", "chromium-browser", "chromium")),
)


@dataclass(frozen=True)
class PromptPlan:
    intent: str
    task_type: str
    title: str
    priority: int
    payload: dict[str, Any]
    preview: dict[str, Any]


def plan_prompt_task(prompt: str, priority: int = 8) -> dict[str, Any]:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    normalized = _normalize_prompt(prompt)
    if _looks_like_youtube_music_request(normalized):
        plan = _plan_youtube_music_request(prompt, normalized, priority)
        return {
            "intent": plan.intent,
            "task_type": plan.task_type,
            "title": plan.title,
            "priority": plan.priority,
            "payload": plan.payload,
            "preview": plan.preview,
        }
    raise ValueError(
        "Unsupported prompt intent. Currently supported: "
        "YouTube music play requests (e.g. open Chrome and play recommended songs)."
    )


def _normalize_prompt(prompt: str) -> str:
    lowered = prompt.strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def _looks_like_youtube_music_request(normalized: str) -> bool:
    if not any(keyword in normalized for keyword in YOUTUBE_KEYWORDS):
        return False
    return any(keyword in normalized for keyword in MUSIC_KEYWORDS)


def _plan_youtube_music_request(prompt: str, normalized: str, priority: int) -> PromptPlan:
    topic = _extract_music_topic(prompt, normalized)
    query = _build_youtube_query(topic, normalized)
    encoded_query = quote_plus(query)
    youtube_search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
    browser_commands = _browser_launch_candidates(normalized)

    launch_step, launch_on_failure = _build_browser_launch_steps(youtube_search_url, browser_commands)
    launch_step["on_failure"] = launch_on_failure
    launch_step["continue_on_failure"] = False

    mission_payload: dict[str, Any] = {
        "source_prompt": prompt,
        "intent": "youtube_music_recommendation",
        "max_step_failures": 2,
        "auto_recovery": True,
        "steps": [
            launch_step,
            {
                "task_type": "desktop_action",
                "title": "Allow browser startup",
                "payload": {"action": "wait", "seconds": 2.0},
                "continue_on_failure": True,
            },
            {
                "task_type": "desktop_action",
                "title": "Focus address bar",
                "payload": {"action": "hotkey", "keys": ["ctrl", "l"]},
                "continue_on_failure": True,
            },
            {
                "task_type": "desktop_action",
                "title": "Type YouTube search URL",
                "payload": {"action": "type_text", "text": youtube_search_url, "delay_ms": 8},
                "continue_on_failure": True,
            },
            {
                "task_type": "desktop_action",
                "title": "Open YouTube search",
                "payload": {"action": "hotkey", "keys": ["Return"]},
                "continue_on_failure": True,
            },
            {
                "task_type": "desktop_action",
                "title": "Wait for search results",
                "payload": {"action": "wait", "seconds": 2.0},
                "continue_on_failure": True,
            },
            {
                "task_type": "desktop_action",
                "title": "Jump to first playable item",
                "payload": {"action": "hotkey", "keys": ["Tab"]},
                "continue_on_failure": True,
            },
            {
                "task_type": "desktop_action",
                "title": "Open selected item",
                "payload": {"action": "hotkey", "keys": ["Return"]},
                "continue_on_failure": True,
            },
            {
                "task_type": "desktop_action",
                "title": "Ensure playback keypress",
                "payload": {"action": "hotkey", "keys": ["k"]},
                "continue_on_failure": True,
            },
            {
                "task_type": "desktop_perception",
                "title": "Capture playback confirmation",
                "payload": {
                    "capture_path": "data/autonomy/prompt-youtube-result.png",
                    "ocr": False,
                },
                "continue_on_failure": True,
            },
        ],
    }

    safe_priority = max(1, min(10, int(priority)))
    title_topic = topic.strip() or query
    title = f"Prompt mission: play YouTube '{title_topic}'"
    return PromptPlan(
        intent="youtube_music_recommendation",
        task_type="mission",
        title=title,
        priority=safe_priority,
        payload=mission_payload,
        preview={
            "query": query,
            "search_url": youtube_search_url,
            "browser_commands": browser_commands,
            "note": "Best effort mission; GUI layout differences may require tuning.",
        },
    )


def _extract_music_topic(prompt: str, normalized: str) -> str:
    original = prompt.strip()
    jp_match = re.search(r"(.+?)をyoutube", original, flags=re.IGNORECASE)
    if jp_match:
        candidate = _sanitize_topic_phrase(jp_match.group(1))
        if candidate:
            return candidate

    en_match = re.search(
        r"(?:play|search|find)\s+(.+?)\s+(?:on|in)\s+youtube",
        normalized,
        flags=re.IGNORECASE,
    )
    if en_match:
        candidate = _sanitize_topic_phrase(en_match.group(1))
        if candidate:
            return candidate

    if "今日" in original or "today" in normalized:
        return "today recommended songs"
    return "recommended songs"


def _build_youtube_query(topic: str, normalized: str) -> str:
    cleaned = topic.strip()
    if not cleaned:
        cleaned = "recommended songs"
    if "おすすめ" in cleaned or "recommend" in cleaned or "recommended" in cleaned:
        return cleaned
    if "今日" in cleaned or "today" in normalized:
        return f"{cleaned} おすすめ 曲"
    return f"{cleaned} songs"


def _sanitize_topic_phrase(value: str) -> str:
    cleaned = value.strip(" \t,、。.!?;:")
    if "、" in cleaned:
        cleaned = cleaned.split("、")[-1].strip()
    if "," in cleaned:
        cleaned = cleaned.split(",")[-1].strip()

    cleaned = re.sub(
        r"^(?:open|launch|start)\s+(?:google\s*chrome|chrome|chromium|browser)\s*(?:and|then)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(?:google\s*chrome|chrome|chromium|microsoft\s*edge|edge)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(?:グーグルクローム|クローム|エッジ)\s*", "", cleaned)
    cleaned = re.sub(r"^(?:を)?(?:開いて|ひらいて|起動して)\s*", "", cleaned)
    cleaned = cleaned.strip(" \t,、。")
    return cleaned


def _browser_launch_candidates(normalized: str) -> list[str]:
    for hints, commands in BROWSER_HINTS:
        if any(hint in normalized for hint in hints):
            return list(commands)
    return ["google-chrome", "chromium-browser", "chromium"]


def _build_browser_launch_steps(url: str, commands: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not commands:
        commands = ["xdg-open"]
    primary = commands[0]
    launch_step: dict[str, Any] = {
        "task_type": "command",
        "title": f"Launch browser ({primary})",
        "payload": {"command": [primary, url]},
        "priority": 8,
    }
    on_failure: list[dict[str, Any]] = []
    for fallback in commands[1:]:
        on_failure.append(
            {
                "task_type": "command",
                "title": f"Fallback browser launch ({fallback})",
                "payload": {"command": [fallback, url]},
                "priority": 7,
            }
        )
    on_failure.append(
        {
            "task_type": "desktop_action",
            "title": "Fallback open_url launch",
            "payload": {"action": "open_url", "url": url},
            "priority": 7,
        }
    )
    return launch_step, on_failure
