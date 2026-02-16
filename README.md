# growing_agent

`growing_agent` is a lightweight Python project with an iterative:

`observe -> plan -> act -> evaluate -> update`

loop.

It now also supports generalized autonomous work (not only coding loops) with
continuous local learning from outcomes.

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

## General autonomous work (beyond coding)

Autonomy tasks currently supported:

- `command`: run an allowlisted command as a task
- `write_note`: append notes under `data/`
- `analyze_state`: generate local insights from current state

Learning behavior:

- keeps per-task-type stats (`attempts`, `successes`, `avg_reward`)
- appends failure-driven recommendations to `improvement_backlog`
- reprioritizes queued tasks using learned reward history
- auto-queues follow-up `analyze_state` tasks for failed executions

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

# Persist preferred language in state
python3 -m growing_agent set-language --language en

# Queue a generic autonomous task
python3 -m growing_agent enqueue-task --task-type write_note --title "daily memo" --payload-json '{"path":"data/autonomy/notes.md","text":"hello"}'

# Run autonomy queue with learning updates
python3 -m growing_agent run-autonomy --cycles 3 --dry-run

# Inspect autonomy queue/learning state
python3 -m growing_agent autonomy-status

# Reset state file
python3 -m growing_agent reset
```

After execution:

- state is stored in `data/state.json`
- command logs are appended to `data/runner.log`
- each history entry keeps `stdout_excerpt` / `stderr_excerpt` for quick diagnostics
- autonomy queue/results/learning are persisted in `state["autonomy"]`
