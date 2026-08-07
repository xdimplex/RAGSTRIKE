# `analyzers/tests`

The Phase 10 brief names this directory in the package structure, so it exists. **The tests
themselves live elsewhere**, and deliberately:

| Suite | Location |
|---|---|
| Rule engine | `tests/unit/test_analyzer_rules.py` |
| Scoring and confidence | `tests/unit/test_analyzer_scoring.py` |
| Evidence, recommendations, validation, registry, engine | `tests/unit/test_analyzer_engine.py` |
| Persistence and end-to-end | `tests/integration/test_analyzer_integration.py` |

## Why not here

`pyproject.toml` sets `testpaths = ["tests"]`, so `pytest` collects only from the repository's
`tests/` tree. A suite placed under `src/` would be silently skipped — present in the repository,
absent from every run, and indistinguishable from tests that pass.

Keeping them in `tests/` also keeps the shipped package free of test code, which matters once
`pip install ragstrike` is the distribution path.
