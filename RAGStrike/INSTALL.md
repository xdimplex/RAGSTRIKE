# Installation

> **Phase 1 status.** The scaffold is in place; the engine is not. These instructions get you a
> working *development environment* — linting, typing, layering checks, and the test harness. There
> is nothing to scan yet. Implementation begins in Phase 3.

---

## Requirements

| | Minimum | Notes |
|---|---|---|
| Python | 3.11 | `tomllib`, `TaskGroup`, `ExceptionGroup`, and `Self` are all used |
| Git | any recent | |
| Disk | ~2 GB | Mostly the Ollama model |
| RAM | 8 GB | 16 GB recommended for comfortable local inference |
| Docker | optional | Needed only for the lab (Phase 2+) |
| Ollama | optional | Needed only for the lab and the optional LLM judge |

Linux, macOS, and Windows are all supported and all tested in CI.

### If you do not have Python 3.11

[`uv`](https://docs.astral.sh/uv/) will fetch and manage one without touching your system Python:

```bash
uv python install 3.11
```

---

## Development install

```bash
git clone https://github.com/OWNER/ragstrike.git
cd ragstrike
```

**POSIX:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,dashboard]"
pre-commit install
```

**Windows PowerShell:**

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,dashboard]"
pre-commit install
```

`-e` (editable) matters: the plugin registry discovers first-party attack packs through entry points,
and a non-editable install requires reinstalling after every pack change.

---

## Verify

```bash
pytest                  # test suite
mypy src                # strict type checking
ruff check .            # lint
black --check .         # formatting
lint-imports            # the dependency rule
```

All five should pass on a clean checkout. If `lint-imports` fails, an import has crossed a layer
boundary — read the contract name it reports and check `ARCHITECTURE.md §1`.

---

## Configuration

```bash
cp .env.example .env
```

The defaults are deliberately restrictive: **the shipped configuration can only reach `localhost`.**
Pointing RAGStrike at anything else requires setting `allow_remote_targets: true` and adding an
allowlist entry — two deliberate steps, because accidentally scanning a third party is an incident.

Configuration precedence, lowest to highest (SDD §21.1):

```
built-in defaults → configs/ragstrike.yaml → profile → target file → RAGSTRIKE_* env → CLI/API
```

Secrets belong in `.env` only. Never in `configs/*.yaml`, never in code.

---

## Optional: Ollama

Needed for the lab targets and for the optional LLM judge detector.

```bash
# https://ollama.com/download
ollama pull qwen3
ollama serve            # listens on 127.0.0.1:11434
```

The judge is **off by default**. RAGStrike's core oracle is deterministic, and a scanner whose
verdicts change when someone upgrades a model cannot support trend analysis.

---

## Optional: the differential lab

From **Phase 2**, the companion repository provides the targets:

> Docker files are not shipped with this build. Run the three applications
> directly, as described above.

| Service | URL |
|---|---|
| VulnerableRAG API | http://127.0.0.1:9000 |
| VulnerableRAG UI | http://127.0.0.1:8601 |
| SecureRAG API | http://127.0.0.1:9001 |
| SecureRAG UI | http://127.0.0.1:8602 |

> ⚠️ **VulnerableRAG is intentionally insecure.** Every port binds to `127.0.0.1` and Compose
> publishes nothing beyond the host. Do not change that. See its `docs/LAB_SAFETY.md`.

---

## Running it (Phase 6+)

```bash
uvicorn ragstrike.api.app:app --host 127.0.0.1 --port 8000    # API
streamlit run src/ragstrike/dashboard/app.py                  # dashboard, separate process
ragstrike doctor                                              # environment diagnostics
```

Two processes is deliberate. The dashboard is an HTTP client of the API and never imports the engine
(ADR-010) — which is what keeps the API provably complete and the UI replaceable.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `lint-imports` fails | An import crossed a layer boundary | Read the contract name; check `ARCHITECTURE.md §1` |
| `mypy` errors on a fresh clone | Wrong interpreter | Confirm the venv is active and is 3.11+ |
| Plugin not discovered | Non-editable install, or a manifest error | Reinstall with `-e`; run `ragstrike packs validate` |
| Migration checksum mismatch | A released migration was edited | Never edit a released migration — write a new one. This failure is the safety net working. |
| Target unreachable | Loopback allowlist | Expected. Remote targets need explicit configuration. |
