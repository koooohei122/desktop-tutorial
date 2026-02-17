from __future__ import annotations

from datetime import date
from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import quote_plus

from .prompt_catalog import PromptCatalog, load_prompt_catalog
from .prompt_registry import PromptHandlerRegistry, load_prompt_plugins


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
WRITE_HINT_KEYWORDS = ("write", "書いて", "書く", "つけて", "残して")
DIARY_HINT_KEYWORDS = ("diary", "journal", "日記")

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
class PromptPlan:
    intent: str
    task_type: str
    title: str
    priority: int
    payload: dict[str, Any]
    preview: dict[str, Any]


@dataclass
class GenericPlannerState:
    catalog: PromptCatalog
    prompt: str
    normalized_prompt: str
    clauses: list[str]
    steps: list[dict[str, Any]]
    preview_actions: list[dict[str, Any]]
    browser_commands: list[str]
    browser_opened: bool = False
    browser_session_ready: bool = False
    browser_hint: bool = False


def plan_prompt_task(
    prompt: str,
    priority: int = 8,
    catalog_dir: str | None = None,
    plugin_paths: list[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    normalized = _normalize_prompt(prompt)
    catalog = load_prompt_catalog(catalog_dir)

    if _looks_like_youtube_music_request(normalized):
        specialized = _plan_youtube_music_request(prompt, normalized, priority, catalog)
        return _plan_to_dict(specialized)

    generic = _plan_generic_prompt_request(
        prompt=prompt,
        normalized=normalized,
        priority=priority,
        catalog=catalog,
        plugin_paths=plugin_paths,
    )
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


def _plan_youtube_music_request(
    prompt: str,
    normalized: str,
    priority: int,
    catalog: PromptCatalog,
) -> PromptPlan:
    topic = _extract_music_topic(prompt, normalized)
    query = _build_youtube_query(topic, normalized)
    browser_commands = _browser_launch_candidates(normalized, catalog)
    search_url = _build_platform_search_url("youtube", query, catalog)

    steps, _launched = _build_platform_search_steps(
        platform="youtube",
        query=query,
        wants_play=True,
        browser_commands=browser_commands,
        launch_browser=True,
        use_address_bar_navigation=False,
        catalog=catalog,
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


def _plan_generic_prompt_request(
    prompt: str,
    normalized: str,
    priority: int,
    catalog: PromptCatalog,
    plugin_paths: list[str] | None,
) -> PromptPlan | None:
    clauses = _split_prompt_into_clauses(prompt)
    if not clauses:
        clauses = [prompt.strip()]

    state = GenericPlannerState(
        catalog=catalog,
        prompt=prompt,
        normalized_prompt=normalized,
        clauses=clauses,
        steps=[],
        preview_actions=[],
        browser_commands=_browser_launch_candidates(normalized, catalog),
        browser_opened=False,
        browser_session_ready=False,
        browser_hint=_prompt_mentions_browser(normalized, catalog),
    )
    registry = _build_generic_handler_registry(catalog, plugin_paths)

    for index, clause in enumerate(clauses, start=1):
        clause_text = clause.strip()
        if not clause_text:
            continue
        clause_norm = _normalize_prompt(clause_text)
        for handler_name in registry.ordered_names():
            handler = registry.get(handler_name)
            handler(state, clause_text, clause_norm, index)

    if not state.steps:
        return None

    safe_priority = max(1, min(10, int(priority)))
    payload: dict[str, Any] = {
        "source_prompt": prompt,
        "intent": "generic_prompt_workflow",
        "max_step_failures": 2,
        "auto_recovery": True,
        "steps": state.steps,
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
            "actions": state.preview_actions,
            "action_count": len(state.preview_actions),
            "note": "Parsed with heuristic prompt planner.",
        },
    )


def _build_generic_handler_registry(
    catalog: PromptCatalog,
    plugin_paths: list[str] | None,
) -> PromptHandlerRegistry:
    registry = PromptHandlerRegistry(preferred_order=list(catalog.handler_order))
    registry.register("open_app", _handle_open_app)
    registry.register("open_url", _handle_open_url)
    registry.register("platform_search", _handle_platform_search)
    registry.register("generic_search", _handle_generic_search)
    registry.register("type_or_diary", _handle_type_or_diary)
    registry.register("hotkey", _handle_hotkey)
    registry.register("wait_seconds", _handle_wait_seconds)
    try:
        load_prompt_plugins(registry, plugin_paths)
    except Exception as error:
        raise ValueError(f"failed to load prompt plugins: {error}") from error
    return registry


def _handle_open_app(state: GenericPlannerState, clause_text: str, clause_normalized: str, clause_index: int) -> None:
    open_app_request = _extract_open_app_request(clause_text, clause_normalized, state.catalog)
    if open_app_request is None:
        return
    app_name_raw, browser_hint = open_app_request
    app_name, browser_from_catalog = state.catalog.resolve_app(app_name_raw)
    is_browser_app = bool(browser_hint or browser_from_catalog)

    workflow_steps = state.catalog.render_workflow("open_app", {"app_name": app_name})
    if not workflow_steps:
        workflow_steps = [_build_launch_app_step(app_name=app_name, title=f"Open app ({app_name})")]
    state.steps.extend(workflow_steps)
    state.preview_actions.append({"clause_index": clause_index, "action": "open_app", "app": app_name})

    if is_browser_app:
        state.browser_opened = True
        state.browser_session_ready = True


def _handle_open_url(state: GenericPlannerState, clause_text: str, _clause_normalized: str, clause_index: int) -> None:
    for url in _extract_urls(clause_text):
        state.steps.append(
            {
                "task_type": "desktop_action",
                "title": f"Open URL ({url[:60]})",
                "payload": {"action": "open_url", "url": url},
                "continue_on_failure": True,
            }
        )
        state.preview_actions.append({"clause_index": clause_index, "action": "open_url", "url": url})
        state.browser_opened = True


def _handle_platform_search(
    state: GenericPlannerState,
    clause_text: str,
    clause_normalized: str,
    clause_index: int,
) -> None:
    search_request = _extract_platform_search_request(clause_text, clause_normalized, state.catalog)
    if search_request is None:
        return
    platform, query, wants_play = search_request
    search_steps, launched = _build_platform_search_steps(
        platform=platform,
        query=query,
        wants_play=wants_play,
        browser_commands=state.browser_commands,
        launch_browser=bool(state.browser_hint and not state.browser_opened),
        use_address_bar_navigation=bool(state.browser_session_ready),
        catalog=state.catalog,
    )
    state.steps.extend(search_steps)
    state.preview_actions.append(
        {
            "clause_index": clause_index,
            "action": "platform_search",
            "platform": platform,
            "query": query,
            "wants_play": wants_play,
        }
    )
    if launched:
        state.browser_opened = True
        state.browser_session_ready = True
    else:
        state.browser_opened = True


def _handle_generic_search(
    state: GenericPlannerState,
    clause_text: str,
    clause_normalized: str,
    clause_index: int,
) -> None:
    generic_query = _extract_generic_search_query(clause_text, clause_normalized, state.catalog)
    if not generic_query:
        return
    search_steps, launched = _build_platform_search_steps(
        platform="google",
        query=generic_query,
        wants_play=False,
        browser_commands=state.browser_commands,
        launch_browser=bool(state.browser_hint and not state.browser_opened),
        use_address_bar_navigation=bool(state.browser_session_ready),
        catalog=state.catalog,
    )
    state.steps.extend(search_steps)
    state.preview_actions.append(
        {
            "clause_index": clause_index,
            "action": "generic_search",
            "platform": "google",
            "query": generic_query,
        }
    )
    if launched:
        state.browser_opened = True
        state.browser_session_ready = True
    else:
        state.browser_opened = True


def _handle_type_or_diary(
    state: GenericPlannerState,
    clause_text: str,
    clause_normalized: str,
    clause_index: int,
) -> None:
    typed_text = _extract_type_text(clause_text, clause_normalized)
    if typed_text:
        state.steps.append(
            {
                "task_type": "desktop_action",
                "title": "Type requested text",
                "payload": {"action": "type_text", "text": typed_text, "delay_ms": 10},
                "continue_on_failure": True,
            }
        )
        state.preview_actions.append(
            {"clause_index": clause_index, "action": "type_text", "text_excerpt": typed_text[:80]}
        )
        return

    diary_text = _extract_diary_text_template(clause_text, clause_normalized)
    if diary_text:
        state.steps.append(
            {
                "task_type": "desktop_action",
                "title": "Write diary template",
                "payload": {"action": "type_text", "text": diary_text, "delay_ms": 12},
                "continue_on_failure": True,
            }
        )
        state.preview_actions.append(
            {
                "clause_index": clause_index,
                "action": "write_diary_template",
                "text_excerpt": diary_text[:80],
            }
        )


def _handle_hotkey(
    state: GenericPlannerState,
    clause_text: str,
    clause_normalized: str,
    clause_index: int,
) -> None:
    hotkey = _extract_hotkey(clause_text, clause_normalized)
    if not hotkey:
        return
    state.steps.append(
        {
            "task_type": "desktop_action",
            "title": "Press requested hotkey",
            "payload": {"action": "hotkey", "keys": hotkey},
            "continue_on_failure": True,
        }
    )
    state.preview_actions.append({"clause_index": clause_index, "action": "hotkey", "keys": hotkey})


def _handle_wait_seconds(
    state: GenericPlannerState,
    clause_text: str,
    clause_normalized: str,
    clause_index: int,
) -> None:
    wait_seconds = _extract_wait_seconds(clause_text, clause_normalized)
    if wait_seconds is None:
        return
    state.steps.append(
        {
            "task_type": "desktop_action",
            "title": f"Wait {wait_seconds:.2f}s",
            "payload": {"action": "wait", "seconds": wait_seconds},
            "continue_on_failure": True,
        }
    )
    state.preview_actions.append({"clause_index": clause_index, "action": "wait", "seconds": wait_seconds})


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


def _prompt_mentions_browser(normalized: str, catalog: PromptCatalog) -> bool:
    if "browser" in normalized or "ブラウザ" in normalized:
        return True
    for alias in catalog.browser_aliases:
        if alias and alias in normalized:
            return True
    return False


def _extract_open_app_request(
    clause_text: str,
    clause_normalized: str,
    catalog: PromptCatalog,
) -> tuple[str, bool] | None:
    if not any(keyword in clause_normalized for keyword in OPEN_HINT_KEYWORDS):
        return None

    english = re.search(
        r"(?:open|launch|start)\s+(?P<app>.+)",
        clause_text,
        flags=re.IGNORECASE,
    )
    if english:
        app_name = _sanitize_app_name(str(english.group("app")))
        if app_name:
            return app_name, _looks_like_browser_app(app_name, catalog)

    japanese = re.search(
        r"(?P<app>.+?)(?:を)?(?:開いて|ひらいて|開く|起動して|起動|立ち上げて|立ち上げる)",
        clause_text,
        flags=re.IGNORECASE,
    )
    if japanese:
        app_name = _sanitize_app_name(str(japanese.group("app")))
        if app_name:
            return app_name, _looks_like_browser_app(app_name, catalog)

    if "browser" in clause_normalized or "ブラウザ" in clause_text:
        return "browser", True
    return None


def _sanitize_app_name(value: str) -> str:
    cleaned = value.strip(" \t,、。.!?;:()[]{}\"'“”")
    cleaned = re.sub(
        r"\s+to\s+(?:search|find|look|play|open|launch|start).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+(?:and|then)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(?:app|application|software)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" \t,、。.!?;:()[]{}\"'“”")
    return cleaned


def _looks_like_browser_app(app_name: str, catalog: PromptCatalog) -> bool:
    normalized = _normalize_prompt(app_name)
    if not normalized:
        return False
    if "browser" in normalized or "ブラウザ" in app_name:
        return True
    _resolved, is_browser = catalog.resolve_app(app_name)
    return is_browser


def _extract_urls(clause_text: str) -> list[str]:
    return [match.group(0).strip() for match in URL_PATTERN.finditer(clause_text)]


def _extract_platform_search_request(
    clause_text: str,
    clause_normalized: str,
    catalog: PromptCatalog,
) -> tuple[str, str, bool] | None:
    alias_tokens = sorted(
        {alias for aliases in catalog.platform_aliases.values() for alias in aliases if alias},
        key=len,
        reverse=True,
    )
    platform_pattern = "|".join(re.escape(token) for token in alias_tokens)
    if not platform_pattern:
        platform_pattern = "youtube|google|github|wikipedia|bing"

    english = re.search(
        rf"(?:search|find|look up|play)\s+(?P<query>.+?)\s+(?:on|in)\s+"
        rf"(?P<platform>{platform_pattern})",
        clause_normalized,
        flags=re.IGNORECASE,
    )
    if english:
        platform = _canonical_platform(str(english.group("platform")), catalog)
        query = _sanitize_topic_phrase(str(english.group("query")))
        wants_play = "play" in clause_normalized or (
            platform == "youtube" and any(keyword in clause_normalized for keyword in PLAY_KEYWORDS)
        )
        if platform and query:
            return platform, query, wants_play

    jp_patterns = [
        re.compile(
            rf"(?P<query>.+?)を(?P<platform>{platform_pattern})"
            r"(?:で)?(?P<verb>検索|探して|調べて|再生|流して|再生して|見つけて)?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"(?P<platform>{platform_pattern})"
            r"(?:で)(?P<query>.+?)(?P<verb>検索|探して|調べて|再生|流して|再生して|見つけて)",
            flags=re.IGNORECASE,
        ),
    ]
    for pattern in jp_patterns:
        matched = pattern.search(clause_text)
        if not matched:
            continue
        platform = _canonical_platform(str(matched.group("platform")), catalog)
        query = _sanitize_topic_phrase(str(matched.group("query")))
        verb = str(matched.groupdict().get("verb", ""))
        wants_play = bool(
            any(token in verb for token in ("再生", "流"))
            or (platform == "youtube" and any(keyword in clause_normalized for keyword in PLAY_KEYWORDS))
        )
        if platform and query:
            return platform, query, wants_play

    for platform, aliases in catalog.platform_aliases.items():
        if not any(alias in clause_normalized for alias in aliases):
            continue
        if platform == "youtube" and any(keyword in clause_normalized for keyword in PLAY_KEYWORDS):
            guessed = _extract_music_topic(clause_text, clause_normalized)
            if guessed:
                return "youtube", guessed, True
    return None


def _extract_generic_search_query(
    clause_text: str,
    clause_normalized: str,
    catalog: PromptCatalog,
) -> str | None:
    if any(alias in clause_normalized for alias in catalog.platform_alias_tokens()):
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


def _extract_diary_text_template(clause_text: str, clause_normalized: str) -> str | None:
    if not any(keyword in clause_normalized for keyword in DIARY_HINT_KEYWORDS):
        return None
    if not any(keyword in clause_normalized or keyword in clause_text for keyword in WRITE_HINT_KEYWORDS):
        return None

    today = date.today().isoformat()
    if _contains_japanese(clause_text):
        return (
            f"{today} 日記\n"
            "- 今日の出来事:\n"
            "- 良かったこと:\n"
            "- 明日やること:\n"
        )
    return (
        f"{today} Diary\n"
        "- What happened today:\n"
        "- What went well:\n"
        "- Plan for tomorrow:\n"
    )


def _contains_japanese(text: str) -> bool:
    return bool(re.search(r"[ぁ-んァ-ン一-龥]", text))


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


def _canonical_platform(value: str, catalog: PromptCatalog) -> str | None:
    return catalog.canonical_platform(value)


def _build_platform_search_url(platform: str, query: str, catalog: PromptCatalog) -> str:
    template = catalog.platform_url_templates.get(
        platform,
        catalog.platform_url_templates.get("google", "https://www.google.com/search?q={query}"),
    )
    encoded_query = quote_plus(query.strip() or "recommended")
    return template.format(query=encoded_query)


def _build_launch_app_step(app_name: str, title: str) -> dict[str, Any]:
    return {
        "task_type": "desktop_action",
        "title": title,
        "payload": {"action": "launch_app", "app_name": app_name},
        "priority": 7,
        "continue_on_failure": True,
    }


def _build_platform_search_steps(
    platform: str,
    query: str,
    wants_play: bool,
    browser_commands: list[str],
    launch_browser: bool,
    use_address_bar_navigation: bool,
    catalog: PromptCatalog,
) -> tuple[list[dict[str, Any]], bool]:
    search_url = _build_platform_search_url(platform, query, catalog)
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


def _browser_launch_candidates(normalized: str, catalog: PromptCatalog) -> list[str]:
    return catalog.browser_commands_for_prompt(normalized)


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
