# RAGStrike — Linux / WSL Runbook

Every command here was executed on this machine during the Linux bring-up and its output observed.
Where a number appears (timings, throughput), it was measured, not estimated.

The original `docs/runbook.md` is written for Windows PowerShell against `D:\Project\`. This file is
the Linux equivalent, rooted at `/home/iacsd/project/RAGSTRIKE/`.

---

## 0. What you are starting

Three separate applications, seven listening ports, all bound to loopback.

| Service | Port | Project | Purpose |
|---|---|---|---|
| Ollama | 11434 | system | model runtime (`qwen3:4b`, `nomic-embed-text`) |
| VulnerableRAG API | 9000 | VulnerableRAG | the deliberately weak target |
| VulnerableRAG UI | 8601 | VulnerableRAG | chat interface for the weak target |
| SecureRAG API | 9001 | SecureRAG | the hardened twin |
| SecureRAG UI | 8602 | SecureRAG | chat interface for the hardened twin |
| RAGStrike API | 8000 | RAGStrike | REST surface, `/api/v1` |
| RAGStrike dashboard | 8501 | RAGStrike | operator console |

**Each project has its own virtualenv. They are not interchangeable.** There is no shared venv and
no global install; `ModuleNotFoundError` almost always means the wrong `.venv/bin/python`.

---

## 1. Prerequisites

```bash
python3 --version
```

Needs 3.11 or later. This machine runs 3.13.5.

```bash
sudo apt-get install -y python3-venv
```

Ollama, with both models:

```bash
ollama pull qwen3:4b
```

```bash
ollama pull nomic-embed-text
```

Confirm Ollama is up and holding both:

```bash
curl -s http://127.0.0.1:11434/api/tags | python3 -m json.tool | grep '"name"'
```

If Ollama is not running, start it in its own terminal with `ollama serve`. "address already in use"
means it is already running as a service — that is fine, skip it.

---

## 2. One-time setup

### 2.1 Build the three virtualenvs

If you copied this project from Windows, the `.venv` directories contain `Scripts/` and `Lib/`
instead of `bin/` and `lib/`. Those are Windows venvs and cannot run here — delete and rebuild.

VulnerableRAG:

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && rm -rf .venv && python3 -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -e ".[ui]"
```

SecureRAG:

```bash
cd /home/iacsd/project/RAGSTRIKE/SecureRAG && rm -rf .venv && python3 -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -e ".[ui]"
```

RAGStrike — install the extras, not just the base package. Without `pdf` the PDF reporter is missing
at runtime and `POST /reports {"format":"pdf"}` fails with *"Cannot render pdf"*:

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && python3 -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -e ".[dashboard,pdf,dev]"
```

Verify all three:

```bash
/home/iacsd/project/RAGSTRIKE/VulnerableRAG/.venv/bin/python -c "import rag, chromadb; print('VulnerableRAG OK')" && /home/iacsd/project/RAGSTRIKE/SecureRAG/.venv/bin/python -c "import rag, chromadb; print('SecureRAG OK')" && /home/iacsd/project/RAGSTRIKE/RAGStrike/.venv/bin/ragstrike version
```

### 2.2 Seed both corpora

Both labs must hold the same documents or the differential comparison means nothing.

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && .venv/bin/python scripts/seed_corpus.py
```

```bash
cd /home/iacsd/project/RAGSTRIKE/SecureRAG && .venv/bin/python scripts/seed_corpus.py
```

Do **not** pass `--include-poisoned` for a first run. The poisoned documents are the payload of the
context-poisoning exercise; ingesting them up front destroys the clean baseline the attacks are
measured against.

---

## 3. Every session — starting the stack

`RAGSTRIKE_LAB_ACK=1` is a deliberate speed bump on both lab apps. They refuse to start without it.

Run each block in its own terminal, or use the detached form shown in §3.5.

### 3.1 VulnerableRAG API (9000)

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && RAGSTRIKE_LAB_ACK=1 .venv/bin/python -m profiles.vulnerable.main_api
```

Expect: `VULNERABLE profile assembled -- 0 security policies active`.

### 3.2 SecureRAG API (9001)

```bash
cd /home/iacsd/project/RAGSTRIKE/SecureRAG && RAGSTRIKE_LAB_ACK=1 .venv/bin/python -m profiles.secure.main_api
```

Expect: `SECURE profile assembled -- 7 security policies active`.

**Those two log lines are the whole project in miniature.** 0 vs 7 is the only difference between the
applications.

### 3.3 RAGStrike API (8000)

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike-api
```

Docs at <http://127.0.0.1:8000/api/v1/docs>. Note the `/api/v1` prefix — there is nothing at
`/openapi.json`, only at `/api/v1/openapi.json`.

### 3.4 RAGStrike dashboard (8501)

Start the API first; the dashboard is an HTTP client of it (ADR-010) and shows BACKEND OFFLINE
otherwise.

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/streamlit run src/ragstrike/dashboard/app.py
```

Binding comes from `.streamlit/config.toml`, which pins loopback. Do not override it with
`--server.address 0.0.0.0`.

### 3.5 The two lab chat UIs (8601, 8602)

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && RAGSTRIKE_LAB_ACK=1 .venv/bin/python -m profiles.vulnerable.main_ui
```

```bash
cd /home/iacsd/project/RAGSTRIKE/SecureRAG && RAGSTRIKE_LAB_ACK=1 .venv/bin/python -m profiles.secure.main_ui
```

These two side by side are the best demo asset in the project: ask both the same attack question and
watch one comply and the other refuse.

### 3.6 Starting everything detached (one terminal)

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && RAGSTRIKE_LAB_ACK=1 setsid nohup .venv/bin/python -m profiles.vulnerable.main_api > /tmp/vuln_api.log 2>&1 < /dev/null & disown
```

```bash
cd /home/iacsd/project/RAGSTRIKE/SecureRAG && RAGSTRIKE_LAB_ACK=1 setsid nohup .venv/bin/python -m profiles.secure.main_api > /tmp/secure_api.log 2>&1 < /dev/null & disown
```

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && setsid nohup .venv/bin/ragstrike-api > /tmp/rs_api.log 2>&1 < /dev/null & disown
```

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && setsid nohup .venv/bin/streamlit run src/ragstrike/dashboard/app.py > /tmp/rs_dash.log 2>&1 < /dev/null & disown
```

Give the lab APIs ~15 seconds each — they open ChromaDB and probe Ollama on startup.

### 3.7 Confirm all seven ports

```bash
ss -ltn | grep -E ':(8000|8501|8601|8602|9000|9001|11434)' | awk '{print $4}' | sort
```

Every address must read `127.0.0.1:` — never `0.0.0.0:` or `*:`.

---

## 4. Verifying before you scan

```bash
curl -s http://127.0.0.1:9000/health | python3 -m json.tool | head -30
```

All four components (`database`, `vector_store`, `ollama`, `model`) must be `"healthy": true`, and
`document_count` must be non-zero. Repeat for port 9001.

A real question, end to end — this is the honest check that generation works:

```bash
curl -s --max-time 300 -X POST http://127.0.0.1:9000/chat -H 'Content-Type: application/json' -d '{"message":"What is the leave policy?"}' | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['answer'][:300]); print('chunks:', d['chunk_count'], 'sources:', d['sources'], 'ms:', d['elapsed_ms'])"
```

**Expect this to take 60–110 seconds on CPU.** That is normal, not a hang. See §7.

Then the scanner's own view:

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike targets --verify
```

Both targets must report `OK`. Also useful:

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike plugins
```

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike profiles
```

---

## 5. Scanning

Always run `smoke` first. It runs only `dummy-attack`, whose entire job is to prove the harness
reaches the target. **A failure there means the scanner is broken, not the target.**

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike scan --target vulnerable-rag --profile smoke
```

Then the real one:

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike scan --target vulnerable-rag --profile quick
```

Then the comparison — this is the point of the whole project:

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike scan --target secure-rag --profile quick
```

### Measured cost on this machine

`qwen3:4b` on CPU measures **~5.5 tokens/second**, and one generation takes **65–120 seconds**.
Every payload is a full round trip, so:

| Profile | Packs | Payloads × attempts | Generations | Realistic wall time |
|---|---|---|---|---|
| `smoke` | 1 | 1 × 1 | 1 | ~1–2 min |
| `quick` | 3 | 10 × 2 | ~20 | ~25–40 min |
| `standard` | 9 | 46 × 3 | ~138 | ~3 hours |
| `deep` | 9 | 59 × 5 | ~295 | ~6+ hours |

There is no shortcut that preserves the result. A cached or mocked response tests the harness, not
the target.

For long scans, run detached and watch the log:

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && setsid nohup .venv/bin/ragstrike scan --target vulnerable-rag --profile standard > /tmp/scan_standard.log 2>&1 < /dev/null & disown
```

```bash
tail -f /tmp/scan_standard.log | sed 's/\x1b\[[0-9;]*m//g'
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | findings exceeded threshold |
| 2 | configuration error |
| 3 | target unreachable |
| 4 | scan errored |
| 5 | authorization missing |

---

## 6. Reading results and generating reports

List scans:

```bash
curl -s http://127.0.0.1:8000/api/v1/scans | python3 -m json.tool | head -40
```

One scan — note `coverage`, `grade`, and `findings_count` together:

```bash
curl -s http://127.0.0.1:8000/api/v1/scans/<SCAN_ID> | python3 -m json.tool
```

Findings, including the SKIPPED rows that record coverage gaps:

```bash
curl -s http://127.0.0.1:8000/api/v1/scans/<SCAN_ID>/findings | python3 -m json.tool | head -60
```

Generate a report — all four formats work once `[pdf]` is installed:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/scans/<SCAN_ID>/reports -H 'Content-Type: application/json' -d '{"format":"html"}'
```

Substitute `markdown`, `json`, or `pdf`. Output lands in
`/home/iacsd/project/RAGSTRIKE/RAGStrike/reports/<SCAN_ID>/`.

**Read coverage before you read the grade.** A scan of 11% of the surface reporting "no failures"
and a scan of 100% reporting the same are completely different facts, and the headline is identical.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `.venv/bin/python: No such file` | Windows venv (`Scripts/`, `Lib/`) copied from `D:\` | Rebuild it — §2.1 |
| Lab app exits with a safety message | `RAGSTRIKE_LAB_ACK` unset | Prefix the command with `RAGSTRIKE_LAB_ACK=1` |
| `Port NNNN is not available` / `[Errno 98] address already in use` | That service is **already running** | Not an error. Check with `ss -ltn \| grep NNNN`. Only restart it if you changed its code |
| SecureRAG seeding → `ModuleNotFoundError: profiles.vulnerable` | Fork leftover in `scripts/seed_corpus.py` | Already fixed — it now imports `profiles.secure` |
| `/chat` takes 60–110s | CPU inference at ~5.5 tok/s | Normal. A GPU cuts this ~10× |
| `/chat` returns nothing after exactly 180s | `model.max_tokens` exceeds what fits in `model.timeout_s` | Already fixed: 384 tokens / 300s in `configs/config.yaml` |
| Scan reports COMPLETED but ran few packs | `scan_timeout_s` too small for CPU speed | Already raised in `configs/profiles/*.yaml` |
| `{"detail":"Not Found"}` on `:9000/` | The app is running; `/` has no route | Use `/health` or `/docs` |
| `openapi.json` 404 on `:8000` | Everything is under `/api/v1` | Use `/api/v1/openapi.json` |
| PDF report → "Cannot render pdf" | `[pdf]` extra not installed | `pip install -e ".[pdf]"`, then **restart the API** |
| Lab UI never binds its port | Streamlit's first-run email prompt blocking on stdin | Already fixed with `--server.headless true` in `main_ui.py` |
| Dashboard prints an External URL on a public IP | Streamlit defaults to `0.0.0.0` | Already fixed by `.streamlit/config.toml` |
| Any Streamlit UI shows "Connection error — status 500" in a browser, `Exception in ASGI application` / `GZipResponder.__init__() missing 1 required keyword-only argument: 'thread_minimum_size'` in its log | starlette 1.4.0 vs streamlit 1.61.0 incompatibility | Already fixed by the `starlette<1.4` pin. **Verify UIs in a browser, not with curl** — curl sends no `Accept-Encoding` by default, so it returns 200 while the browser gets 500 |
| Scan errors with `did not respond within 60s` although `targets.yaml` says otherwise | SDK request builder stamped a hardcoded 60s over the target's configured timeout | Already fixed — the builder now leaves it unset so `targets.yaml` applies |
| Dashboard says BACKEND OFFLINE | `ragstrike-api` not started | Start it first — §3.3 |
| Code changes have no effect | A running server is holding the old module | Stop and restart it |
| `pkill -f main_api` kills your own shell | The pattern matches the `pkill` command line itself | Use a bracket: `pkill -f "[m]ain_api"` |

Stop everything:

```bash
pkill -f "[m]ain_api"; pkill -f "[m]ain_ui"; pkill -f "[r]agstrike-api"; pkill -f "[s]treamlit run"
```

Reset a lab between exercises — poisoning attacks write persistent state by design, and a corpus
carried over from a previous session produces results that look like findings but are leftovers:

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && .venv/bin/python scripts/reset_lab.py --yes && .venv/bin/python scripts/seed_corpus.py
```

---

## 8. Running the test suite

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/python -m pytest -q
```

Architecture contracts (a failure here is a design failure, not a lint failure):

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/lint-imports
```

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/mypy src/ragstrike
```
