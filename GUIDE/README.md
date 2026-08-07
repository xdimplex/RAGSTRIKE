# RAGStrike — Documentation

Everything needed to install, run, demo, and troubleshoot the project.

**Never run this before? → [00-WALKTHROUGH.md](00-WALKTHROUGH.md)** — the whole thing in one file,
setup through demo.

**Already installed and just want it running? → [02-START-EVERY-TIME.md](02-START-EVERY-TIME.md)**

---

| File | Read it when |
|---|---|
| [00-WALKTHROUGH.md](00-WALKTHROUGH.md) | **One file, start to finish** — install, start, verify, and run a complete demo, with the real measured numbers |
| [01-INSTALLATION.md](01-INSTALLATION.md) | Setting up a machine that has never run this |
| [02-START-EVERY-TIME.md](02-START-EVERY-TIME.md) | **Coming back after a shutdown** — which terminal, which command |
| [03-PROJECT-OVERVIEW.md](03-PROJECT-OVERVIEW.md) | Explaining what the project is and why it is built this way |
| [04-DEMO.md](04-DEMO.md) | Presenting it to an audience |
| [05-TROUBLESHOOTING.md](05-TROUBLESHOOTING.md) | Something is not working |

---

## The project in one paragraph

Three separate applications. **VulnerableRAG** is a deliberately insecure RAG chatbot;
**SecureRAG** is the same application with seven security controls switched on; **RAGStrike** is a
security scanner that attacks both. Running the same attack against both is what makes a finding
checkable — an attack that fires on both is measuring something other than the control it claims to
measure. Most scanners have no way to validate themselves; this one does.

---

## The seven services

| Service | Port | Where |
|---|---|---|
| Ollama | 11434 | system |
| VulnerableRAG API | 9000 | `VulnerableRAG/` |
| VulnerableRAG chat | 8601 | `VulnerableRAG/` |
| SecureRAG API | 9001 | `SecureRAG/` |
| SecureRAG chat | 8602 | `SecureRAG/` |
| RAGStrike API | 8000 | `RAGStrike/` |
| RAGStrike dashboard | 8501 | `RAGStrike/` |

All loopback-only. One of these applications is intentionally insecure — none of them should ever be
reachable from a network.

---

## Other folders

- **`sample-corpus/`** — ten demonstration documents (5 PDFs, 5 text files) for a fictional company.
  **Not pre-loaded**, on purpose, so the upload path can be demonstrated live. See its own README.
- **`issues/`** — the reported-issue PDFs that drove the last round of fixes.

---

## Deeper reference

This folder is the practical guide. The full engineering documentation lives inside each project:

| Document | Where |
|---|---|
| Software Design Document | `RAGStrike/docs/SDD.md` |
| Architecture Decision Records | `RAGStrike/docs/annex-c-adrs.md` |
| Attack catalog (all twelve packs) | `RAGStrike/docs/annex-b-attack-catalog.md` |
| What the tool does **not** do | `RAGStrike/docs/limitations.md` |
| Known issues and technical debt | `RAGStrike/docs/known-issues.md`, `technical-debt.md` |
| The ten weaknesses, reproduced | `VulnerableRAG/docs/vulnerabilities.md` |
| The seven controls | `SecureRAG/docs/controls.md` |

> The older `RAGStrike/docs/runbook.md` is written for **Windows PowerShell** against `D:\Project\`
> — the original development machine. For this Linux box, use
> [02-START-EVERY-TIME.md](02-START-EVERY-TIME.md) or `RAGStrike/docs/runbook-linux.md`.

---

## Measured performance

No GPU on this machine. Every timeout in the project is derived from these numbers:

| | |
|---|---|
| Model | `qwen2.5:3b` at ~5.5 tokens/sec |
| One chat answer | 30–70 s |
| `smoke` scan | ~25 s |
| `quick` scan | ~10–15 min |

**Anything that looks like a hang is usually just inference.** Check elapsed time before assuming a
deadlock.
