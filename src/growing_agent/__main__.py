from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .autonomy import (
    DEFAULT_AUTONOMY_ALLOWED_COMMANDS,
    SUPPORTED_AUTONOMY_TASKS,
    AutonomousWorker,
)
from .config import AgentConfig
from .i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, translate
from .memory import MemoryStore
from .orchestrator import GrowingAgentOrchestrator
from .prompt_planner import plan_prompt_task
from .tools.runner import CommandRunner

WINDOW_TITLE_ACTIONS = {"focus_window", "hotkey", "type_text", "click", "move", "screenshot"}
WINDOW_TITLE_REQUIRED_ACTIONS = {"focus_window"}
TEXT_INPUT_ACTIONS = {"hotkey", "type_text"}
RELATIVE_COORDINATE_ACTIONS = {"click", "move"}
WINDOW_MATCH_MODE_CHOICES = ("smart", "exact", "contains", "regex")


def parse_language_arg(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_LANGUAGES:
        raise argparse.ArgumentTypeError(
            f"unsupported language '{value}'. choose from {', '.join(SUPPORTED_LANGUAGES)}"
        )
    return normalized


def add_language_argument(parser: argparse.ArgumentParser, required: bool = False) -> None:
    parser.add_argument(
        "--language",
        type=parse_language_arg,
        default=None if not required else argparse.SUPPRESS,
        required=required,
        help=f"Output/state language ({'/'.join(SUPPORTED_LANGUAGES)}).",
    )


def parse_payload_json(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"payload-json must be valid JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise ValueError("payload-json must be a JSON object")
    return payload


def parse_steps_json(value: str) -> list[dict[str, Any]]:
    try:
        steps = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"steps-json must be valid JSON: {error.msg}") from error
    if not isinstance(steps, list):
        raise ValueError("steps-json must be a JSON array")
    normalized = [item for item in steps if isinstance(item, dict)]
    if len(normalized) != len(steps):
        raise ValueError("each step in steps-json must be a JSON object")
    return normalized


def build_desktop_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {"action": args.action}
    window_title = str(args.window_title).strip() if isinstance(args.window_title, str) else ""
    window_class = str(args.window_class).strip() if isinstance(args.window_class, str) else ""
    window_pid: int | None = None
    raw_window_pid = args.window_pid
    if raw_window_pid is not None:
        try:
            parsed_pid = int(raw_window_pid)
        except (TypeError, ValueError) as error:
            raise ValueError("--window-pid must be a positive integer") from error
        if parsed_pid <= 0:
            raise ValueError("--window-pid must be a positive integer")
        window_pid = parsed_pid
    has_window_selector = bool(window_title or window_class or window_pid is not None)

    raw_window_index = args.window_index
    window_match_mode = str(args.window_match_mode).strip().lower()
    raw_focus_settle_ms = args.focus_settle_ms
    relative_to_window = bool(args.relative_to_window)

    if raw_window_index is not None and int(raw_window_index) < 0:
        raise ValueError("--window-index must be >= 0")
    if raw_window_index is not None and not has_window_selector:
        raise ValueError("--window-index requires --window-title or --window-class or --window-pid")
    if has_window_selector and args.action not in WINDOW_TITLE_ACTIONS:
        raise ValueError(
            f"Window selectors are only supported for actions: {', '.join(sorted(WINDOW_TITLE_ACTIONS))}"
        )
    if not has_window_selector and args.action in WINDOW_TITLE_REQUIRED_ACTIONS:
        raise ValueError("focus_window action requires --window-title or --window-class or --window-pid")
    if window_match_mode != "smart" and not window_title:
        raise ValueError("--window-match-mode requires --window-title")
    if relative_to_window and args.action not in RELATIVE_COORDINATE_ACTIONS:
        raise ValueError("--relative-to-window is only supported for click/move actions")
    if relative_to_window and not has_window_selector:
        raise ValueError("--relative-to-window requires --window-title or --window-class or --window-pid")

    if args.action in {"click", "move"}:
        if args.x is None or args.y is None:
            raise ValueError("click/move actions require --x and --y")
        payload["x"] = int(args.x)
        payload["y"] = int(args.y)
        if args.action == "click":
            payload["button"] = int(args.button)
    elif args.action == "type_text":
        if args.text is None:
            raise ValueError("type_text action requires --text")
        payload["text"] = str(args.text)
    elif args.action == "hotkey":
        if not args.keys:
            raise ValueError("hotkey action requires --keys")
        payload["keys"] = [str(item) for item in args.keys]
    elif args.action == "wait":
        if args.seconds is None:
            raise ValueError("wait action requires --seconds")
        payload["seconds"] = float(args.seconds)
    elif args.action == "screenshot":
        payload["path"] = str(args.path) if args.path else "data/autonomy/screenshot.png"
    elif args.action == "open_url":
        if args.url is None:
            raise ValueError("open_url action requires --url")
        payload["url"] = str(args.url)

    if has_window_selector:
        if window_title:
            payload["window_title"] = window_title
        if window_class:
            payload["window_class"] = window_class
        if window_pid is not None:
            payload["window_pid"] = window_pid
        payload["window_index"] = max(0, int(raw_window_index or 0))
        if window_title:
            payload["window_match_mode"] = (
                window_match_mode if window_match_mode in WINDOW_MATCH_MODE_CHOICES else "smart"
            )
        if args.action in TEXT_INPUT_ACTIONS:
            settle_ms = 120 if raw_focus_settle_ms is None else int(raw_focus_settle_ms)
            settle_ms = max(0, min(2000, settle_ms))
            payload["focus_settle_seconds"] = settle_ms / 1000.0
    if relative_to_window:
        payload["relative_to_window"] = True
    return payload


def build_fun_moment(summary: dict[str, Any], language: str) -> str:
    level_ups = int(summary.get("level_ups", 0))
    new_badges = summary.get("new_badges", [])
    if not isinstance(new_badges, list):
        new_badges = []
    valid_badges = [badge for badge in new_badges if isinstance(badge, str) and badge]

    if level_ups > 0:
        return translate("fun_level_up", language)
    if valid_badges:
        return f"{translate('fun_new_badge', language)} {', '.join(valid_badges)}"
    if int(summary.get("executed_count", 0)) == 0:
        return translate("fun_queue_empty", language)
    if int(summary.get("failure_count", 0)) == 0:
        return translate("fun_clean_run", language)
    return translate("fun_keep_going", language)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="growing_agent")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_parser = subparsers.add_parser("run", help="Run the agent loop.")
    run_parser.add_argument("--iterations", type=int, default=3)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        default=None,
        help=(
            "Command to execute in each iteration. "
            "When used, place --command at the end of the CLI arguments."
        ),
    )
    run_parser.add_argument("--state-path", default="data/state.json")
    run_parser.add_argument("--log-path", default="data/runner.log")
    run_parser.add_argument("--timeout-seconds", type=float, default=30.0)
    run_parser.add_argument("--max-history", type=int, default=200)
    run_parser.add_argument("--target-score", type=float, default=1.0)
    run_parser.add_argument("--stop-on-target", action="store_true")
    run_parser.add_argument("--halt-on-error", action="store_true")
    add_language_argument(run_parser)

    status_parser = subparsers.add_parser("status", help="Show current saved state.")
    status_parser.add_argument("--state-path", default="data/state.json")
    add_language_argument(status_parser)

    reset_parser = subparsers.add_parser("reset", help="Reset saved state.")
    reset_parser.add_argument("--state-path", default="data/state.json")
    add_language_argument(reset_parser)

    set_language_parser = subparsers.add_parser(
        "set-language",
        help="Persist preferred language in state.",
    )
    set_language_parser.add_argument("--state-path", default="data/state.json")
    add_language_argument(set_language_parser, required=True)

    enqueue_task_parser = subparsers.add_parser(
        "enqueue-task",
        help="Queue an autonomous task.",
    )
    enqueue_task_parser.add_argument("--state-path", default="data/state.json")
    enqueue_task_parser.add_argument("--log-path", default="data/runner.log")
    enqueue_task_parser.add_argument(
        "--task-type",
        choices=SUPPORTED_AUTONOMY_TASKS,
        required=True,
    )
    enqueue_task_parser.add_argument("--title", required=True)
    enqueue_task_parser.add_argument("--priority", type=int, default=5)
    enqueue_task_parser.add_argument("--payload-json", default="{}")
    enqueue_task_parser.add_argument(
        "--allow-command",
        action="append",
        default=None,
        help="Extra allowlisted command for command tasks.",
    )
    add_language_argument(enqueue_task_parser)

    enqueue_desktop_parser = subparsers.add_parser(
        "enqueue-desktop-action",
        help="Queue a desktop action task (click/type/hotkey/wait/screenshot/open_url/focus_window).",
    )
    enqueue_desktop_parser.add_argument("--state-path", default="data/state.json")
    enqueue_desktop_parser.add_argument("--log-path", default="data/runner.log")
    enqueue_desktop_parser.add_argument(
        "--action",
        choices=("hotkey", "type_text", "click", "move", "wait", "screenshot", "open_url", "focus_window"),
        required=True,
    )
    enqueue_desktop_parser.add_argument("--title", default="Desktop action")
    enqueue_desktop_parser.add_argument("--priority", type=int, default=6)
    enqueue_desktop_parser.add_argument("--x", type=int)
    enqueue_desktop_parser.add_argument("--y", type=int)
    enqueue_desktop_parser.add_argument("--button", type=int, default=1)
    enqueue_desktop_parser.add_argument("--text")
    enqueue_desktop_parser.add_argument("--keys", nargs="+")
    enqueue_desktop_parser.add_argument("--seconds", type=float)
    enqueue_desktop_parser.add_argument("--path")
    enqueue_desktop_parser.add_argument("--url")
    enqueue_desktop_parser.add_argument("--window-title")
    enqueue_desktop_parser.add_argument("--window-class")
    enqueue_desktop_parser.add_argument("--window-pid", type=int)
    enqueue_desktop_parser.add_argument("--window-index", type=int)
    enqueue_desktop_parser.add_argument(
        "--window-match-mode",
        choices=WINDOW_MATCH_MODE_CHOICES,
        default="smart",
        help="How to match window title (smart/exact/contains/regex).",
    )
    enqueue_desktop_parser.add_argument(
        "--focus-settle-ms",
        type=int,
        default=120,
        help="Wait time after focusing for type_text/hotkey (0-2000 ms).",
    )
    enqueue_desktop_parser.add_argument(
        "--relative-to-window",
        action="store_true",
        help="Interpret x/y as offsets from focused window's top-left (click/move only).",
    )
    add_language_argument(enqueue_desktop_parser)

    enqueue_perception_parser = subparsers.add_parser(
        "enqueue-desktop-perception",
        help="Queue a desktop perception task (screenshot + optional OCR).",
    )
    enqueue_perception_parser.add_argument("--state-path", default="data/state.json")
    enqueue_perception_parser.add_argument("--log-path", default="data/runner.log")
    enqueue_perception_parser.add_argument("--title", default="Desktop perception")
    enqueue_perception_parser.add_argument("--priority", type=int, default=6)
    enqueue_perception_parser.add_argument("--path", help="Screenshot output path under data/")
    enqueue_perception_parser.add_argument("--ocr-lang", default="eng")
    enqueue_perception_parser.add_argument("--ocr", dest="ocr", action="store_true")
    enqueue_perception_parser.add_argument("--no-ocr", dest="ocr", action="store_false")
    enqueue_perception_parser.set_defaults(ocr=True)
    add_language_argument(enqueue_perception_parser)

    enqueue_mission_parser = subparsers.add_parser(
        "enqueue-mission",
        help="Queue a multi-step mission task.",
    )
    enqueue_mission_parser.add_argument("--state-path", default="data/state.json")
    enqueue_mission_parser.add_argument("--log-path", default="data/runner.log")
    enqueue_mission_parser.add_argument("--title", required=True)
    enqueue_mission_parser.add_argument("--priority", type=int, default=7)
    enqueue_mission_parser.add_argument("--max-step-failures", type=int, default=0)
    enqueue_mission_parser.add_argument("--auto-recovery", dest="auto_recovery", action="store_true")
    enqueue_mission_parser.add_argument("--no-auto-recovery", dest="auto_recovery", action="store_false")
    enqueue_mission_parser.set_defaults(auto_recovery=True)
    enqueue_mission_parser.add_argument(
        "--steps-json",
        required=True,
        help="JSON array of mission steps. Each step needs task_type and payload.",
    )
    add_language_argument(enqueue_mission_parser)

    run_autonomy_parser = subparsers.add_parser(
        "run-autonomy",
        help="Run queued autonomous tasks with learning updates.",
    )
    run_autonomy_parser.add_argument("--state-path", default="data/state.json")
    run_autonomy_parser.add_argument("--log-path", default="data/runner.log")
    run_autonomy_parser.add_argument("--cycles", type=int, default=3)
    run_autonomy_parser.add_argument("--dry-run", action="store_true")
    run_autonomy_parser.add_argument("--until-empty", action="store_true")
    run_autonomy_parser.add_argument(
        "--max-cycles",
        type=int,
        default=50,
        help="Safety cap when --until-empty is set.",
    )
    run_autonomy_parser.add_argument(
        "--allow-command",
        action="append",
        default=None,
        help="Extra allowlisted command for command tasks.",
    )
    add_language_argument(run_autonomy_parser)

    run_prompt_parser = subparsers.add_parser(
        "run-prompt",
        help="Plan a natural-language prompt into a mission and execute it.",
    )
    run_prompt_parser.add_argument("--prompt", required=True)
    run_prompt_parser.add_argument("--state-path", default="data/state.json")
    run_prompt_parser.add_argument("--log-path", default="data/runner.log")
    run_prompt_parser.add_argument("--priority", type=int, default=8)
    run_prompt_parser.add_argument("--cycles", type=int, default=3)
    run_prompt_parser.add_argument("--dry-run", action="store_true")
    run_prompt_parser.add_argument(
        "--allow-command",
        action="append",
        default=None,
        help="Extra allowlisted command for prompt-generated command steps.",
    )
    add_language_argument(run_prompt_parser)

    autonomy_status_parser = subparsers.add_parser(
        "autonomy-status",
        help="Show autonomous queue/learning status.",
    )
    autonomy_status_parser.add_argument("--state-path", default="data/state.json")
    add_language_argument(autonomy_status_parser)

    list_windows_parser = subparsers.add_parser(
        "list-windows",
        help="List candidate windows for reliable desktop targeting.",
    )
    list_windows_parser.add_argument("--state-path", default="data/state.json")
    list_windows_parser.add_argument("--log-path", default="data/runner.log")
    list_windows_parser.add_argument("--title", default="", help="Window title pattern.")
    list_windows_parser.add_argument("--window-class", default="", help="Filter by window class.")
    list_windows_parser.add_argument("--window-pid", type=int, help="Filter by owning PID.")
    list_windows_parser.add_argument(
        "--match-mode",
        choices=WINDOW_MATCH_MODE_CHOICES,
        default="smart",
        help="Window title match mode.",
    )
    list_windows_parser.add_argument("--limit", type=int, default=20)
    list_windows_parser.add_argument("--dry-run", action="store_true")
    add_language_argument(list_windows_parser)

    spawn_challenges_parser = subparsers.add_parser(
        "spawn-challenges",
        help="Generate fun challenge tasks in autonomy queue.",
    )
    spawn_challenges_parser.add_argument("--state-path", default="data/state.json")
    spawn_challenges_parser.add_argument("--log-path", default="data/runner.log")
    spawn_challenges_parser.add_argument("--count", type=int, default=3)
    spawn_challenges_parser.add_argument("--base-priority", type=int, default=6)
    add_language_argument(spawn_challenges_parser)

    fun_status_parser = subparsers.add_parser(
        "fun-status",
        help="Show XP, level, badges, and streak.",
    )
    fun_status_parser.add_argument("--state-path", default="data/state.json")
    fun_status_parser.add_argument("--log-path", default="data/runner.log")
    add_language_argument(fun_status_parser)
    return parser


def build_orchestrator_from_args(args: argparse.Namespace) -> GrowingAgentOrchestrator:
    command = list(args.command) if args.command else ["pytest", "-q"]
    if command and command[0] == "--":
        command = command[1:]

    memory = MemoryStore(args.state_path)
    previous = memory.read_state()
    language = args.language or str(previous.get("language", DEFAULT_LANGUAGE))

    config = AgentConfig(
        iterations=args.iterations,
        dry_run=args.dry_run,
        command=command,
        target_score=args.target_score,
        stop_on_target=args.stop_on_target,
        max_history=args.max_history,
        timeout_seconds=args.timeout_seconds,
        halt_on_error=args.halt_on_error,
        language=language,
    )
    command_token = config.command[0]
    executable = Path(command_token).name
    runner = CommandRunner(
        allowed_commands={command_token, executable},
        log_path=args.log_path,
    )
    return GrowingAgentOrchestrator(memory=memory, runner=runner, config=config)


def build_autonomous_worker_from_args(args: argparse.Namespace) -> AutonomousWorker:
    memory = MemoryStore(args.state_path)
    previous = memory.read_state()
    language = args.language or str(previous.get("language", DEFAULT_LANGUAGE))

    allow_commands = set(DEFAULT_AUTONOMY_ALLOWED_COMMANDS)
    raw_allow = getattr(args, "allow_command", None)
    if isinstance(raw_allow, list):
        allow_commands.update(str(item) for item in raw_allow if str(item).strip())

    runner = CommandRunner(
        allowed_commands=allow_commands,
        log_path=getattr(args, "log_path", "data/runner.log"),
    )
    return AutonomousWorker(memory=memory, runner=runner, language=language)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.subcommand == "run":
        orchestrator = build_orchestrator_from_args(args)
        state = orchestrator.run()
        language = orchestrator.config.language
        state["display_language"] = language
        history = state.get("history", [])
        last_returncode = 0
        if isinstance(history, list) and history:
            last_item = history[-1]
            if isinstance(last_item, dict):
                raw_returncode = last_item.get("returncode", 0)
                try:
                    last_returncode = int(raw_returncode)
                except (TypeError, ValueError):
                    last_returncode = 1
        message_key = "run_completed" if last_returncode == 0 else "run_completed_with_errors"
        state["message"] = translate(message_key, language)
        if "stop_reason" in state:
            state["stop_message"] = translate(str(state["stop_reason"]), language)
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "status":
        memory = MemoryStore(args.state_path)
        state = memory.read_state()
        language = args.language or str(state.get("language", DEFAULT_LANGUAGE))
        state["display_language"] = language
        state["message"] = translate("status_loaded", language)
        if "stop_reason" in state:
            state["stop_message"] = translate(str(state["stop_reason"]), language)
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "reset":
        memory = MemoryStore(args.state_path)
        previous = memory.read_state()
        language = args.language or str(previous.get("language", DEFAULT_LANGUAGE))
        state = memory.reset_state()
        state["language"] = language
        memory.write_state(state)
        state["display_language"] = language
        state["message"] = translate("state_reset", language)
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "set-language":
        memory = MemoryStore(args.state_path)
        state = memory.read_state()
        language = str(args.language)
        state["language"] = language
        if "stop_reason" in state:
            state["stop_message"] = translate(str(state["stop_reason"]), language)
        memory.write_state(state)
        state["display_language"] = language
        state["message"] = translate("language_updated", language)
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "enqueue-task":
        worker = build_autonomous_worker_from_args(args)
        try:
            payload = parse_payload_json(args.payload_json)
            task = worker.enqueue(
                task_type=args.task_type,
                title=args.title,
                payload=payload,
                priority=args.priority,
            )
        except ValueError as error:
            parser.error(str(error))
        language = worker.language
        response = {
            "task": task,
            "display_language": language,
            "message": translate("task_enqueued", language),
        }
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "enqueue-desktop-action":
        worker = build_autonomous_worker_from_args(args)
        try:
            payload = build_desktop_payload_from_args(args)
            task = worker.enqueue(
                task_type="desktop_action",
                title=args.title,
                payload=payload,
                priority=args.priority,
            )
        except ValueError as error:
            parser.error(str(error))
        language = worker.language
        response = {
            "task": task,
            "display_language": language,
            "message": translate("task_enqueued", language),
        }
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "enqueue-desktop-perception":
        worker = build_autonomous_worker_from_args(args)
        try:
            payload: dict[str, Any] = {
                "ocr": bool(args.ocr),
                "ocr_lang": str(args.ocr_lang),
            }
            if args.path:
                payload["capture_path"] = str(args.path)
            task = worker.enqueue(
                task_type="desktop_perception",
                title=args.title,
                payload=payload,
                priority=args.priority,
            )
        except ValueError as error:
            parser.error(str(error))
        language = worker.language
        response = {
            "task": task,
            "display_language": language,
            "message": translate("task_enqueued", language),
        }
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "enqueue-mission":
        worker = build_autonomous_worker_from_args(args)
        try:
            steps = parse_steps_json(args.steps_json)
            payload = {
                "steps": steps,
                "max_step_failures": args.max_step_failures,
                "auto_recovery": bool(args.auto_recovery),
            }
            task = worker.enqueue(
                task_type="mission",
                title=args.title,
                payload=payload,
                priority=args.priority,
            )
        except ValueError as error:
            parser.error(str(error))
        language = worker.language
        response = {
            "task": task,
            "display_language": language,
            "message": translate("task_enqueued", language),
        }
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "run-autonomy":
        worker = build_autonomous_worker_from_args(args)
        try:
            if args.until_empty:
                cycles = max(1, int(args.max_cycles))
            else:
                cycles = args.cycles
            result = worker.run(cycles=cycles, dry_run=args.dry_run)
        except ValueError as error:
            parser.error(str(error))
        state = result["state"]
        language = str(state.get("language", worker.language))
        response = {
            "summary": result["summary"],
            "executed": result["executed"],
            "autonomy": state.get("autonomy", {}),
            "fun": state.get("autonomy", {}).get("game", {}),
            "moment": build_fun_moment(result["summary"], language),
            "display_language": language,
            "message": translate("autonomy_run_completed", language),
        }
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "run-prompt":
        worker = build_autonomous_worker_from_args(args)
        try:
            planned = plan_prompt_task(prompt=args.prompt, priority=args.priority)
            task = worker.enqueue(
                task_type=str(planned["task_type"]),
                title=str(planned["title"]),
                payload=planned.get("payload", {}),
                priority=int(planned["priority"]),
            )
            result = worker.run(cycles=max(1, int(args.cycles)), dry_run=args.dry_run)
        except ValueError as error:
            parser.error(str(error))
        state = result["state"]
        language = str(state.get("language", worker.language))
        response = {
            "prompt": args.prompt,
            "planned": {
                "intent": planned.get("intent"),
                "task_type": planned.get("task_type"),
                "title": planned.get("title"),
                "priority": planned.get("priority"),
                "preview": planned.get("preview", {}),
            },
            "task": task,
            "summary": result["summary"],
            "executed": result["executed"],
            "autonomy": state.get("autonomy", {}),
            "fun": state.get("autonomy", {}).get("game", {}),
            "moment": build_fun_moment(result["summary"], language),
            "display_language": language,
            "message": translate("prompt_run_completed", language),
        }
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "autonomy-status":
        memory = MemoryStore(args.state_path)
        state = memory.read_state()
        language = args.language or str(state.get("language", DEFAULT_LANGUAGE))
        response = {
            "autonomy": state.get("autonomy", {}),
            "fun": state.get("autonomy", {}).get("game", {}),
            "display_language": language,
            "message": translate("autonomy_status_loaded", language),
        }
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "list-windows":
        worker = build_autonomous_worker_from_args(args)
        try:
            if args.window_pid is not None and int(args.window_pid) <= 0:
                raise ValueError("--window-pid must be a positive integer")
            inspected = worker.inspect_windows(
                title=args.title,
                window_class=args.window_class,
                window_pid=args.window_pid,
                match_mode=args.match_mode,
                limit=args.limit,
                dry_run=args.dry_run,
            )
        except ValueError as error:
            parser.error(str(error))
        language = worker.language
        response = {
            **inspected,
            "display_language": language,
            "message": translate("desktop_windows_listed", language),
        }
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "spawn-challenges":
        worker = build_autonomous_worker_from_args(args)
        try:
            tasks = worker.spawn_challenges(
                count=args.count,
                base_priority=args.base_priority,
            )
        except ValueError as error:
            parser.error(str(error))
        language = worker.language
        response = {
            "tasks": tasks,
            "added_count": len(tasks),
            "display_language": language,
            "message": translate("challenges_spawned", language),
        }
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "fun-status":
        worker = build_autonomous_worker_from_args(args)
        fun = worker.fun_status()
        response = {
            "fun": fun,
            "display_language": worker.language,
            "message": translate("fun_status_loaded", worker.language),
        }
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    parser.error("Unknown subcommand")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
