# Contributing to growing_agent

Thanks for your interest in contributing.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

## Pull request guidelines

- Keep changes focused and small.
- Add or update tests for behavior changes.
- Update documentation for CLI or workflow changes.
- Avoid destructive defaults; preserve safety checks.
- Make sure all tests pass before opening a PR.

## Commit message style

Use clear, imperative messages, for example:

- `Add autonomy task queue persistence`
- `Fix language fallback for status output`

## Reporting issues

Open a GitHub issue with:

- expected behavior
- actual behavior
- minimal reproduction steps
- environment details (OS, Python version)
