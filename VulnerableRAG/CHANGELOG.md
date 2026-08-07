# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning:
[SemVer](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added — Phase 2: VulnerableRAG v1

- **RAG pipeline**, end to end: PDF loader (pypdf) → text splitter
  (LangChain `RecursiveCharacterTextSplitter`) → Ollama embeddings → ChromaDB → retriever → weak
  prompt template → Ollama → answer.
- **FastAPI service** on `127.0.0.1:9000`: `POST /upload`, `POST /chat`, `GET /documents`,
  `DELETE /documents/{id}`, `GET /health`, plus `GET /documents/{id}/chunks` and `POST /chat/reset`
  for inspection. Every response is JSON, including every error.
- **Streamlit UI** on `127.0.0.1:8601` with five pages: Home, Upload Documents, Chat, System Status,
  Settings. It reaches the engine only through the API — never Ollama, Chroma, or the database.
- **Security policy seam** (`rag/policy/`): five hook points, a composable chain, and
  `PolicyRejectionError`. VulnerableRAG composes `SecurityPolicyChain([])` in code.
- **Persistence**: aiosqlite for document metadata, upload history, and settings, behind
  repositories and a forward-only migration runner. No vectors in SQLite.
- **Error taxonomy** covering invalid PDF, empty PDF, unsupported type, oversize upload, missing
  document, empty corpus, Ollama unreachable, model not pulled, model timeout, empty model response,
  and vector store unavailable — each with an actionable `hint`.
- **Structured JSON logging** to `logs/`, covering uploads, questions, retrieved chunks, errors,
  API requests, and response times.
- **Corpus tooling**: `scripts/seed_corpus.py` generates three benign and three poisoned reference
  PDFs (including white-on-white and metadata payloads) and ingests the benign set;
  `scripts/reset_lab.py` returns the lab to a clean state.
- **63 tests**, none requiring Ollama — a scripted model client and a hash-based embedder stand in.
- `docs/vulnerabilities.md`: the V1–V9 catalogue with reproduction commands.

### Fixed during Phase 2

- `extra=` keys colliding with reserved `LogRecord` attributes (`name`, `filename`) raised at every
  `log.info` call. Found only after raising pytest's `log_level` to `INFO` — at the default
  `WARNING`, those records were never constructed and the logging path was silently untested.
- Qwen3 spending its entire `num_predict` budget on internal reasoning and returning an empty
  answer. Thinking is now off by default, and an empty response raises `EmptyModelResponseError`
  rather than surfacing as a blank reply.
- `Engine` moved from `profiles/vulnerable/profile.py` to `rag/engine.py`. FastAPI resolves
  annotations at import time, and a type that exists only under `TYPE_CHECKING` was silently
  reinterpreted as a query parameter — turning every request into a 422.

### Added — Phase 1: Engineering Foundation

- Full directory structure with a README in every folder stating purpose, responsibilities, future
  contents, and explicit boundaries
- Two-profile architecture established: `rag/policy/` as the single security seam, `profiles/` as the
  two thin applications (ADR-009)
- Packaging and tool configuration, marked `Private :: Do Not Upload` so this can never reach PyPI
- Runtime and development dependency manifests with per-dependency justification
- Configuration scaffold with retrieval parameters shared across profiles by construction
- `docs/LAB_SAFETY.md` — containment rules
- GitHub workflow and issue template placeholders
- Docker placeholders, loopback-bound

### Not yet implemented

No RAG pipeline, no API endpoints, no UI pages, no policy controls, no database access. Phase 1 is
structure only.

---

## Planned

| Phase | Deliverable |
|---|---|
| 2 | VulnerableRAG v1 — ingestion, retrieval, generation, UI, all nine weaknesses reproducible |
| 11 | SecureRAG — the full control chain, plus functional parity tests |
