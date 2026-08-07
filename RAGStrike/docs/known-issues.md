# Known issues

> Symptoms you may hit, with the reason and the workaround. Distinct from
> [`limitations.md`](limitations.md), which is about what the framework *does not attempt*, and from
> [`technical-debt.md`](technical-debt.md), which is about what is owed internally.

---

## The dashboard says BACKEND OFFLINE

**Expected.** `/api/v1` is a scaffold with no handlers ([D-03](technical-debt.md)). The dashboard is
an HTTP client by design (ADR-010) and reports honestly when nothing answers.

**Workaround.** Use the CLI for real scans; use `RAGSTRIKE_DASHBOARD__TRANSPORT=demo` to explore the
interface with clearly-labelled fixtures.

---

## A scan takes a very long time

**Expected on CPU.** Every payload is a full RAG round trip through a local model — roughly 5–40
seconds each. A pack with 30 payloads is a 10–20 minute job, and a full differential across two
targets is measured in hours.

**Workarounds.** Scope with `--plugins`; keep the model warm between runs; use GPU inference if
available. For a demonstration, run one pack rather than all of them.

---

## `mypy src` reports 11 errors

**Expected and recorded.** [D-01](technical-debt.md). They predate the current subsystems. `mypy` on
any individual subsystem added in Phases 10–14 is clean.

---

## PDF export produces nothing

**Expected.** `formats()` reports `pdf: false` and the exporter skips it rather than writing a file
that would not open ([D-05](technical-debt.md)). HTML, Markdown, and JSON all work.

---

## A plugin is skipped with "capability not supported"

**Working as intended.** The target adapter declares its capabilities; a pack that needs one the
target lacks is skipped with a reason, and the skip appears in the report's Coverage section
(ADR-020). It is not a silent omission.

**If it is wrong**, the adapter is under-declaring — check its `capabilities()`.

---

## A scan refuses to start: "no authorization record"

**Working as intended.** ADR-017: authorization is a persisted record, not a checkbox. Create one for
the target before scanning.

---

## A non-local target is rejected

**Working as intended, and deliberately hard to change.** Default policy accepts `127.0.0.1` and
`localhost` only. Scanning a system you do not own is not a configuration question.

---

## Ollama returns a 500 on a long question

Very long inputs can exceed what the local model accepts. SecureRAG validates length at the HTTP
boundary before the pipeline runs; VulnerableRAG deliberately does not — that is one of the
vulnerabilities it exists to demonstrate.

---

## Windows: peak memory reports 0

**Fixed.** The ctypes call into `GetProcessMemoryInfo` needed explicit `argtypes` — without them the
`HANDLE` was truncated on 64-bit and the call silently failed. If you see a 0 again, the process
handle is the first thing to check.

---

## Reporting anything else

Include the RAGStrike version, the command, `configs/` (with any secrets removed — there is nowhere
in the schema to put one), and the relevant log lines. Log lines never contain document, question, or
answer text by design, so they are safe to attach.
