# Security Policy

RAGStrike is offensive security tooling. This document covers three things: how to use it
responsibly, what its own trust boundaries are, and how to report a vulnerability in it.

---

## 1. Responsible use

**Use RAGStrike only against systems you own or are explicitly authorized to test.**

Scanning a system without authorization is likely illegal in your jurisdiction regardless of intent
or outcome. "I was only testing" is not a defence.

### The controls built into the tool

These are not suggestions in a document — they are the shipped defaults.

| Control | Behaviour |
|---|---|
| **Authorization gate** | No scan starts without a persisted authorization record: who authorized it, against what reference, when. It is a required field on the target, not a checkbox, and it is embedded in every report. |
| **Loopback default** | The shipped configuration reaches only `localhost`, `127.0.0.1`, and `::1`. A remote target requires setting `allow_remote_targets: true` **and** adding an allowlist entry. Two deliberate steps. |
| **Mandatory rate limiting** | The token bucket has no disable path. Every request to an LLM endpoint has real cost; a tool that can be trivially turned into a denial-of-service instrument is irresponsible. |
| **Non-destructive payloads** | First-party payloads declare `destructive: false`, and the conformance suite rejects payloads matching a destructive-pattern deny-list. RAGStrike demonstrates weaknesses; it does not exploit them into damage. |
| **Cleanup obligation** | Every artifact written into a target — poisoned documents, canary tokens — is tracked and removed. Where an adapter cannot delete, the residual is listed prominently in the report so a human can. |

### Features this project will not implement

- WAF or guardrail **evasion**
- Rate-limit **circumvention**
- Detection **avoidance**
- Mass or untargeted scanning

These are recorded here so the boundary is not relitigated in every feature discussion. They are out
of scope permanently, not "not yet."

### If you find a vulnerability in someone else's system

Follow coordinated disclosure: contact the operator privately, give them reasonable time to fix it,
and do not publish exploit details before a fix ships. RAGStrike reports are evidence for the
operator, not material for a public write-up.

---

## 2. The plugin trust model

**Stated plainly: installing a third-party attack pack is equivalent to installing a Python package,
and grants equivalent trust.** A pack can execute arbitrary code in your process.

RAGStrike raises the bar in three ways, and it is honest about what it does not do:

**What it does.** Pack manifests are parsed *before* any pack code is imported (ADR-003), so
compatibility and declared permissions are checked before a third party gets execution. Packs declare
`network_egress` and `filesystem_write` permissions, and the installation UX warns loudly when a pack
requests elevated ones. The SDK conformance suite tests for undeclared egress and writes.

**What it does not do.** There is no OS-level sandbox in v1. Subprocess isolation with a capability
broker is a roadmap item (Annex D, R-07). **Claiming a sandbox that does not exist would be worse
than declaring none**, because it would produce false confidence in exactly the place where
confidence should be earned.

**What this means for you.** Install packs from sources you trust, the same way you would any
dependency. Review the manifest's `permissions` block before installing.

---

## 3. Data handling

RAGStrike records complete evidence for every probe, which means **`data/scans.db` may contain real
credentials and real personal data that a target disclosed during a scan.**

| Location | Contents | Protection |
|---|---|---|
| `data/scans.db` | Raw, unredacted evidence | Gitignored. Local only. Never sync to shared storage. |
| `reports/` | Rendered reports | Redacted by default (`partial`). Gitignored. |
| `logs/debug/` | Full request and response bodies | Off by default. Never enable in a shipped configuration. |
| `logs/*` | Structured logs | Redaction applied by a pipeline processor, not per call site (ADR-013) — so no future log statement can leak by omission. |

Setting the redaction policy to `none` is an explicit operator choice and is recorded on the report.

---

## 4. Reporting a vulnerability in RAGStrike

**Do not open a public issue.**

Email the maintainers at `security@example.com` (replace with the real address before the first
public release) with:

- A description of the vulnerability and its impact
- Steps to reproduce, ideally with a minimal case
- Affected version or commit
- Any suggested fix

**What to expect:** acknowledgement within 3 working days, an initial assessment within 10, and
coordinated disclosure once a fix is available. We will credit you unless you prefer otherwise.

### Especially interested in

- Anything letting a **malicious attack pack** escape its declared permissions
- **Evidence leakage** — unredacted secrets reaching a report, a log, or any exported artifact
- **Payload template escapes** — the payload renderer must have no evaluation capability at all
  (ADR-016); if you can evaluate an expression through it, that is a serious finding
- **Authorization gate bypass** — any path that starts a scan without a persisted authorization record
- **Rate limiter bypass** — any path that reaches a target faster than the configured ceiling

### Out of scope

- Vulnerabilities in **VulnerableRAG**. That application is intentionally insecure; its weaknesses
  are the specification, documented in its `docs/vulnerabilities.md`. A finding there is only a bug
  if it is a weakness that is *not* in the catalogue.
- Findings requiring an already-compromised host.
- Denial of service against your own local installation.

---

## 5. Supported versions

| Version | Supported |
|---|---|
| 0.x (pre-release) | Current `main` only |

Once 1.0 ships, the latest minor of the current major receives security fixes.
