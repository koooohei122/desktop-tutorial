# growing_agent

`growing_agent` is a lightweight Python project with an iterative:

`observe -> plan -> act -> evaluate -> update`

loop.

## 15 improvements included

1. Runtime settings centralized with `AgentConfig`.
2. Atomic JSON state writes (`temp` -> `replace`).
3. Corrupt state file backup and safe recovery.
4. `reset_state()` support for quick restart.
5. State normalization for core fields.
6. Runner timeout handling.
7. Safety blocklist for risky command tokens.
8. Run duration captured in `RunResult`.
9. Log rotation with size limit.
10. Expanded pytest summary parsing (passed/failed/errors/skipped/xfailed/xpassed).
11. Detailed evaluator output (`evaluate_pytest_result`).
12. Early-stop by target score.
13. Configurable history size limit.
14. CLI subcommands: `run`, `status`, `reset`.
15. Unit test suite for all key modules.

## Project structure

- `src/growing_agent/orchestrator.py`: orchestration loop and runtime controls
- `src/growing_agent/memory.py`: state read/write/reset and corruption handling
- `src/growing_agent/tools/runner.py`: allowlisted command execution and JSONL logs
- `src/growing_agent/evaluator.py`: pytest-like output scoring
- `src/growing_agent/__main__.py`: CLI entrypoint
- `tests/`: unit tests

## Run steps

1. Create and activate virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install editable package:
   ```bash
   python3 -m pip install -e .
   ```
3. Run loop with dry-run (requested command shape is supported):
   ```bash
   python3 -m growing_agent run --iterations 3 --dry-run
   ```
4. Switch language (Japanese/English):
   ```bash
   python3 -m growing_agent run --iterations 1 --dry-run --language en
   ```

## CLI examples

```bash
# Default dry-run loop
python3 -m growing_agent run --iterations 3 --dry-run

# Stop when score reaches threshold
python3 -m growing_agent run --iterations 15 --dry-run --stop-on-target --target-score 0.95

# Switch output/state language
python3 -m growing_agent run --iterations 3 --dry-run --language en

# Run a custom command (put --command at the end)
python3 -m growing_agent run --iterations 1 --state-path /tmp/ga-state.json --log-path /tmp/ga.log --command /usr/bin/python3 -c "print('ok')"

# Inspect current state
python3 -m growing_agent status

# Inspect state with UI message in Japanese
python3 -m growing_agent status --language ja

# Reset state file
python3 -m growing_agent reset
```

After execution:

- state is stored in `data/state.json`
- command logs are appended to `data/runner.log`
