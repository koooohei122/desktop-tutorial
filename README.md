# Growing Agent

A minimal self-improving agent with an observe-plan-act-evaluate-update loop.

## Overview

Growing Agent is a Python framework that implements a basic autonomous agent capable of:
- **Observing** its current state and environment
- **Planning** actions based on observations
- **Acting** by executing safe, allowlisted commands
- **Evaluating** the results (especially pytest outcomes)
- **Updating** its internal state to improve over time

## Features

- 🔄 **Main Loop**: Automated observe-plan-act-evaluate-update cycle
- 💾 **Persistent Memory**: State management with JSON storage
- 🛡️ **Safe Execution**: Allowlist-based command runner (no network, no destructive operations)
- 📊 **Evaluation**: Numeric scoring based on pytest results
- 🔍 **Logging**: Comprehensive execution logs
- 🏃 **CLI**: Easy-to-use command-line interface

## Project Structure

```
growing_agent/
├── src/growing_agent/
│   ├── __init__.py
│   ├── __main__.py          # CLI entry point
│   ├── orchestrator.py       # Main loop controller
│   ├── memory.py             # State persistence
│   ├── evaluator.py          # Performance scoring
│   └── tools/
│       ├── __init__.py
│       └── runner.py         # Safe command executor
├── data/
│   └── state.json           # Agent state storage
├── pyproject.toml           # Package configuration
└── README.md
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd growing_agent
```

2. Install the package in development mode:
```bash
pip install -e .
```

3. (Optional) Install development dependencies:
```bash
pip install -e ".[dev]"
```

## Usage

### Basic Run

Run the agent for a single iteration:

```bash
python -m growing_agent run
```

### Multiple Iterations

Run for 3 iterations:

```bash
python -m growing_agent run --iterations 3
```

### Dry Run Mode

Test the agent without actually executing commands:

```bash
python -m growing_agent run --iterations 3 --dry-run
```

### Custom State File

Use a custom state file location:

```bash
python -m growing_agent run --state-file custom/path/state.json
```

### Verbose Logging

Enable detailed debug logging:

```bash
python -m growing_agent run --iterations 3 --verbose
```

## How It Works

### The Agent Loop

Each iteration follows these steps:

1. **Observe**: Read current state (iteration number, best score, history)
2. **Plan**: Generate a list of commands to execute
3. **Act**: Run planned commands through the safe command runner
4. **Evaluate**: Calculate a numeric score (0-100) based on results
5. **Update**: Save results to history and update best score

### Command Safety

The agent uses an allowlist of safe commands:

**Allowed:**
- Python/Testing: `python`, `pytest`, `pip`
- File operations: `ls`, `cat`, `grep`, `find` (read-only)
- System info: `pwd`, `date`, `echo`
- Git (read-only): `git status`, `git log`, `git diff`

**Blocked:**
- Network: `curl`, `wget`, `ssh`, `ftp`
- Destructive: `rm`, `dd`, `mkfs`, `sudo`

### State Persistence

The agent maintains state in `data/state.json`:

```json
{
  "iteration": 3,
  "best_score": 85.5,
  "history": [
    {
      "timestamp": "2026-02-16T10:30:00",
      "iteration": 0,
      "commands": ["pwd", "ls"],
      "score": 100.0,
      "results_summary": {...}
    }
  ]
}
```

## Examples

### Example 1: Basic Exploration

```bash
python -m growing_agent run --dry-run
```

This runs one iteration in dry-run mode, showing what commands would be executed.

### Example 2: Testing Workflow

```bash
# First, ensure pytest is available
pip install pytest

# Run the agent
python -m growing_agent run --iterations 3
```

The agent will:
- Iteration 0: Explore the environment
- Iteration 1-2: Run pytest and evaluate test results

### Example 3: Monitor Progress

```bash
# Run with verbose logging
python -m growing_agent run --iterations 5 --verbose

# Check the state
cat data/state.json
```

## Design Principles

- **No Network**: All operations are local-only
- **Non-Destructive**: Only read operations and safe commands
- **Transparent**: All actions are logged
- **Extensible**: Easy to add new evaluators and planning strategies

## Development

### Running Tests

```bash
pytest
```

### Project Dependencies

- Python >= 3.8
- No external runtime dependencies
- pytest (optional, for testing)

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
