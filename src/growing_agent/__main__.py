from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import AgentConfig
from .memory import MemoryStore
from .orchestrator import GrowingAgentOrchestrator
from .tools.runner import CommandRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="growing_agent")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_parser = subparsers.add_parser("run", help="Run the agent loop.")
    run_parser.add_argument("--iterations", type=int, default=3)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument(
        "--command",
        nargs="+",
        default=["pytest", "-q"],
        help="Command to execute in each iteration.",
    )
    run_parser.add_argument("--state-path", default="data/state.json")
    run_parser.add_argument("--log-path", default="data/runner.log")
    run_parser.add_argument("--timeout-seconds", type=float, default=30.0)
    run_parser.add_argument("--max-history", type=int, default=200)
    run_parser.add_argument("--target-score", type=float, default=1.0)
    run_parser.add_argument("--stop-on-target", action="store_true")
    run_parser.add_argument("--halt-on-error", action="store_true")

    status_parser = subparsers.add_parser("status", help="Show current saved state.")
    status_parser.add_argument("--state-path", default="data/state.json")

    reset_parser = subparsers.add_parser("reset", help="Reset saved state.")
    reset_parser.add_argument("--state-path", default="data/state.json")
    return parser


def build_orchestrator_from_args(args: argparse.Namespace) -> GrowingAgentOrchestrator:
    config = AgentConfig(
        iterations=args.iterations,
        dry_run=args.dry_run,
        command=list(args.command),
        target_score=args.target_score,
        stop_on_target=args.stop_on_target,
        max_history=args.max_history,
        timeout_seconds=args.timeout_seconds,
        halt_on_error=args.halt_on_error,
    )
    memory = MemoryStore(args.state_path)
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
        print(json.dumps(state, indent=2, ensure_ascii=True))
        return 0

    if args.subcommand == "status":
        memory = MemoryStore(args.state_path)
        state = memory.read_state()
        print(json.dumps(state, indent=2, ensure_ascii=True))
        return 0

    if args.subcommand == "reset":
        memory = MemoryStore(args.state_path)
        state = memory.reset_state()
        print(json.dumps(state, indent=2, ensure_ascii=True))
        return 0

    parser.error("Unknown subcommand")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
