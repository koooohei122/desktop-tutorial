from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import AgentConfig
from .i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, translate
from .memory import MemoryStore
from .orchestrator import GrowingAgentOrchestrator
from .tools.runner import CommandRunner


def add_language_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--language",
        choices=SUPPORTED_LANGUAGES,
        default=None,
        help=f"Output/state language ({'/'.join(SUPPORTED_LANGUAGES)}).",
    )


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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.subcommand == "run":
        orchestrator = build_orchestrator_from_args(args)
        state = orchestrator.run()
        language = orchestrator.config.language
        state["display_language"] = language
        state["message"] = translate("run_completed", language)
        if "stop_reason" in state and "stop_message" not in state:
            state["stop_message"] = translate(str(state["stop_reason"]), language)
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return 0

    if args.subcommand == "status":
        memory = MemoryStore(args.state_path)
        state = memory.read_state()
        language = args.language or str(state.get("language", DEFAULT_LANGUAGE))
        state["display_language"] = language
        state["message"] = translate("status_loaded", language)
        if "stop_reason" in state and "stop_message" not in state:
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

    parser.error("Unknown subcommand")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
