# Lab Safety

> Read this before running anything in this repository.

---

## What you are about to run

An application built to be broken. It will:

- Follow instructions found inside documents you upload
- Disclose its system prompt when asked
- Return synthetic credentials embedded in that prompt
- Apply no filtering to what the model produces
- Retrieve any document in the corpus regardless of who asked

This is intentional and documented. It is not a set of bugs to report.

---

## The containment rules

### 1. Loopback only. Always.

Every service binds to `127.0.0.1`. Compose publishes nothing beyond the host. **Do not change this
to make remote access convenient.**

Exposing this application to a network hands anyone who finds it a working attack surface: a document
upload endpoint that will execute what it ingests, on a host inside your perimeter, with an LLM
attached.

### 2. Never on shared infrastructure

No staging server, no shared VM, no cloud instance, no cluster your team can reach. A laptop or an
isolated local VM. That is the whole list.

### 3. Never with real data

The corpus is synthetic. Keep it that way.

- No real company documents
- No real personal data
- No real credentials — the lab's secrets are synthetic, high-entropy, and canary-tagged so a real
  one could never be confused with them
- No production PDFs "just to see what happens"

Every attack RAGStrike runs is recorded as evidence, and evidence is stored raw. Real data in the
corpus becomes real data in a database, in logs, and in report drafts.

### 4. Reset between sessions

```bash
python scripts/reset_lab.py
```

Poisoning attacks write persistent state. A corpus carried over from a previous session makes the
next run's results meaningless — and makes a "finding" that is really a leftover.

### 5. The acknowledgement gate

The application refuses to start without:

```bash
export RAGSTRIKE_LAB_ACK=1
```

This is a deliberate speed bump. If it is set in a shell profile or a Dockerfile somewhere, the gate
has been defeated and someone will eventually start this application without meaning to.

---

## What this repository is not

- **Not a template for a real RAG application.** The vulnerable profile is a catalogue of mistakes.
  If you want a reference implementation, read `profiles/secure/` and `rag/policy/controls/` — and
  read them as a starting point, not as a finished security posture.
- **Not a security product.** Neither profile is hardened against anything outside the documented
  threat model.
- **Not a place to report vulnerabilities.** Its weaknesses are the specification. A finding is only
  a bug if it is *not* in [`vulnerabilities.md`](vulnerabilities.md) — for example, a path traversal
  in the upload handler would be a genuine bug, because it is not one of the nine documented lessons.

---

## If you are teaching with this

- Run it on isolated machines you control, and say so explicitly at the start.
- Give learners the [`docs/the-diff.md`](the-diff.md) comparison. Watching the same attack succeed
  against one profile and fail against the other is the entire pedagogical point.
- Pair every attack exercise with its defence. An attack technique taught without its mitigation is
  half a lesson.
- Make the containment rules part of the exercise, not a footnote. Understanding *why* this must stay
  on loopback is itself a security lesson.

---

## Reporting

Vulnerabilities in **RAGStrike** (the scanner): see
[`../RAGStrike/SECURITY.md`](../RAGStrike/SECURITY.md).

Vulnerabilities in **this repository**: only if the weakness is not already in the catalogue. Check
[`vulnerabilities.md`](vulnerabilities.md) first.
