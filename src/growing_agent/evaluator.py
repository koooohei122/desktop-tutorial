"""Evaluator for scoring agent performance."""

import re
import logging
from typing import Dict, Optional


logger = logging.getLogger(__name__)


class Evaluator:
    """Evaluates agent performance based on test results."""
    
    def __init__(self):
        """Initialize evaluator."""
        self.last_score = 0.0
    
    def evaluate_pytest_result(self, result: Dict[str, any]) -> float:
        """Calculate numeric score from pytest execution result.
        
        The score is based on:
        - Test pass rate (0-100)
        - Successful execution (returncode 0)
        
        Args:
            result: Dictionary containing command execution results
            
        Returns:
            Numeric score between 0.0 and 100.0
        """
        if not result:
            logger.warning("No result provided for evaluation")
            return 0.0
        
        # Check if command executed successfully
        if result.get("error"):
            logger.warning(f"Command had error: {result['error']}")
            return 0.0
        
        # If dry run, return a default score
        if result.get("dry_run"):
            logger.info("Dry run mode - returning default score")
            return 50.0
        
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        returncode = result.get("returncode")
        
        # Parse pytest output
        score = self._parse_pytest_output(stdout + stderr, returncode)
        
        self.last_score = score
        logger.info(f"Evaluated score: {score:.2f}")
        
        return score
    
    def _parse_pytest_output(self, output: str, returncode: Optional[int]) -> float:
        """Parse pytest output to extract test results.
        
        Args:
            output: Combined stdout and stderr
            returncode: Process return code
            
        Returns:
            Score between 0.0 and 100.0
        """
        if not output:
            # No output - likely no tests found or not pytest
            if returncode == 0:
                # Success but no pytest output - might be a different command
                return 50.0
            return 0.0
        
        # Look for pytest summary line like "5 passed, 2 failed in 0.12s"
        # Common patterns:
        # - "X passed"
        # - "X failed"
        # - "X error"
        # - "X skipped"
        
        passed = 0
        failed = 0
        errors = 0
        
        # Match patterns like "5 passed", "2 failed", etc.
        passed_match = re.search(r'(\d+)\s+passed', output)
        failed_match = re.search(r'(\d+)\s+failed', output)
        error_match = re.search(r'(\d+)\s+error', output)
        
        if passed_match:
            passed = int(passed_match.group(1))
        if failed_match:
            failed = int(failed_match.group(1))
        if error_match:
            errors = int(error_match.group(1))
        
        total = passed + failed + errors
        
        if total == 0:
            # No tests found or parsed
            if returncode == 0:
                return 50.0  # Executed successfully but no tests
            return 0.0
        
        # Calculate pass rate
        pass_rate = (passed / total) * 100.0
        
        logger.info(f"Tests: {passed} passed, {failed} failed, {errors} errors (total: {total})")
        
        return pass_rate
    
    def evaluate_generic_result(self, result: Dict[str, any]) -> float:
        """Evaluate a generic command result.
        
        Args:
            result: Dictionary containing command execution results
            
        Returns:
            Numeric score between 0.0 and 100.0
        """
        if not result:
            return 0.0
        
        if result.get("error"):
            return 0.0
        
        if result.get("dry_run"):
            return 50.0
        
        returncode = result.get("returncode", -1)
        
        if returncode == 0:
            return 100.0
        else:
            return 0.0
    
    def get_last_score(self) -> float:
        """Get the last evaluated score.
        
        Returns:
            Last score value
        """
        return self.last_score
