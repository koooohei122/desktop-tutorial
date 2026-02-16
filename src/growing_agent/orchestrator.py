"""Orchestrator for the agent's main loop."""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from .memory import Memory
from .tools.runner import CommandRunner
from .evaluator import Evaluator


logger = logging.getLogger(__name__)


class Orchestrator:
    """Manages the agent's observe-plan-act-evaluate-update loop."""
    
    def __init__(self, dry_run: bool = False, state_file: str = "data/state.json"):
        """Initialize orchestrator.
        
        Args:
            dry_run: If True, commands are logged but not executed
            state_file: Path to state file
        """
        self.memory = Memory(state_file)
        self.runner = CommandRunner(dry_run=dry_run)
        self.evaluator = Evaluator()
        self.dry_run = dry_run
    
    def observe(self) -> Dict:
        """Observe the current state.
        
        Returns:
            Dictionary containing observations
        """
        logger.info("=== OBSERVE ===")
        
        state = self.memory.read_state()
        iteration = state.get("iteration", 0)
        best_score = state.get("best_score", 0.0)
        
        observations = {
            "iteration": iteration,
            "best_score": best_score,
            "timestamp": datetime.now().isoformat(),
            "history_count": len(state.get("history", []))
        }
        
        logger.info(f"Current iteration: {iteration}")
        logger.info(f"Best score so far: {best_score:.2f}")
        
        return observations
    
    def plan(self, observations: Dict) -> List[str]:
        """Create a plan based on observations.
        
        Args:
            observations: Current observations
            
        Returns:
            List of commands to execute
        """
        logger.info("=== PLAN ===")
        
        iteration = observations.get("iteration", 0)
        
        # Simple planning strategy: run pytest if available
        # In a real implementation, this would be more sophisticated
        commands = []
        
        if iteration == 0:
            # First iteration: explore the environment
            commands = [
                "pwd",
                "ls -la",
                "python --version"
            ]
        else:
            # Subsequent iterations: try to improve by running tests
            commands = [
                "pytest --version",
                "pytest -v"
            ]
        
        logger.info(f"Planned {len(commands)} commands")
        for i, cmd in enumerate(commands, 1):
            logger.info(f"  {i}. {cmd}")
        
        return commands
    
    def act(self, commands: List[str]) -> List[Dict]:
        """Execute the planned commands.
        
        Args:
            commands: List of commands to execute
            
        Returns:
            List of execution results
        """
        logger.info("=== ACT ===")
        
        results = []
        for cmd in commands:
            result = self.runner.run(cmd)
            results.append(result)
            
            # Log summary
            if result.get("allowed"):
                status = "✓" if result.get("returncode") == 0 else "✗"
                logger.info(f"{status} {cmd}")
            else:
                logger.warning(f"✗ {cmd} (blocked)")
        
        return results
    
    def evaluate(self, results: List[Dict]) -> float:
        """Evaluate the results of actions.
        
        Args:
            results: List of execution results
            
        Returns:
            Numeric score
        """
        logger.info("=== EVALUATE ===")
        
        if not results:
            logger.warning("No results to evaluate")
            return 0.0
        
        # Find pytest results
        pytest_result = None
        for result in results:
            cmd = result.get("command", "")
            if "pytest" in cmd:
                pytest_result = result
                break
        
        # Evaluate pytest if available, otherwise use generic evaluation
        if pytest_result:
            score = self.evaluator.evaluate_pytest_result(pytest_result)
        else:
            # Evaluate based on successful command execution
            successful = sum(1 for r in results 
                           if r.get("returncode") == 0 and r.get("allowed", False))
            total = len([r for r in results if r.get("allowed", False)])
            
            if total > 0:
                score = (successful / total) * 100.0
            else:
                score = 0.0
        
        logger.info(f"Score: {score:.2f}")
        
        return score
    
    def update(self, observations: Dict, commands: List[str], 
               results: List[Dict], score: float) -> None:
        """Update the agent's state based on the iteration.
        
        Args:
            observations: Observations from this iteration
            commands: Commands that were planned
            results: Results from execution
            score: Evaluated score
        """
        logger.info("=== UPDATE ===")
        
        # Create history entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "iteration": observations.get("iteration", 0),
            "commands": commands,
            "score": score,
            "results_summary": {
                "total_commands": len(results),
                "successful": sum(1 for r in results if r.get("returncode") == 0),
                "failed": sum(1 for r in results if r.get("returncode") != 0),
                "blocked": sum(1 for r in results if not r.get("allowed", True))
            }
        }
        
        # Add to history
        self.memory.add_history_entry(entry)
        
        # Update best score if improved
        state = self.memory.read_state()
        current_best = state.get("best_score", 0.0)
        
        if score > current_best:
            logger.info(f"New best score! {current_best:.2f} -> {score:.2f}")
            self.memory.update_state(best_score=score)
        else:
            logger.info(f"Score {score:.2f} did not beat best {current_best:.2f}")
        
        # Increment iteration
        new_iteration = self.memory.increment_iteration()
        logger.info(f"Completed iteration. Next: {new_iteration}")
    
    def run_iteration(self) -> Dict:
        """Run a single iteration of the agent loop.
        
        Returns:
            Dictionary with iteration summary
        """
        logger.info("\n" + "="*60)
        logger.info("STARTING NEW ITERATION")
        logger.info("="*60)
        
        # 1. Observe
        observations = self.observe()
        
        # 2. Plan
        commands = self.plan(observations)
        
        # 3. Act
        results = self.act(commands)
        
        # 4. Evaluate
        score = self.evaluate(results)
        
        # 5. Update
        self.update(observations, commands, results, score)
        
        logger.info("="*60)
        logger.info("ITERATION COMPLETE")
        logger.info("="*60 + "\n")
        
        return {
            "iteration": observations.get("iteration", 0),
            "score": score,
            "commands": len(commands),
            "results": len(results)
        }
    
    def run(self, iterations: int = 1) -> List[Dict]:
        """Run multiple iterations of the agent loop.
        
        Args:
            iterations: Number of iterations to run
            
        Returns:
            List of iteration summaries
        """
        logger.info(f"Starting agent run: {iterations} iteration(s)")
        if self.dry_run:
            logger.info("DRY RUN MODE - commands will not be executed")
        
        summaries = []
        for i in range(iterations):
            summary = self.run_iteration()
            summaries.append(summary)
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("RUN COMPLETE")
        logger.info("="*60)
        
        state = self.memory.read_state()
        logger.info(f"Total iterations: {state.get('iteration', 0)}")
        logger.info(f"Best score: {state.get('best_score', 0.0):.2f}")
        logger.info(f"History entries: {len(state.get('history', []))}")
        
        return summaries
