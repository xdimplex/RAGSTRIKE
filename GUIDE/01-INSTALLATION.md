# First-time installation

> ### ⚠️ The virtual environments are NOT included
>
> This copy of the project ships **source only**. The three `.venv/` folders were removed before
> export — they were 2.8 GB and 79,000 files between them, against roughly 6 MB of actual source.
>
> **You must create them.** Section 3 below does exactly that, and takes about five minutes on a
> normal connection. Nothing else is missing: the code, the configs, the corpus and the databases
> are all here.

For a machine that has never run this project. If everything is already installed and you just want
to start it, go to [02-START-EVERY-TIME.md](02-START-EVERY-TIME.md).

Target platform: **Linux / WSL2**. The older `RAGStrike/docs/runbook.md` is written for Windows
PowerShell against `D:\Project\` — that was the original development machine, not this one.

---

## 1. Prerequisites

```bash
python3 --version
```

Needs **3.11 or later**. This machine runs 3.13.

```bash
sudo apt-get install -y python3-venv
```

---

## 2. Ollama and the models

Ollama must be installed and running. Then pull both models:

```bash
ollama pull qwen2.5:3b
```

```bash
ollama pull nomic-embed-text
```

Confirm:

```bash
curl -s http://127.0.0.1:11434/api/tags | python3 -m json.tool | grep '"name"'
```

> **Why `qwen2.5:3b` and not `qwen3:4b`.** Qwen3 is a *reasoning* model: it narrates its thinking in
> plain prose before answering, and Ollama's `think: false` does not suppress that. Measured on this
> machine with the same prompt: qwen3:4b took 74s and 246 tokens with the answer buried in
> reasoning; qwen2.5:3b took 32s and 23 tokens and answered directly. On a CPU at ~5.5 tokens/sec
> that difference is the whole reason the assistant felt slow.

---

## 3. The three virtual environments

Each project has its own venv. **They are not interchangeable** — a `ModuleNotFoundError` almost
always means the wrong `.venv/bin/python`.

> If you copied this project from Windows, the `.venv` directories will contain `Scripts/` and
> `Lib/` instead of `bin/` and `lib/`. Those are Windows venvs and cannot run here. The commands
> below delete and rebuild them, which is correct.

**VulnerableRAG:**

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && rm -rf .venv && python3 -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -e ".[ui,dev]"
```

**SecureRAG:**

```bash
cd /home/iacsd/project/RAGSTRIKE/SecureRAG && rm -rf .venv && python3 -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -e ".[ui,dev]"
```

**RAGStrike** — install the extras, not just the base package:

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && rm -rf .venv && python3 -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip && .venv/bin/python -m pip install -e ".[dashboard,pdf,dev]"
```

> Without `pdf`, report generation fails at runtime with *"Cannot render pdf"* — the reporter is
> present but its library is not.

**Verify all three:**

```bash
/home/iacsd/project/RAGSTRIKE/VulnerableRAG/.venv/bin/python -c "import rag, chromadb; print('VulnerableRAG OK')" && /home/iacsd/project/RAGSTRIKE/SecureRAG/.venv/bin/python -c "import rag, chromadb; print('SecureRAG OK')" && /home/iacsd/project/RAGSTRIKE/RAGStrike/.venv/bin/ragstrike version
```

---

## 4. Seed the lab corpora

Both labs must hold the **same** documents, or the differential comparison measures nothing.

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && .venv/bin/python scripts/seed_corpus.py
```

```bash
cd /home/iacsd/project/RAGSTRIKE/SecureRAG && .venv/bin/python scripts/seed_corpus.py
```

Do **not** pass `--include-poisoned` on a first run. Those documents are the payload of the
context-poisoning exercise; ingesting them up front destroys the clean baseline every attack is
measured against.

> The demo documents in `/home/iacsd/project/RAGSTRIKE/sample-corpus/` are **not** seeded by this step, on
> purpose — they exist so you can demonstrate the upload path live through the UI. See
> [04-DEMO.md](04-DEMO.md).

---

## 5. Verify the whole stack

Start everything using [02-START-EVERY-TIME.md](02-START-EVERY-TIME.md), then:

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike targets --verify
```

Both targets must report `OK`. Then run the diagnostic scan:

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike scan --target vulnerable-rag --profile smoke
```

> `smoke` runs **only** `dummy-attack`, a reachability diagnostic. It proves the scanner can reach
> and exercise the target. **It finds no vulnerabilities, by design** — a failure here means the
> *scanner* is broken, not the target. To actually find something, run `--profile quick`.

---

## 6. Optional: the quality gates

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/python -m pytest -q
```

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/lint-imports
```

`lint-imports` checks the six architectural layering contracts. A failure there is a **design**
failure, not a lint failure, and the fix is essentially never to edit the contract file.

---

## Known first-run problems, already fixed

These were all hit and repaired during the Linux bring-up. They are listed so that if you see one,
you know it is a known shape and where the fix lives.

| Symptom | Cause | Where it is fixed |
|---|---|---|
| `.venv/bin/python: No such file` | Windows venv copied from `D:\` | Step 3 rebuilds it |
| Every `/chat` empty after exactly 180s | `max_tokens` exceeded `timeout_s` | `configs/config.yaml` — 224 tokens / 300s |
| Chat UI shows "Connection error — status 500" | starlette 1.4 vs streamlit 1.61 incompatibility | `starlette<1.4` pin in all three `pyproject.toml` |
| A lab UI never binds its port | Streamlit's first-run email prompt blocking on stdin | `--server.headless true` in `main_ui.py` |
| Dashboard prints a public External URL | Streamlit defaults to `0.0.0.0` | `RAGStrike/.streamlit/config.toml` |
| SecureRAG seeding → `No module named 'profiles.vulnerable'` | fork leftover | `SecureRAG/scripts/seed_corpus.py` |
| Scans fail with `did not respond within 60s` | SDK stamped a hardcoded timeout over the configured one | `sdk/request_builder/builder.py` |
