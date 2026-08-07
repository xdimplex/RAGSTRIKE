# Deployment guide

> SecureRAG is a **lab application**. This guide covers running it on loopback beside VulnerableRAG.
> It is not a production deployment guide, and the distinction is not a formality — see the last
> section.

---

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) running locally
- Models pulled:

```bash
ollama pull qwen3:4b
ollama pull nomic-embed-text
```

---

## Install

```bash
cd SecureRAG
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on POSIX
pip install -e ".[ui,dev]"
```

---

## Run

Both entry points refuse to start without the acknowledgement variable:

```bash
RAGSTRIKE_LAB_ACK=1 python -m profiles.secure.main_api    # API on 9001
RAGSTRIKE_LAB_ACK=1 python -m profiles.secure.main_ui     # UI  on 8602
```

On Windows PowerShell:

```powershell
$env:RAGSTRIKE_LAB_ACK = "1"; python -m profiles.secure.main_api
```

### Why the hardened half still has a gate

SecureRAG is **hardened, not audited**. Every control was written and tested against the attacks its
author thought of; that is not the same claim as "safe to expose". It also ingests the same synthetic
corpus as VulnerableRAG, canaries included, and that corpus belongs on loopback wherever it is
loaded. Keeping the startup behaviour identical between the two halves also matters: a lab where one
side starts differently is a lab where the difference between them is no longer only security.

---

## Running the pair

```bash
# terminal 1
cd VulnerableRAG && RAGSTRIKE_LAB_ACK=1 python -m profiles.vulnerable.main_api   # 9000

# terminal 2
cd SecureRAG     && RAGSTRIKE_LAB_ACK=1 python -m profiles.secure.main_api       # 9001
```

Ports, databases, and Chroma collections are all distinct, so the two never share state.

Seed both with the same corpus — the comparison is only meaningful over identical documents:

```bash
python scripts/seed_corpus.py
```

---

## Scanning with RAGStrike

`configs/targets.yaml` in the RAGStrike repository already carries a `secure-rag` entry pointing at
`http://127.0.0.1:9001`, disabled by default. Enable it:

```yaml
- name: secure-rag
  url: "http://127.0.0.1:9001"
  adapter: fastapi
  enabled: true          # <- was false
```

Then:

```bash
ragstrike targets --verify
ragstrike scan --target vulnerable-rag
ragstrike scan --target secure-rag
```

**RAGStrike requires no modification.** SecureRAG speaks the same API, declares the same
capabilities, and negotiates identically. The `fastapi` adapter options in `targets.yaml` apply
unchanged.

---

## Docker

`docker/` is inherited from VulnerableRAG and its compose file names the vulnerable profile. Point it
at `profiles.secure.main_api` and port 9001 before using it. It is not exercised by the test suite.

---

## Binding beyond loopback

`ServerSettings` warns rather than refuses when `host` is not loopback, because an operator may have
a reason. **There is no good reason here.** SecureRAG has no authentication, no authorization, and no
rate limiting — all three are declared and not implemented — so anything that can reach it can read
the whole corpus and spend the model budget.

If you are considering exposing this, read
[`security-features.md`](security-features.md#what-securerag-does-not-do) first.
