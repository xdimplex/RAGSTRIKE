# Runbook — every command, start to finish

Copy-paste order for a full demo. **PowerShell syntax** (Windows).

> **Environment variables in PowerShell are `$env:NAME = "value"`.**
> `set NAME=value` is CMD syntax and will not work in PowerShell — it silently sets a PowerShell
> variable instead of an environment variable, and the app will refuse to start with a message about
> the acknowledgement being missing.

---

## The layout

| What | Folder | Its own venv? | Port |
|---|---|---|---|
| Ollama (the AI model) | — | — | 11434 |
| VulnerableRAG API | `D:\Project\VulnerableRAG` | ✅ yes | **9000** |
| VulnerableRAG UI | same | same | 8601 |
| SecureRAG API | `D:\Project\SecureRAG` | ✅ yes | **9001** |
| SecureRAG UI | same | same | 8602 |
| RAGStrike CLI | `D:\Project\RAGStrike` | ✅ yes | — |
| RAGStrike API | same | same | **8000** |
| RAGStrike dashboard | same | same | 8501 |

**Each of the three projects has its own `.venv`.** They are not interchangeable. Activating the
wrong one is the most common cause of "module not found".

---

# ONE-TIME SETUP

Do this once, ever. Skip to *Every Session* if you have already done it.

## 1. Pull the AI models

```powershell
ollama pull qwen3:4b
ollama pull nomic-embed-text
```

Two models: one answers questions, one turns text into searchable vectors. ~3 GB total.

## 2. Install each project

**VulnerableRAG:**
```powershell
cd D:\Project\VulnerableRAG
.venv\Scripts\activate
pip install -e .
deactivate
```

**SecureRAG:**
```powershell
cd D:\Project\SecureRAG
.venv\Scripts\activate
pip install -e .
deactivate
```

**RAGStrike:**
```powershell
cd D:\Project\RAGStrike
.venv\Scripts\activate
pip install -e ".[dev,pdf,dashboard]"
deactivate
```

## 3. Seed the documents into both labs

Both apps must hold the **same** documents, or the comparison between them means nothing.

**VulnerableRAG:**
```powershell
cd D:\Project\VulnerableRAG
.venv\Scripts\activate
python scripts\seed_corpus.py
deactivate
```

**SecureRAG:**
```powershell
cd D:\Project\SecureRAG
.venv\Scripts\activate
python scripts\seed_corpus.py
deactivate
```

This generates three synthetic PDFs and ingests them. Takes a couple of minutes — each page has to
be turned into vectors by the embedding model.

> **Do not pass `--include-poisoned` yet.** The poisoned documents carry live attack payloads.
> Ingesting them up front poisons every session before it starts, so you would never see the clean
> baseline the attack is measured against. Add them deliberately, for a specific exercise.

---

# EVERY SESSION

Four terminal windows. Windows 1–3 stay open and print logs; **you only type in window 4.**

## Terminal 1 — Ollama

```powershell
ollama serve
```

*If it says "address already in use", Ollama is already running. That is fine — leave it.*

## Terminal 2 — VulnerableRAG (port 9000)

```powershell
cd D:\Project\VulnerableRAG
.venv\Scripts\activate
$env:RAGSTRIKE_LAB_ACK = "1"
python -m profiles.vulnerable.main_api
```

**Why the `RAGSTRIKE_LAB_ACK` line:** this app follows instructions found in uploaded documents and
gives up its system prompt on request. Starting it is meant to be a decision, not an accident.
Without that variable it refuses to start and tells you why.

**You should see:** `Starting VulnerableRAG API on http://127.0.0.1:9000 -- INTENTIONALLY VULNERABLE`

## Terminal 3 — SecureRAG (port 9001)

```powershell
cd D:\Project\SecureRAG
.venv\Scripts\activate
$env:RAGSTRIKE_LAB_ACK = "1"
python -m profiles.secure.main_api
```

## Terminal 4 — RAGStrike (this is where you work)

```powershell
cd D:\Project\RAGStrike
.venv\Scripts\activate
```

Your prompt now shows `(.venv)`. Every command below runs here.

---

# CHECK BEFORE YOU SCAN

```powershell
ragstrike targets --verify
```

**Expect:**
```
OK  vulnerable-rag   http://127.0.0.1:9000
OK  secure-rag       http://127.0.0.1:9001
```

**If either says unreachable, stop.** Nothing after this will mean anything. Check that terminal's
window for an error.

```powershell
ragstrike version      # engine + plugin API versions
ragstrike plugins      # the 9 packs
ragstrike profiles     # the 4 scan depths
```

---

# SCANNING

## Step 1 — Prove the pipeline works (seconds)

```powershell
ragstrike scan --target vulnerable-rag --profile smoke
```

Runs `dummy-attack` only. **A failure here means the scanner is broken, not the target** — a
completely different problem, and ten seconds well spent before a long scan.

## Step 2 — Your first real scan (2–13 minutes)

```powershell
ragstrike scan --target vulnerable-rag --profile quick
```

Runs `dummy-attack`, `prompt-injection`, `prompt-leakage`. About 19 questions asked.

**Watch the timing of the first pack.** If 8 calls take 2 minutes, you now know what `deep` would
cost on your machine.

## Step 3 — The comparison (this is the whole point)

```powershell
ragstrike scan --target secure-rag --profile quick
```

**Expect different results.** VulnerableRAG should show failures; SecureRAG should not. That
difference *is* your project working.

## Going deeper (optional)

```powershell
ragstrike scan --target vulnerable-rag --profile standard   # all 9 packs, 15 min – 1.8 hrs
ragstrike scan --target vulnerable-rag --profile deep       # every tier, 30 min – 3.5 hrs
```

## Reviewing

```powershell
ragstrike plugins info prompt-injection    # what one pack does
ragstrike plugins disable context-poisoning   # exclude a pack from future scans
ragstrike plugins enable context-poisoning    # put it back
```

---

# THE WEB INTERFACES (optional, for a demo)

Two more terminals, or reuse window 4 after your scans finish.

## Terminal 5 — RAGStrike API (port 8000)

```powershell
cd D:\Project\RAGStrike
.venv\Scripts\activate
ragstrike-api
```

Open **http://127.0.0.1:8000/api/v1/docs** — a clickable page listing all 17 endpoints, where you
can try each one in the browser. Good for a demo: it makes the engine visible.

## Terminal 6 — RAGStrike dashboard (port 8501)

```powershell
cd D:\Project\RAGStrike
.venv\Scripts\activate
streamlit run src\ragstrike\dashboard\app.py
```

**Start the API in Terminal 5 first**, or the dashboard shows `BACKEND OFFLINE` — which is honest,
not broken. It refuses to invent data it does not have.

## The lab UIs

VulnerableRAG and SecureRAG each have their own chat interface:

```powershell
# Terminal 7 — VulnerableRAG UI
cd D:\Project\VulnerableRAG
.venv\Scripts\activate
$env:RAGSTRIKE_LAB_ACK = "1"
python -m profiles.vulnerable.main_ui        # http://127.0.0.1:8601
```

```powershell
# Terminal 8 — SecureRAG UI
cd D:\Project\SecureRAG
.venv\Scripts\activate
$env:RAGSTRIKE_LAB_ACK = "1"
python -m profiles.secure.main_ui            # http://127.0.0.1:8602
```

**These are the best demo asset you have.** Ask both the *same* attack question, side by side, and
let the audience watch one comply and the other refuse.

---

# SHUTTING DOWN

Press **Ctrl+C** in each terminal. Order does not matter.

To wipe a lab back to a clean state:

```powershell
cd D:\Project\VulnerableRAG
.venv\Scripts\activate
python scripts\reset_lab.py
```

Then re-seed. Same for SecureRAG.

---

# THE MINIMUM DEMO — 6 commands

If you only have a few minutes in front of an audience:

```powershell
# Terminal 1
ollama serve

# Terminal 2
cd D:\Project\VulnerableRAG; .venv\Scripts\activate; $env:RAGSTRIKE_LAB_ACK = "1"
python -m profiles.vulnerable.main_api

# Terminal 3
cd D:\Project\SecureRAG; .venv\Scripts\activate; $env:RAGSTRIKE_LAB_ACK = "1"
python -m profiles.secure.main_api

# Terminal 4
cd D:\Project\RAGStrike; .venv\Scripts\activate
ragstrike targets --verify
ragstrike scan --target vulnerable-rag --profile quick
ragstrike scan --target secure-rag --profile quick
```

---

# WHEN SOMETHING GOES WRONG

| Symptom | Cause | Fix |
|---|---|---|
| `ragstrike` not recognised | venv not activated | `.venv\Scripts\activate` — or use `.venv\Scripts\ragstrike.exe` |
| App exits with a lab-safety message | `RAGSTRIKE_LAB_ACK` not set, **or set with CMD syntax** | `$env:RAGSTRIKE_LAB_ACK = "1"` |
| `targets --verify` says unreachable | That lab app is not running | Check terminals 2 and 3 for errors |
| `ModuleNotFoundError` | Wrong venv activated | Each project has its own. `deactivate`, then activate the right one |
| Scan very slow | Normal — 5–40 s per question on CPU | Use `--profile smoke` or `quick` |
| Ollama connection refused | Ollama not running | `ollama serve` |
| Dashboard says BACKEND OFFLINE | RAGStrike API not started | Run `ragstrike-api` in another terminal |
| Scan finds nothing on **both** apps | Something is wrong with the setup | Run `--profile smoke` — it isolates harness from target |
| Port already in use | An old process is still running | Close the old terminal, or `Get-Process python \| Stop-Process` |

---

# COMMAND REFERENCE

| Command | What it does |
|---|---|
| `ragstrike version` | Engine and plugin API versions |
| `ragstrike targets` | List configured targets |
| `ragstrike targets --verify` | **Probe each target — run this first** |
| `ragstrike profiles` | List scan depths |
| `ragstrike plugins` | List packs, active and refused |
| `ragstrike plugins info <slug>` | Details for one pack |
| `ragstrike plugins validate <slug>` | Check a pack against every rule |
| `ragstrike plugins enable <slug>` | Turn a pack on |
| `ragstrike plugins disable <slug>` | Turn a pack off |
| `ragstrike plugins reload` | Re-discover after adding a pack |
| `ragstrike scan --target <name> --profile <depth>` | **Run a scan** |
| `ragstrike-api` | Serve the HTTP API on 8000 |

| Exit code | Meaning |
|---|---|
| 0 | Success, nothing found |
| 1 | Findings exceeded the threshold |
| 2 | Configuration error |
| 3 | Target unreachable |
| 4 | Scan errored |
| 5 | Authorization missing |
