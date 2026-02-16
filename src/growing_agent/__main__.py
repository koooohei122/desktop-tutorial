"""Command-line interface for the growing agent."""

import argparse
import sys
import logging

from .orchestrator import Orchestrator


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration.
    
    Args:
        verbose: Enable verbose logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def run_command(args) -> int:
    """Execute the run command.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code
    """
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Growing Agent v0.1.0")
    logger.info(f"Iterations: {args.iterations}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"State file: {args.state_file}")
    
    try:
        orchestrator = Orchestrator(
            dry_run=args.dry_run,
            state_file=args.state_file
        )
        
        summaries = orchestrator.run(iterations=args.iterations)
        
        logger.info(f"\nSuccessfully completed {len(summaries)} iteration(s)")
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=args.verbose)
        return 1


def main() -> int:
    """Main entry point for the CLI.
    
    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description='Growing Agent - A self-improving agent with observe-plan-act-evaluate-update loop',
        prog='python -m growing_agent'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run the agent')
    run_parser.add_argument(
        '--iterations',
        type=int,
        default=1,
        help='Number of iterations to run (default: 1)'
    )
    run_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (commands logged but not executed)'
    )
    run_parser.add_argument(
        '--state-file',
        type=str,
        default='data/state.json',
        help='Path to state file (default: data/state.json)'
    )
    run_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    run_parser.set_defaults(func=run_command)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute command
    if hasattr(args, 'func'):
        return args.func(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
