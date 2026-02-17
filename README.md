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

## Fun mode (gamified autonomy)

`growing_agent` now tracks playful progression for autonomous work:

- XP and levels
- streak days
- badges
- challenge packs
- run moments (level-up, badge unlock, clean run feedback)

Use these commands:

```bash
# Create challenge tasks
python3 -m growing_agent spawn-challenges --count 3 --language en

# Run challenges and see fun moment feedback
python3 -m growing_agent run-autonomy --cycles 3 --dry-run --language en

# Show XP/level/badges status
python3 -m growing_agent fun-status --language en
```

## PC autonomy commands (OpenClaw-style building blocks)

You can queue GUI-like actions and multi-step missions:

```bash
# Queue a desktop typing action
python3 -m growing_agent enqueue-desktop-action --action type_text --text "hello world"

# Plan and run a natural-language prompt (example: Chrome + YouTube music)
python3 -m growing_agent run-prompt --prompt "google chromeを開いて、今日におすすめな曲をyoutubeで流して" --cycles 2

# Generic prompt planning examples (app open + search + input + hotkey)
python3 -m growing_agent run-prompt --prompt "Firefoxを開いて、cursor agentをgoogleで検索して"
python3 -m growing_agent run-prompt --prompt "「hello world」と入力して、Enterを押して"
python3 -m growing_agent run-prompt --prompt "メモ帳を開いて今日の日記を書いて"

# Supported generic prompt intents:
# - open app (generic: resolved from system desktop entries / executable names)
# - open URL
# - search on YouTube/Google/GitHub/Wikipedia/Bing
# - type text / press hotkey / wait

# Queue generic app launch without per-app hardcoding
python3 -m growing_agent enqueue-desktop-action --action launch_app --app "Obsidian"

# Focus a target app window by title
python3 -m growing_agent enqueue-desktop-action --action focus_window --window-title "Terminal"

# Focus by class or PID (no title needed)
python3 -m growing_agent enqueue-desktop-action --action focus_window --window-class "gnome-terminal"
python3 -m growing_agent enqueue-desktop-action --action focus_window --window-pid 12345

# List candidate windows before targeting
python3 -m growing_agent list-windows --title "Terminal" --window-class "gnome-terminal" --match-mode smart

# Type into a specific window (focuses first)
python3 -m growing_agent enqueue-desktop-action --action type_text --text "hello world" --window-title "Terminal" --window-match-mode exact --focus-settle-ms 150

# Click relative to target window top-left
python3 -m growing_agent enqueue-desktop-action --action click --x 120 --y 48 --button 1 --window-class "gnome-terminal" --relative-to-window

# Queue a desktop hotkey action
python3 -m growing_agent enqueue-desktop-action --action hotkey --keys ctrl l

# Queue desktop perception (screenshot + OCR)
python3 -m growing_agent enqueue-desktop-perception --path data/autonomy/perception.png --ocr-lang eng

# Queue a mission with multiple steps
python3 -m growing_agent enqueue-mission --title "quick desktop mission" --steps-json '[{"task_type":"desktop_action","payload":{"action":"wait","seconds":0.2}},{"task_type":"command","payload":{"command":["echo","mission-ok"]}}]'

# Mission with recovery steps per failed step
python3 -m growing_agent enqueue-mission --title "recoverable mission" --steps-json '[{"task_type":"desktop_action","payload":{"action":"open_url","url":"https://example.com"},"on_failure":[{"task_type":"desktop_perception","payload":{"ocr":false}}],"continue_on_failure":true}]'

# Execute until queue is empty (bounded by max-cycles)
python3 -m growing_agent run-autonomy --until-empty --max-cycles 50 --dry-run
```

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

# Run until queue is drained (bounded safety cap)
python3 -m growing_agent run-autonomy --until-empty --max-cycles 50 --dry-run

# Inspect autonomy queue/learning state
python3 -m growing_agent autonomy-status

# Generate fun challenge tasks
python3 -m growing_agent spawn-challenges --count 3

# Inspect XP/level/badges
python3 -m growing_agent fun-status

# Queue desktop action
python3 -m growing_agent enqueue-desktop-action --action wait --seconds 0.5

# Queue generic app launch action (works from app name)
python3 -m growing_agent enqueue-desktop-action --action launch_app --app "Firefox"

# Queue desktop window focus action
python3 -m growing_agent enqueue-desktop-action --action focus_window --window-title "Terminal"

# Inspect window candidates for deterministic targeting
python3 -m growing_agent list-windows --title "Terminal" --window-class "gnome-terminal" --match-mode smart --limit 20

# Queue desktop action with target window focus
python3 -m growing_agent enqueue-desktop-action --action type_text --text "hello" --window-title "Terminal" --window-match-mode exact --focus-settle-ms 150

# Queue relative move/click inside focused target window
python3 -m growing_agent enqueue-desktop-action --action move --x 20 --y 20 --window-pid 12345 --relative-to-window
python3 -m growing_agent enqueue-desktop-action --action click --x 20 --y 20 --button 1 --window-pid 12345 --relative-to-window

# Queue desktop perception
python3 -m growing_agent enqueue-desktop-perception --path data/autonomy/snapshot.png

# Queue mission task
python3 -m growing_agent enqueue-mission --title "mission 1" --steps-json '[{"task_type":"write_note","payload":{"path":"data/autonomy/notes.md","text":"hello"}}]'

# Plan and execute natural-language prompt mission
python3 -m growing_agent run-prompt --prompt "open Google Chrome and play recommended songs on YouTube" --dry-run
python3 -m growing_agent run-prompt --prompt "open Firefox and search python asyncio on Google" --dry-run
python3 -m growing_agent run-prompt --prompt "type \"hello world\" and press Enter" --dry-run
python3 -m growing_agent run-prompt --prompt "open notepad and write today's diary" --dry-run

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
- fun progression is persisted in `state["autonomy"]["game"]`
