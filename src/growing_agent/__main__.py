"""CLI: python -m growing_agent run --iterations 3 --dry-run"""

import argparse
from pathlib import Path

from .orchestrator import run_loop


def main() -> None:
    parser = argparse.ArgumentParser(prog="growing_agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the agent loop")
    run_parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of iterations (default: 3)",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip actual command execution",
    )
    run_parser.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help="Working directory (default: current)",
    )

    args = parser.parse_args()

    if args.command == "run":
        state = run_loop(
            iterations=args.iterations,
            cwd=args.cwd,
            dry_run=args.dry_run,
        )
        print(f"Completed {args.iterations} iterations. Final state: {state}")


if __name__ == "__main__":
    main()
