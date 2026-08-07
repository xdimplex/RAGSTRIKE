# Licence review

> Measured against the installed environment on 2026-07-30, not against the requirements files.
> Reproduce with `pip-licenses --format=markdown --with-urls`.

RAGStrike is **Apache-2.0** ([`../LICENSE`](../LICENSE)).

---

## Summary

**Apache-2.0 is a correct and safe licence for this project.** No dependency imposes a term that
conflicts with it, and nothing is vendored.

| Licence family | Distributions | Compatible with Apache-2.0 distribution |
|---|---|---|
| MIT | 51 | Yes |
| BSD (2/3-clause) | 29 | Yes |
| Apache-2.0 | 27 | Yes |
| PSF | 3 | Yes |
| ISC | 1 | Yes |
| **MPL-2.0** | **4** | **Yes — file-level copyleft, and nothing is modified** |
| **GPLv2+ / LGPLv2+ / MPL-1.1 (tri-licensed)** | **1** | **Yes, under the LGPL option — and it is optional** |

**183 distributions** in the development environment, which includes every optional extra and every
dev tool. A base `pip install ragstrike` pulls far fewer.

**116 of the 183 carry a machine-readable licence classifier**; the table above counts those. The
remaining 67 declare a licence in free-text metadata or in a bundled `LICENSE` file, which
`importlib.metadata` cannot classify reliably. They are not unlicensed — they are unclassified, and
the distinction matters: this table is a **screen, not a clearance**. Run `pip-licenses` for the
authoritative list before any distribution that depends on the answer.

---

## The two entries that need a sentence each

### MPL-2.0 — `certifi`, `pathspec`, `orjson`, and one transitive

MPL-2.0 is **file-level** copyleft: obligations attach to modified MPL files, not to a work that
merely depends on them. Nothing here is modified or vendored — every one arrives from PyPI as an
unmodified wheel.

`certifi` is the CA bundle, and it reaches the tree through `httpx`. Unavoidable and unproblematic.

### `pyphen` — GPLv2+ / LGPLv2+ / MPL-1.1

The only entry with a GPL option, and worth stating plainly:

- **It is tri-licensed.** A user may take it under **LGPLv2+**, which permits use as a separate
  dependency of an Apache-2.0 work. That is the option that applies here.
- **It is not a dependency of RAGStrike.** It arrives transitively through `weasyprint`, which is in
  the **optional `pdf` extra** (`pyproject.toml`), not the base install.
- **The PDF renderer is not implemented** ([D-05](technical-debt.md)), so in practice nothing in the
  shipped product reaches it at all.
- Nothing is bundled or statically linked. It is an ordinary PyPI dependency, resolved at install
  time.

**Conclusion: no obligation on this repository.** Recorded here because a licence review that only
lists the comfortable entries is not a review, and because someone will eventually run a scanner over
the environment and ask about this exact line.

---

## Correction to a previously published claim

[`third-party-attribution.md`](third-party-attribution.md) states *"No copyleft dependency is
present."* **That is not accurate** for the full development environment: four MPL-2.0 distributions
and one tri-licensed distribution are present, as above.

The *conclusion* it supports — that Apache-2.0 redistribution is unaffected — is still correct, for
the reasons given above. The claim was too strong; this page is the corrected version, and the
statement is left in place with a pointer rather than quietly rewritten, so the correction is visible
rather than invisible.

---

## Standards and taxonomies

| Source | Used for | Terms |
|---|---|---|
| OWASP Top 10 for LLM Applications | Category mapping (LLM01–LLM10) | CC BY-SA 4.0 |
| MITRE ATLAS | Technique mapping | Publicly available |
| CWE | Weakness identifiers | Publicly available |

**Identifiers are referenced, never reproduced.** A manifest carries `owasp: LLM01`; it does not carry
OWASP's text. This matters for CC BY-SA specifically — copying the prose would carry a share-alike
obligation, and referencing an identifier does not.

## Models

**Qwen3** and **nomic-embed-text**, via Ollama. Neither is distributed with this project. The operator
pulls them under their own licences, which this repository does not restate because restating a
licence is how a licence gets misstated.

## Corpus

Every document in the lab corpus is **synthetic and written for this project**. No third-party
document, no scraped text, no real person or organisation.

## Not derived from

An independent implementation. No code is vendored from another security tool, and no attack corpus is
copied from another project.

---

## Is a NOTICE file required?

**Not strictly.** Apache-2.0 §4(d) requires propagating a `NOTICE` only when you redistribute a
derivative of a work that carried one. RAGStrike vendors nothing, so it inherits no NOTICE
obligation.

One is provided anyway ([`../NOTICE`](../NOTICE)) because it is the conventional place a downstream
consumer looks, and an empty answer there reads as an unanswered question.

## Re-run this review when

- A dependency is added — check the licence **before** the pin, not after
- The `pdf` extra is enabled — that is what brings the tri-licensed entry into a real code path
- Any code is vendored rather than depended on. That is the change that would create a NOTICE
  obligation, and it should be a deliberate decision
