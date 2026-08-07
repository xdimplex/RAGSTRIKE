# Installation validation

> Verifying a clean-environment install. Every step has a command and a pass condition.

---

## 1. Python

```bash
python --version
```

**Pass:** 3.11 or later. The codebase uses `StrEnum`, `X | Y` unions at runtime, and
`datetime.UTC` — none of which exist before 3.11.

## 2. Virtual environment

```bash
python -m venv .venv
.venv/Scripts/activate          # source .venv/bin/activate on POSIX
python -c "import sys; print(sys.prefix)"
```

**Pass:** the prefix points inside `.venv`.

## 3. Dependencies

```bash
pip install -e ".[dashboard,dev]"
pip check
```

**Pass:** `pip check` reports no broken requirements.

## 4. The package imports

```bash
python -c "import ragstrike; print(ragstrike.__version__, ragstrike.PLUGIN_API_VERSION)"
```

**Pass:** `0.3.0 1.0.0`. The two version numbers move independently by design (ADR-015).

## 5. The CLI

```bash
ragstrike version
```

**Pass:** engine version, plugin API version, and at least one adapter.

## 6. Plugin discovery

```bash
ragstrike plugins
```

**Pass:** 9 active, 0 refused. Refusals print their reason.

## 7. SQLite

```bash
python -c "import sqlite3, aiosqlite; print(sqlite3.sqlite_version)"
```

**Pass:** 3.35 or later (for `RETURNING`). Migrations apply automatically on first run.

## 8. Configuration

```bash
python -c "from ragstrike.core.config.loader import load_settings, load_targets; \
s=load_settings(); t=load_targets(); \
print(len(t), 'targets; allow_remote =', s.safety.allow_remote_targets)"
```

**Pass:** at least one target, and `allow_remote = False`. **A `True` here on a fresh install is a
misconfiguration, not a convenience.**

## 9. Framework consistency

```bash
python -m validation.runner --checks-only
```

**Pass:** 10/10, including analyzer, reporting, database, and dashboard wiring.

## 10. Test suite

```bash
pytest -q
```

**Pass:** all tests pass. Needs no network, no model, and no running target.

---

## For the lab

## 11. Ollama

```bash
curl -s localhost:11434/api/tags | jq -r '.models[].name'
```

**Pass:** `qwen3:4b` and `nomic-embed-text` both listed.

## 12. ChromaDB and FastAPI

```bash
cd VulnerableRAG && python -c "import chromadb, fastapi; print('ok')"
```

**Pass:** imports succeed. Chroma is only needed by the lab applications, not by RAGStrike.

## 13. Streamlit

```bash
python -c "import streamlit; print(streamlit.__version__)"
```

**Pass:** 1.33 or later. Only needed for the dashboard.

## 14. The targets respond

```bash
ragstrike targets --verify
```

**Pass:** `OK` for each running target.

---

## If a step fails

[`troubleshooting.md`](troubleshooting.md) is indexed by symptom.
