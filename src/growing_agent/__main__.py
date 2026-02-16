from __future__ import annotations

import argparse
import json

from .orchestrator import GrowingAgentOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="growing_agent")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_parser = subparsers.add_parser("run", help="Run the agent loop.")
    run_parser.add_argument("--iterations", type=int, default=3)
    run_parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.subcommand == "run":
        orchestrator = GrowingAgentOrchestrator()
        state = orchestrator.run(iterations=args.iterations, dry_run=args.dry_run)
        print(json.dumps(state, indent=2, ensure_ascii=True))
        return 0

    parser.error("Unknown subcommand")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
