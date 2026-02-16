# growing_agent

Minimal Python agent with observe → plan → act → evaluate → update loop.

## Requirements

- Python 3.9+
- No network usage
- No destructive commands (runner uses allowlist)

## Install

```bash
pip install -e .
```

Or from project root:

```bash
cd /workspace
pip install -e .
```

## Run

```bash
# Dry run (3 iterations, no actual commands)
python -m growing_agent run --iterations 3 --dry-run

# Real run (3 iterations, runs pytest)
python -m growing_agent run --iterations 3

# Custom iterations
python -m growing_agent run --iterations 5 --dry-run

# Custom working directory
python -m growing_agent run --iterations 2 --cwd /path/to/project
```

## Output

- `data/state.json` – persisted state (iteration, scores)
- `data/runner.log` – command execution logs

## Structure

```
src/growing_agent/
├── __init__.py
├── __main__.py       # CLI entry
├── orchestrator.py   # observe → plan → act → evaluate → update
├── memory.py         # read/write data/state.json
├── evaluator.py      # numeric score from pytest result
└── tools/
    └── runner.py     # allowlist command runner + logs
```
