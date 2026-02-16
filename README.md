# growing_agent

`growing_agent` is a lightweight Python project with an iterative:

`observe -> plan -> act -> evaluate -> update`

loop.

It now also supports generalized autonomous work (not only coding loops) with
continuous local learning from outcomes.

## Core capabilities included

- Runtime settings centralized with `AgentConfig`.
- Atomic JSON state writes (`temp` -> `replace`).
- Corrupt state file backup and safe recovery.
- State normalization for core fields.
- Runner timeout handling and safety blocklist for risky command tokens.
- Run duration captured in `RunResult`.
- Log rotation with size limit.
- Expanded pytest summary parsing
  (`passed/failed/errors/skipped/xfailed/xpassed`).
- Detailed evaluator output (`evaluate_pytest_result`).
- Early-stop by target score and configurable history size limit.
- Multi-language CLI output (default: English).
- Unit test suite for all key modules.

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

## Launch-ready additions

- MIT license (`LICENSE`)
- Community docs (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`)
- GitHub CI workflow (`.github/workflows/ci.yml`)
- GitHub release workflow (`.github/workflows/release.yml`)
- Docker runtime (`Dockerfile`)
- Launch checklist (`LAUNCH.md`)

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
   Or install with dev dependencies:
   ```bash
   python3 -m pip install -e ".[dev]"
   ```
3. Run loop with dry-run (requested command shape is supported):
   ```bash
   python3 -m growing_agent run --iterations 3 --dry-run
   ```
4. Switch language (default `en`, supported: `en zh it fr pt hi ar ja es`):
   ```bash
   python3 -m growing_agent run --iterations 1 --dry-run --language en
   ```
5. Use console script entrypoint:
   ```bash
   growing-agent status
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

## Docker quick start

```bash
docker build -t growing-agent:latest .
docker run --rm growing-agent:latest status
```

## Public release quick start

1. Ensure CI is green on main branch.
2. Tag a release:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
3. Release workflow builds artifacts and can publish to PyPI if
   `PYPI_API_TOKEN` is configured in repository secrets.

After execution:

- state is stored in `data/state.json`
- command logs are appended to `data/runner.log`
- each history entry keeps `stdout_excerpt` / `stderr_excerpt` for quick diagnostics
- autonomy queue/results/learning are persisted in `state["autonomy"]`
