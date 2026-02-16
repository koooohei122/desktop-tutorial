# Launch Guide (Open Source)

This document is a practical checklist to launch `growing_agent` for public use.

## 1) Project readiness

- [ ] README includes quick start and CLI examples.
- [ ] LICENSE is present.
- [ ] CONTRIBUTING and CODE_OF_CONDUCT are present.
- [ ] SECURITY policy is present.
- [ ] Tests pass in CI.

## 2) Packaging readiness

- [ ] `pyproject.toml` has metadata and script entry points.
- [ ] Local package build succeeds:
  ```bash
  python3 -m pip install -e ".[dev]"
  python3 -m unittest discover -s tests -v
  python3 -m pip install build
  python3 -m build
  ```

## 3) GitHub readiness

- [ ] Enable branch protection on `main`.
- [ ] Enable Discussions and Issues.
- [ ] Configure Actions permissions for release workflow.
- [ ] Configure PyPI Trusted Publisher (optional, for auto publish).

## 4) Release process

1. Create and push a version tag:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
2. GitHub release workflow builds package artifacts.
3. If configured, publish to PyPI from tag workflow.

## 5) Post-launch operations

- [ ] Triage issues weekly.
- [ ] Review improvement backlog from `state["autonomy"]["learning"]`.
- [ ] Cut regular releases with changelog updates.
