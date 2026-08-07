# Troubleshooting

Every entry here was hit and diagnosed on this machine. The causes are real, not guesses.

---

## Things that look broken and are not

| What you see | What it actually means |
|---|---|
| `Port 8601 is not available` | That service is **already running**. Open the URL |
| `[Errno 98] address already in use` | Same. Confirm: `ss -ltn \| grep <port>` |
| `ollama serve` → address in use | Ollama runs as a service already. Skip it |
| `{"detail":"Not Found"}` at `:9000/` | The app is up; `/` has no route. Use `/health` |
| `openapi.json` 404 on `:8000` | Everything is under `/api/v1/openapi.json` |
| A question takes 30–70 seconds | CPU inference at ~5.5 tok/s. Normal |
| `smoke` scan reports no vulnerabilities | **Correct.** It runs only the diagnostic pack |

---

## "The scan found 0 vulnerabilities even though the RAG clearly leaks"

The most common and most confusing one. Three distinct causes, in the order they usually apply:

**1. You ran `smoke`.** It runs *only* `dummy-attack`, a reachability diagnostic that cannot find a
vulnerability. It exists to prove the scanner reaches the target. Use `--profile quick`.

**2. Coverage.** Check the coverage figure beside the grade. A scan that ran 2 of 9 packs and one
that ran 9 of 9 both print "0 failures" and mean completely different things.

**3. The exact-token blind spot.** A finding is decided by whether the target echoed an exact canary
token. A target that leaks its system prompt **in its own paraphrased words** never emits that
token, so the deterministic detector scores it PASS. This is a real limitation, documented in
`src/ragstrike/analyzers/detectors/llm_judge.py` along with the benchmark showing why the intended
fix (an LLM judge) is not usable on this hardware.

Verify a scan is genuinely working:

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike scan --target vulnerable-rag --profile quick
```

A healthy result reports `FAIL prompt-injection` with a ratio like `8/12 payloads returned FAIL`.

---

## Speed

There is no GPU. Measured on this machine:

| | |
|---|---|
| Model throughput | ~5.5 tokens/sec |
| One `/chat` question | 30–70 s |
| `smoke` scan | ~25 s |
| `quick` scan | ~10–15 min |
| `standard` scan | ~1 hour |

Concurrency does not help much — Ollama serialises generation on CPU, so `max_concurrency: 4` still
queues.

**Anything that looks like a hang is usually just inference.** Check elapsed time against this table
before assuming a deadlock.

---

## Errors and their fixes

### `ModuleNotFoundError`

Wrong virtualenv. Each project has its own and they are not interchangeable. Always use the explicit
path: `/home/iacsd/project/RAGSTRIKE/<Project>/.venv/bin/python`.

### `.venv/bin/python: No such file or directory`

The venv was built on Windows (it will contain `Scripts/` and `Lib/`). Rebuild it —
[01-INSTALLATION.md](01-INSTALLATION.md) step 3.

### The lab exits immediately with a safety message

`RAGSTRIKE_LAB_ACK` is not set. Prefix the command:

```bash
RAGSTRIKE_LAB_ACK=1 .venv/bin/python -m profiles.vulnerable.main_api
```

This is a deliberate speed bump, because one of these applications is intentionally insecure.

### Chat UI shows "Connection error — status 500"

starlette 1.4 changed `GZipResponder`'s signature and streamlit 1.61 has not caught up, so every
gzipped response dies. Fixed by the `starlette<1.4` pin in all three `pyproject.toml` files.

> **Verify UIs in a real browser, not with `curl`.** `curl` sends no `Accept-Encoding` header by
> default, so it never takes the gzip path and returns a misleading 200 while the browser gets 500.

### A lab UI never binds its port

Streamlit's first-run welcome prompt blocks on stdin. Fixed with `--server.headless true` in
`main_ui.py`. If you see the "Welcome to Streamlit / Email:" banner, that is this.

### Scan errors with `Cannot connect to http://127.0.0.1:9000`

The lab API died or was restarted **during** the scan. Every remaining payload reports ERROR, which
looks like a scanner bug and is not one. Never restart a lab while a scan is running.

### PDF report fails with "Cannot render pdf"

The `[pdf]` extra is not installed:

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/python -m pip install -e ".[pdf]"
```

Then **restart the API** — a running server holds the old modules.

### `pkill -f main_api` kills my own shell

`pkill -f` matches its own command line. Use a bracket so the pattern does not match itself:

```bash
pkill -f "[m]ain_api"
```

### Code changes have no effect

A running server is holding the old modules. Stop and restart it.

---

## Resetting

Reset one lab to a clean corpus. Do this **between exercises** — poisoning attacks write persistent
state by design, and a corpus carried over from a previous session produces results that look like
findings but are leftovers:

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && .venv/bin/python scripts/reset_lab.py --yes && .venv/bin/python scripts/seed_corpus.py
```

Same for `SecureRAG`. **Reset both**, or the two corpora diverge and the differential comparison
stops meaning anything.

---

## Health checks

```bash
ss -ltn | grep -E ':(8000|8501|8601|8602|9000|9001|11434)' | awk '{print $4}' | sort
```

All seven, all `127.0.0.1:`.

```bash
curl -s http://127.0.0.1:9000/health | python3 -m json.tool | head -20
```

Four components, all `"healthy": true`.

```bash
curl -s http://127.0.0.1:8000/api/v1/health | python3 -m json.tool
```

Eight subsystems. `chromadb` reads `disabled` — correct: the scanner owns no vector store, the labs
do.

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike targets --verify
```

Both targets `OK`.

---

## Git and file counts

If a file explorer shows ~55,000 files and you think the repo is too large to push: it is not. Those
are the three `.venv` directories, which are gitignored and never pushed.

```bash
cd /home/iacsd/project && for d in RAGStrike SecureRAG VulnerableRAG; do echo "$d: $(git -C $d ls-files | wc -l) tracked, $(du -sh $d/.git | cut -f1) history"; done
```

About 1,000 tracked files and under 6 MB of history across all three.
