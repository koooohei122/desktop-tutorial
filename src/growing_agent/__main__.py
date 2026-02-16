from __future__ import annotations

import argparse
import sys

from growing_agent.orchestrator import Orchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="growing_agent")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the agent loop")
    run.add_argument("--iterations", type=int, default=1, help="Number of loop iterations")
    run.add_argument("--dry-run", action="store_true", help="Plan only; do not execute commands")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "run":
        orch = Orchestrator()
        orch.run(iterations=args.iterations, dry_run=args.dry_run)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

