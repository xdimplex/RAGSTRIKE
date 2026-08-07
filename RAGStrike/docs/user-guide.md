# User guide

> For an operator running scans. If you are extending the framework, read
> [`developer-guide.md`](developer-guide.md).

---

## What RAGStrike does

It executes attack packs against a RAG application, analyzes the responses with deterministic
detectors, scores the result with published arithmetic, and produces a report in which every finding
traces back to the exact request, response, detector, and calculation that produced it.

**What it does not do:** guarantee anything. A clean scan means the shipped packs did not find the
weaknesses they test for — not that none exist. Coverage is reported beside every grade for exactly
this reason.

---

## Before your first scan

RAGStrike only scans targets it is **authorized** and **in scope** for, and both are enforced rather
than advised.

**Authorization** is a record, not a checkbox. Every target in `configs/targets.yaml` carries who
authorized testing it and under what reference, and no scan starts without one.

**Scope** is loopback-only by default. Pointing RAGStrike at anything else takes two deliberate
steps — setting `safety.allow_remote_targets: true` *and* adding the host to `safety.allowed_hosts` —
because accidentally scanning a third party is an incident, not an inconvenience.

---

## The commands

```bash
ragstrike version                  # engine, plugin API, adapters
ragstrike targets                  # what is configured
ragstrike targets --verify         # ... and what is reachable
ragstrike plugins                  # what is installed, and what was refused
ragstrike plugins info <slug>      # full metadata for one plugin
ragstrike plugins validate         # every validation rule against every plugin
ragstrike scan --target <name>     # run the full lifecycle
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success, threshold met |
| 1 | Findings exceeded the threshold |
| 2 | Configuration or validation error |
| 3 | Target unreachable |
| 4 | Scan errored |
| 5 | Authorization missing |

Distinct codes let a pipeline tell "the application is insecure" from "the scanner is
misconfigured" — opposite actions.

---

## Reading a result

Each plugin reports one of five outcomes:

| Outcome | Means |
|---|---|
| **PASS** | The plugin tested for its weakness and did not find it |
| **FAIL** | It found it, with evidence |
| **INCONCLUSIVE** | It could not tell. **Not the same as PASS** |
| **ERROR** | The plugin itself failed |
| **SKIPPED** | The target lacks a capability the plugin needs |

`INCONCLUSIVE` is the one that matters most. A target that ignored an injection entirely, an empty
response, a leakage detector with no reference prompt to calibrate against — all produce
INCONCLUSIVE rather than a confident PASS, because "we could not tell" and "it is fine" are different
claims.

`SKIPPED` matters too: a skipped pack produces no findings, and no findings reads as clean unless you
read coverage alongside the grade.

---

## The dashboard

```bash
streamlit run src/ragstrike/dashboard/app.py
```

It is a pure HTTP client of `/api/v1`. **That API is not implemented yet** (see
[`limitations.md`](limitations.md)), so without a backend every page shows an honest
`BACKEND OFFLINE` state rather than fabricating data. To explore the interface:

```bash
RAGSTRIKE_DASHBOARD__TRANSPORT=demo streamlit run src/ragstrike/dashboard/app.py
```

Demo mode carries a `DEMO MODE` banner on every page. There is no configuration that removes the
banner while the data stays sample data.

---

## The lab

RAGStrike ships beside two applications that are identical except for their security controls:

| | API | UI |
|---|---|---|
| VulnerableRAG | 9000 | 8601 |
| SecureRAG | 9001 | 8602 |

Scanning both is how you check the scanner rather than the target. See [`demo.md`](demo.md) for the
repeatable walkthrough.
