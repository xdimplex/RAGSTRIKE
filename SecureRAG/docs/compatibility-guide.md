# Compatibility guide

> Every way SecureRAG differs from VulnerableRAG, and the machinery that keeps the list short.

---

## Why this document exists

[ADR-009](../../RAGStrike/docs/annex-c-adrs.md) rejected two independent repositories for one reason:
**they drift.** A UI change lands in one, a chunker is tuned in the other, and once they diverge the
differential comparison stops measuring security and starts measuring incidental difference — while
continuing to look correct. That failure mode is silent.

SecureRAG was built as a separate repository anyway, on an explicit decision. This document and
`tests/parity/test_compatibility.py` are the mitigation. The test suite is the executable half: it
fails loudly the moment one side grows a field the other lacks.

**When VulnerableRAG changes its API, the recorded contract in that test file must be updated
deliberately — and that edit is the moment someone notices the two have diverged.** Making drift
require a decision instead of happening by omission is the whole mechanism.

---

## The API is identical

| Method | Path | Identical |
|---|---|---|
| `GET` | `/health` | ✅ schema |
| `POST` | `/upload` | ✅ |
| `GET` | `/documents` | ✅ |
| `GET` | `/documents/{document_id}/chunks` | ✅ |
| `DELETE` | `/documents/{document_id}` | ✅ |
| `POST` | `/chat` | ✅ |
| `POST` | `/chat/reset` | ✅ |

No endpoint added, none removed. An extra endpoint would be a compatibility break in the other
direction: a scanner enumerating the surface would find something on one application and not the
other and report a difference that has nothing to do with security posture.

Every response field name is identical, including `system_prompt`, which SecureRAG always returns as
`null`. Removing it would break a client written against VulnerableRAG.

---

## Behavioural differences

Three, all intended, all observable.

### 1. `GET /health?include_prompt=true` returns `null`

The single API-behaviour difference, and the one the endpoint exists to demonstrate.

### 2. `security_policies` is populated; `warning` changes

`[]` becomes seven entries. The warning names the three controls that are **declared and not
implemented**, because listing them as active would be the application lying about its posture.

### 3. Some requests are refused that VulnerableRAG accepts

That is what a validation layer does. Every refusal uses the same error envelope.

| Request | VulnerableRAG | SecureRAG |
|---|---|---|
| Empty / whitespace question | 400 | 400 |
| Question over 2000 chars | 200 | **400** `policy_rejected` |
| Question with control characters | 200 | **400** `policy_rejected` |
| `.txt` upload | 415 | 415 |
| Renamed executable as `.pdf` | 200 (parser fails later) | **400** `invalid_document` |
| Upload over the size limit | 413 | 413 |
| Duplicate upload | ingested twice | **existing record returned** |

A client that handles VulnerableRAG's errors handles SecureRAG's — same envelope, same field names,
same codes where the code already existed.

---

## Files that differ, and why

Everything else in this repository is inherited verbatim. **If you change a file not on this list,
you have introduced drift.**

| File | Change |
|---|---|
| `profiles/secure/*` | Replaces `profiles/vulnerable/*`. Full chain, hardened prompt, ports 9001/8602 |
| `rag/generation/prompt_builder.py` | The hardened template. **The largest and most important diff** |
| `rag/policy/controls/*` | New. Seven controls plus the declared-not-implemented three |
| `rag/security_config.py` | New. The `security.yaml` schema |
| `rag/config.py` | Four lines: default profile, `SRAG_` prefix, `security` field, warning text |
| `backend/validation.py` | New. Upload validation at the boundary |
| `backend/middleware/security.py` | New. Security headers and the rate-limit counter |
| `backend/app_factory.py` | Three lines: profile import, two middlewares, title/description |
| `backend/routers/upload.py` | Calls the validator; duplicates are idempotent |
| `backend/routers/chat.py` | Boundary validation before the pipeline |
| `backend/routers/health.py` | Withholds the prompt; different warning |
| `configs/security.yaml` | New |
| `tests/*` | Weakness assertions inverted; five suites added |

**Deliberately identical:** `rag/engine.py`, `rag/generation/pipeline.py`, `rag/ingestion/*`,
`rag/retrieval/*`, `rag/session/*`, `rag/models.py`, `rag/errors.py`, `rag/policy/{chain,hooks,protocol}.py`,
all of `database/`, all of `frontend/`, `vectorstore/`, and `backend/schemas/`.

Note that `rag/generation/pipeline.py` is **unchanged** — the query pipeline is shared. All hardening
enters through the chain it already called and through the template it already used.

---

## Checking compatibility

```bash
pytest tests/parity          # always runs; asserts against the recorded contract
```

Against a live pair:

```bash
diff <(curl -s localhost:9000/openapi.json | jq -S .paths | jq 'keys')  \
     <(curl -s localhost:9001/openapi.json | jq -S .paths | jq 'keys')
```

---

## Keeping them in sync

1. Change VulnerableRAG.
2. Run `pytest tests/parity` here. If it fails, the contract moved.
3. Port the change to the matching file, or update the recorded contract if the API genuinely
   changed.
4. Re-run the full suite in both repositories.

If step 3 ever requires changing a file *not* on the divergence list above, stop and ask whether the
change belongs in shared core — because that is drift beginning.
