# Starting the project again

**This is the file to open when you come back to the project after shutting it down.**

Everything is already installed. This page is only about starting the services again, in order,
and knowing they are up.

If this is a brand-new machine, do [01-INSTALLATION.md](01-INSTALLATION.md) first.

> **Just copied this from an SSD or cloned it from GitHub?** The `.venv/` folders are not included.
> Run [01-INSTALLATION.md](01-INSTALLATION.md) once, then come back here. A quick way to tell:
> `ls RAGStrike/.venv` — if that fails, you need to install first.

---

## The short version

Six terminals. One command each. Start them in this order.

| Terminal | Directory | What it starts | Port |
|---|---|---|---|
| 1 | anywhere | Ollama (model runtime) | 11434 |
| 2 | `VulnerableRAG` | the vulnerable lab API | 9000 |
| 3 | `SecureRAG` | the hardened lab API | 9001 |
| 4 | `RAGStrike` | the scanner API | 8000 |
| 5 | `RAGStrike` | the scanner dashboard | 8501 |
| 6 | `VulnerableRAG` / `SecureRAG` | the two chat UIs | 8601 / 8602 |

**Order matters in two places:** the lab APIs must be up before you scan them, and the RAGStrike API
(terminal 4) must be up before its dashboard (terminal 5), or the dashboard shows BACKEND OFFLINE.

---

## Terminal 1 — Ollama

```bash
ollama serve
```

If it says **"address already in use"**, Ollama is already running as a service. That is fine —
leave it and move on. Check it with:

```bash
curl -s http://127.0.0.1:11434/api/tags | python3 -m json.tool | grep '"name"'
```

You should see `qwen2.5:3b` and `nomic-embed-text`.

---

## Terminal 2 — VulnerableRAG API (port 9000)

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && RAGSTRIKE_LAB_ACK=1 .venv/bin/python -m profiles.vulnerable.main_api
```

Wait for: `VULNERABLE profile assembled -- 0 security policies active`

---

## Terminal 3 — SecureRAG API (port 9001)

```bash
cd /home/iacsd/project/RAGSTRIKE/SecureRAG && RAGSTRIKE_LAB_ACK=1 .venv/bin/python -m profiles.secure.main_api
```

Wait for: `SECURE profile assembled -- 7 security policies active`

> **Those two lines are the whole project in one sentence.** 0 controls versus 7 is the only
> difference between the two applications. Everything else — same code, same corpus, same model.

`RAGSTRIKE_LAB_ACK=1` is a deliberate speed bump. Both labs refuse to start without it, because one
of them is intentionally insecure.

---

## Terminal 4 — RAGStrike API (port 8000)

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/ragstrike-api
```

API docs: <http://127.0.0.1:8000/api/v1/docs>

Note the `/api/v1` prefix — there is nothing at `/openapi.json`, only at `/api/v1/openapi.json`.

---

## Terminal 5 — RAGStrike dashboard (port 8501)

**Start terminal 4 first.** The dashboard is a pure HTTP client of that API.

```bash
cd /home/iacsd/project/RAGSTRIKE/RAGStrike && .venv/bin/streamlit run src/ragstrike/dashboard/app.py
```

Open <http://127.0.0.1:8501>

---

## Terminal 6 — the two chat UIs (ports 8601, 8602)

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && RAGSTRIKE_LAB_ACK=1 .venv/bin/python -m profiles.vulnerable.main_ui
```

```bash
cd /home/iacsd/project/RAGSTRIKE/SecureRAG && RAGSTRIKE_LAB_ACK=1 .venv/bin/python -m profiles.secure.main_ui
```

- VulnerableRAG chat → <http://127.0.0.1:8601>
- SecureRAG chat → <http://127.0.0.1:8602>

These two side by side are the best thing to show an audience: ask both the same attack question
and watch one comply and the other refuse.

---

## Start everything from ONE terminal instead

If you would rather not manage six terminals, run these five commands in one. Each starts detached
and keeps running after you close the shell.

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

```bash
cd /home/iacsd/project/RAGSTRIKE/VulnerableRAG && RAGSTRIKE_LAB_ACK=1 setsid nohup .venv/bin/python -m profiles.vulnerable.main_ui > /tmp/vuln_ui.log 2>&1 < /dev/null & disown
```

```bash
cd /home/iacsd/project/RAGSTRIKE/SecureRAG && RAGSTRIKE_LAB_ACK=1 setsid nohup .venv/bin/python -m profiles.secure.main_ui > /tmp/secure_ui.log 2>&1 < /dev/null & disown
```

Give the lab APIs about 15 seconds each — they open ChromaDB and probe Ollama on startup.

---

## Confirm everything is up

```bash
ss -ltn | grep -E ':(8000|8501|8601|8602|9000|9001|11434)' | awk '{print $4}' | sort
```

You want all seven, and **every one must read `127.0.0.1:`** — never `0.0.0.0:` or `*:`. These
applications are loopback-only by design; one of them is deliberately insecure.

Then check the labs are actually healthy, not merely listening:

```bash
curl -s http://127.0.0.1:9000/health | python3 -m json.tool | head -20
```

All four components (`database`, `vector_store`, `ollama`, `model`) must be `"healthy": true`.
Repeat for port 9001.

---

## Stopping everything

```bash
pkill -f "[m]ain_api"; pkill -f "[m]ain_ui"; pkill -f "[r]agstrike-api"; pkill -f "[s]treamlit run"
```

> The square brackets are not a typo. `pkill -f main_api` matches **its own command line** and kills
> the shell running it. `[m]ain_api` matches the same processes without matching itself.

---

## Things that look broken and are not

| What you see | What it means |
|---|---|
| `Port 8601 is not available` | That service is **already running**. Not an error — just open the URL |
| `[Errno 98] address already in use` | Same. Check with `ss -ltn \| grep <port>` |
| `{"detail":"Not Found"}` at `:9000` | The app is running; `/` has no route. Use `/health` or `/docs` |
| A question takes 30–70 seconds | Normal. CPU inference — see below |
| `ollama serve` → address in use | Ollama is already running as a service. Skip it |

**On speed.** There is no GPU on this machine, so the model runs on CPU at roughly 5.5 tokens per
second. A single question takes 30–70 seconds and a `quick` scan takes tens of minutes. That is the
hardware, not a fault. Full numbers are in [05-TROUBLESHOOTING.md](05-TROUBLESHOOTING.md).

**Never restart a lab API while a scan is running.** The scan will report `ERROR — Cannot connect`
for every remaining payload, which looks like a scanner bug and is not one.
