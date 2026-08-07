# Third-party attribution

RAGStrike is licensed under **Apache-2.0** (see [`../LICENSE`](../LICENSE)).

> **Correction (v1.0.0).** The statement below that *"No copyleft dependency is present"* is too
> strong. The v1.0.0 licence review measured the installed environment and found four MPL-2.0
> distributions and one tri-licensed (GPLv2+/LGPLv2+/MPL-1.1) transitive dependency in the optional
> `pdf` extra. **The conclusion is unchanged** — Apache-2.0 redistribution is unaffected, and nothing
> is vendored — but the claim was wrong as written. See
> [`license-review.md`](license-review.md), which supersedes this page on dependency licensing. The
> original text is left in place so the correction is visible.

---

## Licence compatibility

Every direct dependency is under a permissive licence compatible with Apache-2.0 redistribution:

| Licence | Packages |
|---|---|
| MIT | `httpx`, `typer`, `aiosqlite`, `pypdf`, `pytest`, `mypy`, `pydantic-settings` |
| BSD-3-Clause | `pydantic`, `jinja2`, `pandas`, `hypothesis`, `click` |
| Apache-2.0 | `chromadb`, `langchain-text-splitters`, `streamlit`, `packaging`, `respx` |
| MIT-CMU | `pyyaml` |
| BSD-3-Clause | `altair`, `rich` |

**No copyleft dependency is present**, and `pip-audit` runs in CI. Verify current state with:

```bash
pip-licenses --format=markdown --with-urls
```

---

## Standards and taxonomies referenced

| Source | Used for | Licence |
|---|---|---|
| **OWASP Top 10 for LLM Applications** | Category mapping (LLM01–LLM10) | CC BY-SA 4.0 |
| **MITRE ATLAS** | Technique mapping | Publicly available |
| **CWE** | Weakness identifiers | Publicly available |
| **CVSS** concepts | *Rejected* as a scoring basis — see ADR-011 | — |

Attack-pack manifests carry `owasp`, `atlas`, and `cwe` fields; those identifiers are references to
the above, not reproductions of their text.

---

## Models

The lab uses **Qwen3** and **nomic-embed-text** through Ollama. Neither is distributed with this
project — both are pulled by the operator, under their own licences.

---

## Not derived from

RAGStrike is an independent implementation. It is **not** derived from, and does not vendor code
from, Garak, PyRIT, promptfoo, or any other LLM security tool. Where the design converges on a
similar idea — canary tokens, differential testing — that is convergence on a well-known technique,
and the reasoning is recorded in [`annex-c-adrs.md`](annex-c-adrs.md).

---

## The lab corpus

Every document under `VulnerableRAG/corpus/` and `SecureRAG/corpus/` is **synthetic**, written for
this project. The planted credentials are high-entropy, canary-tagged, and clearly labelled
`SYNTHETIC-NOT-A-REAL-CREDENTIAL`, so a real leak can never be confused with a lab artifact. No real
organization, person, or system is represented; `acme.invalid` uses the reserved `.invalid` TLD by
design.
