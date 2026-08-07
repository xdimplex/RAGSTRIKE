# Security Policy

## This repository is intentionally vulnerable

**Do not report the documented weaknesses as vulnerabilities.** They are the specification. The full
catalogue is in [`docs/vulnerabilities.md`](docs/vulnerabilities.md), and every entry has a matching
implemented defence in the `secure` profile.

## What *is* worth reporting

A weakness that is **not** in the catalogue. Concretely:

- **Path traversal in the upload handler.** Writing outside `uploads/` is a real bug — the lab is
  meant to be vulnerable at the RAG layer, not at the filesystem layer.
- **Anything reachable off-host.** A default that binds beyond `127.0.0.1`, a Compose file that
  publishes a port externally, or a code path that ignores the loopback binding. Containment failures
  are the most serious class of bug this repository can have.
- **A real credential** committed anywhere. Every secret in this lab must be synthetic,
  high-entropy, and canary-tagged.
- **A weakness in the `secure` profile** that the corresponding control claims to prevent. If
  SecureRAG leaks its system prompt, the prompt-protection control is broken, and that matters:
  RAGStrike's false-positive gate depends on SecureRAG actually being hardened.
- **Anything that makes the two profiles behave differently on benign input.** That breaks functional
  parity and silently invalidates RAGStrike's differential validation.

Report privately to `security@example.com`. Do not open a public issue.

## Safe use

See [`docs/LAB_SAFETY.md`](docs/LAB_SAFETY.md). The short version:

- Loopback only, always
- Never on shared infrastructure
- Never with real data
- Reset between sessions
- The `RAGSTRIKE_LAB_ACK=1` gate exists for a reason; do not bake it into a profile or an image

## Licence and intent

Apache-2.0, provided for education and authorized security testing. Using it to attack systems you do
not own or are not authorized to test is illegal in most jurisdictions and is not a use this project
supports.
