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
PLAY_KEYWORDS = ("play", "listen", "再生", "流して", "聴", "聞")
OPEN_HINT_KEYWORDS = ("open", "launch", "start", "開いて", "開く", "起動", "立ち上げ")
SEARCH_HINT_KEYWORDS = ("search", "find", "look up", "検索", "探して", "調べて", "見つけて")
TYPE_HINT_KEYWORDS = ("type", "enter", "入力", "タイプ")

BROWSER_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("google chrome", "chrome", "クローム", "グーグルクローム"), ("google-chrome", "chromium-browser", "chromium")),
    (("microsoft edge", "edge", "エッジ"), ("microsoft-edge", "google-chrome", "chromium-browser", "chromium")),
    (("firefox", "ファイアフォックス"), ("firefox", "google-chrome", "chromium-browser", "chromium")),
)

PLATFORM_ALIASES: dict[str, tuple[str, ...]] = {
    "youtube": ("youtube", "ユーチューブ", "ようつべ", "yt"),
    "google": ("google", "グーグル"),
    "github": ("github", "ギットハブ"),
    "wikipedia": ("wikipedia", "ウィキペディア"),
    "bing": ("bing", "ビング"),
}

PLATFORM_SEARCH_URL_TEMPLATES: dict[str, str] = {
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "google": "https://www.google.com/search?q={query}",
    "github": "https://github.com/search?q={query}",
    "wikipedia": "https://wikipedia.org/w/index.php?search={query}",
    "bing": "https://www.bing.com/search?q={query}",
}

URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", flags=re.IGNORECASE)

HOTKEY_ALIASES: dict[str, str] = {
    "enter": "Return",
    "return": "Return",
    "tab": "Tab",
    "esc": "Escape",
    "escape": "Escape",
    "space": "space",
    "スペース": "space",
    "エンター": "Return",
    "タブ": "Tab",
    "エスケープ": "Escape",
}


@dataclass(frozen=True)
class AppProfile:
    name: str
    keywords: tuple[str, ...]
    commands: tuple[str, ...]
    is_browser: bool = False


APP_PROFILES: tuple[AppProfile, ...] = (
    AppProfile(
        name="google-chrome",
        keywords=("google chrome", "chrome", "クローム", "グーグルクローム"),
        commands=("google-chrome", "chromium-browser", "chromium"),
        is_browser=True,
    ),
    AppProfile(
        name="microsoft-edge",
        keywords=("microsoft edge", "edge", "エッジ"),
        commands=("microsoft-edge", "google-chrome", "chromium-browser", "chromium"),
        is_browser=True,
    ),
    AppProfile(
        name="firefox",
        keywords=("firefox", "ファイアフォックス"),
        commands=("firefox",),
        is_browser=True,
    ),
    AppProfile(
        name="code",
        keywords=("vscode", "visual studio code", "vs code", "code"),
        commands=("code",),
        is_browser=False,
    ),
    AppProfile(
        name="gnome-terminal",
        keywords=("terminal", "ターミナル"),
        commands=("gnome-terminal", "x-terminal-emulator"),
        is_browser=False,
    ),
    AppProfile(
        name="slack",
        keywords=("slack",),
        commands=("slack",),
        is_browser=False,
    ),
    AppProfile(
        name="spotify",
        keywords=("spotify", "スポティファイ"),
        commands=("spotify",),
        is_browser=False,
    ),
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
        specialized = _plan_youtube_music_request(prompt, normalized, priority)
        return _plan_to_dict(specialized)

    generic = _plan_generic_prompt_request(prompt, normalized, priority)
    if generic is not None:
        return _plan_to_dict(generic)

    raise ValueError(
        "Unsupported prompt intent. Supported prompt patterns include: opening apps, opening URLs, "
        "platform search (YouTube/Google/GitHub/Wikipedia/Bing), text input, hotkeys, wait, and "
        "YouTube music playback."
    )


def _plan_to_dict(plan: PromptPlan) -> dict[str, Any]:
    return {
        "intent": plan.intent,
        "task_type": plan.task_type,
        "title": plan.title,
        "priority": plan.priority,
        "payload": plan.payload,
        "preview": plan.preview,
    }


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
    browser_commands = _browser_launch_candidates(normalized)
    search_url = _build_platform_search_url("youtube", query)

    steps, _launched = _build_platform_search_steps(
        platform="youtube",
        query=query,
        wants_play=True,
        browser_commands=browser_commands,
        launch_browser=True,
        use_address_bar_navigation=False,
    )
    steps.append(
        {
            "task_type": "desktop_perception",
            "title": "Capture playback confirmation",
            "payload": {
                "capture_path": "data/autonomy/prompt-youtube-result.png",
                "ocr": False,
            },
            "continue_on_failure": True,
        }
    )

    mission_payload: dict[str, Any] = {
        "source_prompt": prompt,
        "intent": "youtube_music_recommendation",
        "max_step_failures": 2,
        "auto_recovery": True,
        "steps": steps,
    }

    safe_priority = max(1, min(10, int(priority)))
    title_topic = topic.strip() or query
    return PromptPlan(
        intent="youtube_music_recommendation",
        task_type="mission",
        title=f"Prompt mission: play YouTube '{title_topic}'",
        priority=safe_priority,
        payload=mission_payload,
        preview={
            "query": query,
            "search_url": search_url,
            "browser_commands": browser_commands,
            "note": "Best effort mission; GUI layout differences may require tuning.",
        },
    )


def _plan_generic_prompt_request(prompt: str, normalized: str, priority: int) -> PromptPlan | None:
    clauses = _split_prompt_into_clauses(prompt)
    if not clauses:
        clauses = [prompt.strip()]

    steps: list[dict[str, Any]] = []
    preview_actions: list[dict[str, Any]] = []
    browser_commands = _browser_launch_candidates(normalized)
    browser_opened = False
    browser_session_ready = False
    browser_hint = _prompt_mentions_browser(normalized)

    for index, clause in enumerate(clauses, start=1):
        clause_text = clause.strip()
        if not clause_text:
            continue
        clause_norm = _normalize_prompt(clause_text)

        app = _extract_open_app_profile(clause_norm)
        if app is not None:
            steps.append(
                _build_app_launch_step(
                    commands=list(app.commands),
                    title=f"Open app ({app.name})",
                )
            )
            preview_actions.append(
                {"clause_index": index, "action": "open_app", "app": app.name}
            )
            if app.is_browser:
                browser_opened = True
                browser_session_ready = True

        for url in _extract_urls(clause_text):
            steps.append(
                {
                    "task_type": "desktop_action",
                    "title": f"Open URL ({url[:60]})",
                    "payload": {"action": "open_url", "url": url},
                    "continue_on_failure": True,
                }
            )
            preview_actions.append(
                {"clause_index": index, "action": "open_url", "url": url}
            )
            browser_opened = True

        search_request = _extract_platform_search_request(clause_text, clause_norm)
        if search_request is not None:
            platform, query, wants_play = search_request
            search_steps, launched = _build_platform_search_steps(
                platform=platform,
                query=query,
                wants_play=wants_play,
                browser_commands=browser_commands,
                launch_browser=bool(browser_hint and not browser_opened),
                use_address_bar_navigation=bool(browser_session_ready),
            )
            steps.extend(search_steps)
            preview_actions.append(
                {
                    "clause_index": index,
                    "action": "platform_search",
                    "platform": platform,
                    "query": query,
                    "wants_play": wants_play,
                }
            )
            if launched:
                browser_opened = True
                browser_session_ready = True
            else:
                browser_opened = True
        else:
            generic_query = _extract_generic_search_query(clause_text, clause_norm)
            if generic_query:
                search_steps, launched = _build_platform_search_steps(
                    platform="google",
                    query=generic_query,
                    wants_play=False,
                    browser_commands=browser_commands,
                    launch_browser=bool(browser_hint and not browser_opened),
                    use_address_bar_navigation=bool(browser_session_ready),
                )
                steps.extend(search_steps)
                preview_actions.append(
                    {
                        "clause_index": index,
                        "action": "generic_search",
                        "platform": "google",
                        "query": generic_query,
                    }
                )
                if launched:
                    browser_opened = True
                    browser_session_ready = True
                else:
                    browser_opened = True

        typed_text = _extract_type_text(clause_text, clause_norm)
        if typed_text:
            steps.append(
                {
                    "task_type": "desktop_action",
                    "title": "Type requested text",
                    "payload": {"action": "type_text", "text": typed_text, "delay_ms": 10},
                    "continue_on_failure": True,
                }
            )
            preview_actions.append(
                {"clause_index": index, "action": "type_text", "text_excerpt": typed_text[:80]}
            )

        hotkey = _extract_hotkey(clause_text, clause_norm)
        if hotkey:
            steps.append(
                {
                    "task_type": "desktop_action",
                    "title": "Press requested hotkey",
                    "payload": {"action": "hotkey", "keys": hotkey},
                    "continue_on_failure": True,
                }
            )
            preview_actions.append(
                {"clause_index": index, "action": "hotkey", "keys": hotkey}
            )

        wait_seconds = _extract_wait_seconds(clause_text, clause_norm)
        if wait_seconds is not None:
            steps.append(
                {
                    "task_type": "desktop_action",
                    "title": f"Wait {wait_seconds:.2f}s",
                    "payload": {"action": "wait", "seconds": wait_seconds},
                    "continue_on_failure": True,
                }
            )
            preview_actions.append(
                {"clause_index": index, "action": "wait", "seconds": wait_seconds}
            )

    if not steps:
        return None

    safe_priority = max(1, min(10, int(priority)))
    payload: dict[str, Any] = {
        "source_prompt": prompt,
        "intent": "generic_prompt_workflow",
        "max_step_failures": 2,
        "auto_recovery": True,
        "steps": steps,
    }
    shortened_prompt = prompt.strip().replace("\n", " ")
    if len(shortened_prompt) > 60:
        shortened_prompt = shortened_prompt[:57] + "..."
    return PromptPlan(
        intent="generic_prompt_workflow",
        task_type="mission",
        title=f"Prompt mission: {shortened_prompt}",
        priority=safe_priority,
        payload=payload,
        preview={
            "clauses": clauses,
            "actions": preview_actions,
            "action_count": len(preview_actions),
            "note": "Parsed with heuristic prompt planner.",
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


def _split_prompt_into_clauses(prompt: str) -> list[str]:
    text = prompt.strip()
    if not text:
        return []
    staged = text
    staged = re.sub(r"\s+(?:and then|then)\s+", " || ", staged, flags=re.IGNORECASE)
    staged = re.sub(r"\s+and\s+", " || ", staged, flags=re.IGNORECASE)
    staged = re.sub(r"(?:してから|したあとで|した後で)\s*", " || ", staged)
    staged = staged.replace("。", "||")
    staged = staged.replace("、", "||")
    staged = staged.replace(",", "||")
    staged = staged.replace("->", "||")
    staged = staged.replace("\n", "||")
    parts = [part.strip() for part in staged.split("||") if part.strip()]
    return parts if parts else [text]


def _prompt_mentions_browser(normalized: str) -> bool:
    if "browser" in normalized or "ブラウザ" in normalized:
        return True
    for hints, _commands in BROWSER_HINTS:
        if any(hint in normalized for hint in hints):
            return True
    return False


def _extract_open_app_profile(clause_normalized: str) -> AppProfile | None:
    if not any(keyword in clause_normalized for keyword in OPEN_HINT_KEYWORDS):
        return None
    for profile in APP_PROFILES:
        if any(keyword in clause_normalized for keyword in profile.keywords):
            return profile
    if "browser" in clause_normalized or "ブラウザ" in clause_normalized:
        return APP_PROFILES[0]
    return None


def _extract_urls(clause_text: str) -> list[str]:
    return [match.group(0).strip() for match in URL_PATTERN.finditer(clause_text)]


def _extract_platform_search_request(
    clause_text: str,
    clause_normalized: str,
) -> tuple[str, str, bool] | None:
    english = re.search(
        r"(?:search|find|look up|play)\s+(?P<query>.+?)\s+(?:on|in)\s+"
        r"(?P<platform>youtube|google|github|wikipedia|bing)",
        clause_normalized,
        flags=re.IGNORECASE,
    )
    if english:
        platform = _canonical_platform(str(english.group("platform")))
        query = _sanitize_topic_phrase(str(english.group("query")))
        wants_play = "play" in clause_normalized or (
            platform == "youtube" and any(keyword in clause_normalized for keyword in PLAY_KEYWORDS)
        )
        if platform and query:
            return platform, query, wants_play

    jp_patterns = [
        re.compile(
            r"(?P<query>.+?)を(?P<platform>youtube|ユーチューブ|ようつべ|google|グーグル|github|ギットハブ|wikipedia|ウィキペディア|bing|ビング)"
            r"(?:で)?(?P<verb>検索|探して|調べて|再生|流して|再生して|見つけて)?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"(?P<platform>youtube|ユーチューブ|ようつべ|google|グーグル|github|ギットハブ|wikipedia|ウィキペディア|bing|ビング)"
            r"(?:で)(?P<query>.+?)(?P<verb>検索|探して|調べて|再生|流して|再生して|見つけて)",
            flags=re.IGNORECASE,
        ),
    ]
    for pattern in jp_patterns:
        matched = pattern.search(clause_text)
        if not matched:
            continue
        platform = _canonical_platform(str(matched.group("platform")))
        query = _sanitize_topic_phrase(str(matched.group("query")))
        verb = str(matched.groupdict().get("verb", ""))
        wants_play = bool(
            any(token in verb for token in ("再生", "流"))
            or (platform == "youtube" and any(keyword in clause_normalized for keyword in PLAY_KEYWORDS))
        )
        if platform and query:
            return platform, query, wants_play

    for platform, aliases in PLATFORM_ALIASES.items():
        if not any(alias in clause_normalized for alias in aliases):
            continue
        if platform == "youtube" and any(keyword in clause_normalized for keyword in PLAY_KEYWORDS):
            guessed = _extract_music_topic(clause_text, clause_normalized)
            if guessed:
                return "youtube", guessed, True
    return None


def _extract_generic_search_query(clause_text: str, clause_normalized: str) -> str | None:
    if any(alias in clause_normalized for aliases in PLATFORM_ALIASES.values() for alias in aliases):
        return None
    if not any(keyword in clause_normalized for keyword in SEARCH_HINT_KEYWORDS):
        return None

    jp_match = re.search(r"(?P<query>.+?)を検索", clause_text, flags=re.IGNORECASE)
    if jp_match:
        query = _sanitize_topic_phrase(str(jp_match.group("query")))
        if query:
            return query

    en_match = re.search(
        r"(?:search|find|look up)\s+(?P<query>.+)",
        clause_normalized,
        flags=re.IGNORECASE,
    )
    if en_match:
        query = _sanitize_topic_phrase(str(en_match.group("query")))
        if query:
            return query
    return None


def _extract_type_text(clause_text: str, clause_normalized: str) -> str | None:
    quoted = re.search(
        r"[\"'「『](?P<text>.+?)[\"'」』]\s*(?:と)?(?:入力|タイプ|type|enter)",
        clause_text,
        flags=re.IGNORECASE,
    )
    if quoted:
        text = str(quoted.group("text")).strip()
        if text:
            return text

    if not any(keyword in clause_normalized for keyword in TYPE_HINT_KEYWORDS):
        return None
    en = re.search(
        r"(?:type|enter)\s+(?P<text>[^,.;]+)",
        clause_normalized,
        flags=re.IGNORECASE,
    )
    if en:
        text = str(en.group("text")).strip(" \t\"'")
        if text and " key" not in text:
            return text
    return None


def _extract_hotkey(clause_text: str, clause_normalized: str) -> list[str] | None:
    combo = re.search(
        r"(?:press|押して)\s+(?P<keys>(?:ctrl|alt|shift|cmd|meta)\s*\+\s*[a-z0-9]+)",
        clause_normalized,
        flags=re.IGNORECASE,
    )
    if combo:
        raw = str(combo.group("keys")).replace(" ", "")
        tokens = [token.strip() for token in raw.split("+") if token.strip()]
        if tokens:
            return [_normalize_hotkey_token(token) for token in tokens]

    if "押" not in clause_text and "press" not in clause_normalized:
        return None
    for token, key_name in HOTKEY_ALIASES.items():
        if token.lower() in clause_normalized or token in clause_text:
            return [key_name]
    return None


def _normalize_hotkey_token(token: str) -> str:
    normalized = token.strip().lower()
    if normalized in HOTKEY_ALIASES:
        return HOTKEY_ALIASES[normalized]
    return normalized


def _extract_wait_seconds(clause_text: str, clause_normalized: str) -> float | None:
    jp = re.search(r"(?P<seconds>\d+(?:\.\d+)?)\s*秒", clause_text)
    if jp and ("待" in clause_text or "wait" in clause_normalized):
        return max(0.0, min(30.0, float(jp.group("seconds"))))
    en = re.search(
        r"(?:wait|sleep)\s+(?P<seconds>\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds)?",
        clause_normalized,
    )
    if en:
        return max(0.0, min(30.0, float(en.group("seconds"))))
    return None


def _canonical_platform(value: str) -> str | None:
    normalized = value.strip().lower()
    for platform, aliases in PLATFORM_ALIASES.items():
        if normalized in aliases:
            return platform
    return None


def _build_platform_search_url(platform: str, query: str) -> str:
    template = PLATFORM_SEARCH_URL_TEMPLATES.get(platform, PLATFORM_SEARCH_URL_TEMPLATES["google"])
    encoded_query = quote_plus(query.strip() or "recommended")
    return template.format(query=encoded_query)


def _build_app_launch_step(commands: list[str], title: str) -> dict[str, Any]:
    launch_step: dict[str, Any] = {
        "task_type": "command",
        "title": title,
        "payload": {"command": [commands[0]]},
        "priority": 7,
        "continue_on_failure": True,
    }
    on_failure: list[dict[str, Any]] = []
    for fallback in commands[1:]:
        on_failure.append(
            {
                "task_type": "command",
                "title": f"{title} fallback ({fallback})",
                "payload": {"command": [fallback]},
                "priority": 6,
            }
        )
    if on_failure:
        launch_step["on_failure"] = on_failure
    return launch_step


def _build_platform_search_steps(
    platform: str,
    query: str,
    wants_play: bool,
    browser_commands: list[str],
    launch_browser: bool,
    use_address_bar_navigation: bool,
) -> tuple[list[dict[str, Any]], bool]:
    search_url = _build_platform_search_url(platform, query)
    steps: list[dict[str, Any]] = []
    launched = False

    if launch_browser:
        launch_step, on_failure = _build_browser_launch_steps(search_url, browser_commands)
        launch_step["on_failure"] = on_failure
        launch_step["continue_on_failure"] = False
        steps.append(launch_step)
        launched = True
    elif use_address_bar_navigation:
        steps.extend(
            [
                {
                    "task_type": "desktop_action",
                    "title": "Wait for browser focus",
                    "payload": {"action": "wait", "seconds": 1.0},
                    "continue_on_failure": True,
                },
                {
                    "task_type": "desktop_action",
                    "title": "Focus browser address bar",
                    "payload": {"action": "hotkey", "keys": ["ctrl", "l"]},
                    "continue_on_failure": True,
                },
                {
                    "task_type": "desktop_action",
                    "title": f"Type {platform} search URL",
                    "payload": {"action": "type_text", "text": search_url, "delay_ms": 8},
                    "continue_on_failure": True,
                },
                {
                    "task_type": "desktop_action",
                    "title": "Open typed search URL",
                    "payload": {"action": "hotkey", "keys": ["Return"]},
                    "continue_on_failure": True,
                },
            ]
        )
    else:
        steps.append(
            {
                "task_type": "desktop_action",
                "title": f"Open {platform} search URL",
                "payload": {"action": "open_url", "url": search_url},
                "continue_on_failure": True,
            }
        )

    if platform == "youtube" and wants_play:
        steps.extend(
            [
                {
                    "task_type": "desktop_action",
                    "title": "Wait for YouTube search results",
                    "payload": {"action": "wait", "seconds": 2.0},
                    "continue_on_failure": True,
                },
                {
                    "task_type": "desktop_action",
                    "title": "Move focus to first playable item",
                    "payload": {"action": "hotkey", "keys": ["Tab"]},
                    "continue_on_failure": True,
                },
                {
                    "task_type": "desktop_action",
                    "title": "Open selected YouTube item",
                    "payload": {"action": "hotkey", "keys": ["Return"]},
                    "continue_on_failure": True,
                },
                {
                    "task_type": "desktop_action",
                    "title": "Toggle YouTube playback",
                    "payload": {"action": "hotkey", "keys": ["k"]},
                    "continue_on_failure": True,
                },
            ]
        )

    return steps, launched


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
