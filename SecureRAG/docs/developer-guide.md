# Developer guide

---

## Layout

```
SecureRAG/
├── backend/        FastAPI: routers, schemas, middleware, upload validation
├── rag/            The pipeline: config, ingestion, retrieval, generation, policy
│   └── policy/
│       └── controls/   ← the seven controls. The interesting directory
├── database/       SQLite: connection, migrations, repositories
├── vectorstore/    ChromaDB client and collections
├── frontend/       Streamlit UI, shared with VulnerableRAG
├── profiles/
│   └── secure/     The application: chain composition, prompt, ports, entry points
├── configs/        config.yaml, security.yaml, logging.yaml
├── corpus/         Synthetic documents
├── scripts/        Corpus seeding, PDF generation, lab reset
├── tests/          unit · integration · parity · regression
└── docs/
```

Full per-directory responsibilities: [`folder-responsibilities.md`](folder-responsibilities.md).

---

## Run the tests

```bash
pytest                    # 248 tests
pytest tests/unit         # fast, no Ollama
pytest tests/parity       # the drift gate
pytest tests/regression   # the nine weaknesses, asserted absent
```

`ScriptedLLM` stands in for the model and a hash-based embedder replaces `nomic-embed-text`, so the
suite runs with Ollama stopped. Every test gets its own temp root, database, and Chroma directory —
Chroma holds an exclusive lock, and shared state produces failures that appear only in certain orders.

---

## Adding a control

1. Subclass `SecurityPolicy` in `rag/policy/controls/`. Override only the hooks you need; every hook
   has a pass-through default.
2. Add a settings section to `rag/security_config.py` with bounded fields.
3. Add it to `build_controls()` in `rag/policy/controls/__init__.py`, **in the right position** — see
   the ordering table in that module.
4. Add it to `EXPECTED_CHAIN` in `tests/unit/test_policy_chain.py`.
5. Write tests for the attack **and** for the legitimate input it must not break.
6. Document it in `docs/security-features.md`.

**If it inspects the answer, it goes before `SecretMasker`.** A test enforces the masker is last.

### If you cannot finish it

Put it in `future_controls.py` as a `DeclaredControl` with a `blocked_on` string. It will be excluded
from the chain by construction and reported honestly by `GET /health`. A half-built control in the
chain is worse than none.

---

## Conventions

- **Policies never know which profile assembled them.** If one needs to ask, the seam is broken.
- **Never log document text, question text, or answer text.** Log lengths, ids, reason codes, and
  fingerprints. A control that logs what it blocked turns the log into the channel it just closed.
- **Errors carry a hint.** A refusal with no next step is a dead end.
- **Raise from `rag/errors.py`.** Only `backend/app_factory.py` maps errors to HTTP statuses, and only
  it raises `HTTPException`.
- **Do not touch shared core** without checking [`compatibility-guide.md`](compatibility-guide.md).
  Files not on its divergence list are inherited verbatim, and changing one is how drift starts.

---

## Gate

```bash
ruff check . && black --check . && pytest
```

---

## Debugging

**See the exact prompt:**

```bash
curl -s localhost:9001/chat \
  -H 'content-type: application/json' \
  -d '{"message":"What is the policy?","include_prompt":true}' | jq -r .prompt
```

**See what a control did to a document:**

```bash
curl -s localhost:9001/documents/<id>/chunks | jq -r '.chunks[].text' | grep neutralized
```

**See the active chain:**

```bash
curl -s localhost:9001/health | jq '.security_policies, .warning'
```

**Compare against the vulnerable half** — with both running, the same request against 9000 and 9001
is the most informative thing you can do.
