# Changelog

All notable changes to SecureRAG are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added — SecureRAG

The hardened half of the lab: the same application as VulnerableRAG, with the security control chain
composed instead of empty.

- **Seven security controls** in `rag/policy/controls/`, composed in code and ordered deliberately:
  context sanitizer, input validator, retrieval filter, session bounder, citation grounder, output
  filter, and secret masker. The masker is last, always, so nothing downstream can reintroduce a
  value it removed — enforced by a test.
- **A hardened prompt template.** Fenced regions, per-chunk provenance, the instruction hierarchy
  stated twice, and fence escaping so a document cannot close the fence early. The fence nonce is
  regenerated per process, so a document written in advance cannot contain the marker. This is the
  structural defence; the pattern matching is defence in depth behind it.
- **A system prompt with no credentials.** The cheapest fix in the application, and the one masking
  backs up rather than replaces.
- **`configs/security.yaml`**, validated by `rag/security_config.py` with bounded fields and
  fail-fast startup. **No value in it can remove a control from the chain** — a test turns every
  boolean off at once and asserts the chain is still complete.
- **Upload validation at the boundary** (`backend/validation.py`): size, filename, extension, MIME,
  and magic bytes — in front of the PDF parser rather than after it. An allowed extension with no
  registered signature is refused rather than waved through.
- **Security headers and a rate-limit counter.** HSTS is deliberately absent: a loopback lab has no
  TLS, and pinning a browser to `https://localhost` would break the next application to bind there.
  The rate-limit middleware counts and sets `X-RateLimit-Policy: none; not implemented`.
- **Three controls declared and NOT implemented** — rate limiting, authentication, authorization —
  each recording what blocks it, excluded from the chain by construction, and named in `GET /health`
  under `warning` rather than `security_policies`. A control listed as active but doing nothing tells
  an operator they are covered when they are not.
- **248 tests** across eight suites: unit, API, validation, upload, configuration, pipeline,
  regression, and compatibility. The regression suite is indexed by weakness rather than by module,
  so a red build names the lesson that regressed.
- Documentation: architecture comparison, security features, configuration, deployment,
  compatibility, migration, developer guide, and folder responsibilities.

### Fixed — defects found by the tests while building this

- **The lab-canary mask was partial.** The pattern's body class was uppercase-only, so
  `VRAG-CANARY-SECRET-` was masked and the random `a7f3c91e4b8d2065` that followed was left in the
  response. A partial mask is not a mask.
- **Citation extraction ran backwards into the sentence.** The bare-filename pattern allowed spaces,
  so `"See Handbook.PDF"` was extracted whole, never matched a retrieved source, and every ordinary
  citation was reported as ungrounded.
- **Input validation could not protect the path it was written for.** `on_context_assembly` fires
  *after* retrieval, and retrieval embeds the question — so a 5000-character question reached the
  embedding model and returned a 500 before the length limit ever ran. A boundary check now runs in
  `backend/routers/chat.py`, in front of the embedder. The in-chain validator stays as defence in
  depth; the residual gap for direct in-process callers is recorded in `docs/security-features.md`
  rather than hidden by weakening the test.
- **A compatibility test was passing vacuously.** Route enumeration walked `app.routes` and silently
  returned nothing, so "no endpoint was added" could never fail. It reads `/openapi.json` now — which
  is also the surface a client generator and a scanner actually consume.

### Changed from VulnerableRAG

Every divergence is listed in `docs/compatibility-guide.md`. The API is unchanged: same endpoints,
same response schemas, same error envelope. One behavioural difference —
`GET /health?include_prompt=true` returns `null` — with the field retained so a client written
against VulnerableRAG keeps working.
