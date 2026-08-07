# Deployment guide

> RAGStrike is designed for **local, single-operator** use. This guide reflects that, and
> [`limitations.md`](limitations.md) explains why it is not a multi-tenant service.

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) for the lab targets
- ~4 GB disk for models

```bash
ollama pull qwen3:4b
ollama pull nomic-embed-text
```

---

## Install

```bash
git clone <repository> && cd RAGStrike
python -m venv .venv && .venv/Scripts/activate    # source .venv/bin/activate on POSIX
pip install -e ".[dashboard,dev]"
```

Verify:

```bash
ragstrike version
ragstrike plugins
python -m validation.runner --checks-only
```

Ten passing consistency checks means the installation is sound.

---

## Running the lab

Three processes, in three terminals:

```bash
cd VulnerableRAG && RAGSTRIKE_LAB_ACK=1 python -m profiles.vulnerable.main_api   # 9000
cd SecureRAG     && RAGSTRIKE_LAB_ACK=1 python -m profiles.secure.main_api       # 9001
cd RAGStrike     && ragstrike targets --verify
```

Both lab applications refuse to start without `RAGSTRIKE_LAB_ACK=1`. VulnerableRAG executes
instructions found in uploaded documents; SecureRAG is hardened but not audited and carries the same
synthetic canaries. Neither belongs anywhere but loopback.

---

## Docker

`docker/` holds Dockerfiles for the API, the dashboard, and the lab, plus a compose file. They are
scaffolds from Phase 1 and are **not exercised by CI**. Treat them as a starting point rather than a
supported path.

---

## CI

`.github/workflows/ci.yml` runs the gate:

```bash
pytest && lint-imports && mypy src && ruff check . && black --check .
```

`lint-imports` is the one that matters most. It enforces the dependency rule as a merge gate — six
contracts, including "the dashboard never imports the engine" and "scoring cannot reach a model or
any I/O". Layering that is documented but unenforced degrades within months.

---

## Upgrading

1. `pip install -e ".[dashboard,dev]"`
2. `python -m validation.runner --checks-only` — migrations apply automatically at startup
3. Re-scan a known target and compare the grade

**Scores are versioned.** A target that has not changed must not change grade because RAGStrike was
upgraded. Trend views refuse cross-version comparison without an explicit recompute, and a weight
change requires a `scoring_model_version` bump and a changelog entry.
