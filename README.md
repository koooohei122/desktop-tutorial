# growing_agent

A minimal, self-improving Python agent that runs an **observe → plan → act → evaluate → update** loop.

## Project structure

```
src/growing_agent/
├── __init__.py          # package metadata
├── __main__.py          # CLI entry-point
├── orchestrator.py      # main loop (observe/plan/act/evaluate/update)
├── memory.py            # read/write data/state.json
├── evaluator.py         # numeric score from pytest results
└── tools/
    ├── __init__.py
    └── runner.py        # allowlist-based safe command runner
```

## Requirements

- Python 3.10+
- (optional) pytest ≥ 7.0 for the evaluation step

## Quick start

```bash
# 1. Install in editable mode (from the repo root)
pip install -e ".[dev]"

# 2. Run the agent loop (3 iterations, dry-run mode)
python -m growing_agent run --iterations 3 --dry-run

# 3. Run for real (executes pytest internally)
python -m growing_agent run --iterations 3

# 4. Verbose output
python -m growing_agent run --iterations 2 --dry-run --verbose
```

## CLI reference

```
python -m growing_agent run [OPTIONS]

Options:
  --iterations, -n   Number of cycles (default: 1)
  --dry-run          Validate commands without executing them
  --state-path       Override data/state.json location
  --verbose, -v      Enable DEBUG logging
```

## State file

After each run the agent writes its state to `data/state.json`:

```json
{
  "iteration": 3,
  "score": 100.0,
  "history": [
    {"iteration": 1, "score": 100.0, "passed": 5, "failed": 0, "errors": 0, "actions": ["python3 -m pytest --tb=short -q"]}
  ],
  "plan": []
}
```

## Safety

- The command runner only allows a small set of safe commands (see `ALLOWED_COMMANDS` in `tools/runner.py`).
- Dangerous substrings (`rm -rf`, `curl`, `wget`, etc.) are blocked.
- No network access is performed by the agent itself.
