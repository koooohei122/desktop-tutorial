"""CLI entry-point: ``python -m growing_agent``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="growing_agent",
        description="A minimal self-improving agent.",
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Execute the agent loop")
    run_parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=1,
        help="Number of observe→plan→act→evaluate→update cycles (default: 1)",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate commands without executing them",
    )
    run_parser.add_argument(
        "--state-path",
        type=Path,
        default=None,
        help="Override the default data/state.json path",
    )
    run_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.command == "run":
        from growing_agent.orchestrator import run_loop

        state = run_loop(
            iterations=args.iterations,
            dry_run=args.dry_run,
            state_path=args.state_path,
        )
        print(f"\nDone – final score: {state['score']}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
