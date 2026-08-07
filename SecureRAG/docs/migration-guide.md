# Migration guide

> Porting the controls in this repository into a real RAG application, and what changes when you do.

---

## The order that matters

If you adopt only part of this, adopt it in this order. It is roughly descending by
value-per-line-of-code.

### 1. Remove secrets from the system prompt

The cheapest fix in the entire application, and the only one that is a *fix* rather than a
mitigation. A credential in the prompt travels to the model on every request, and any leak — through
any of a hundred phrasings — discloses it.

Nothing else on this list is worth doing before this one.

### 2. Fence and label the retrieved context

[`rag/generation/prompt_builder.py`](../rag/generation/prompt_builder.py). Four properties: an
instruction hierarchy stated in the prompt and restated above the fence, delimiters, per-chunk
provenance, and escaping so a document cannot close the fence early.

This is the structural defence. Everything below it is defence in depth behind this.

**Watch for:** the escaping. Without it the delimiters are decoration, and the failure is invisible
until someone crafts the input.

### 3. Detect system-prompt echo on output

[`OutputFilter`](../rag/policy/controls/output_filter.py). Compare the answer against your own prompt
rather than trying to recognise the request. It catches every phrasing at once because it tests the
outcome.

**Watch for:** compare on normalized, whitespace-collapsed text using overlapping shingles.
Exact-match containment catches nothing once the model reformats.

### 4. Put a relevance floor on retrieval

[`RetrievalFilter`](../rag/policy/controls/retrieval_filter.py). A vector search always returns its
`top_k` however bad the matches are — so an off-topic poisoned document rides along with every
unrelated question.

**Watch for:** the right floor is corpus-specific. Measure it before choosing.

### 5. Bound conversation history

[`SessionBounder`](../rag/policy/controls/session_bounder.py). Gives a poisoned turn a lifetime
instead of unlimited replays.

### 6. Validate input at the boundary

[`InputValidator`](../rag/policy/controls/input_validator.py), called from the route **before** the
pipeline. Length, encoding, control characters.

**Watch for:** validate before you embed. This repository shipped it in the policy chain first, where
the hook fires *after* retrieval — so an over-long question still reached the embedding model. A test
caught it. See [`security-features.md`](security-features.md#what-securerag-does-not-do).

**Watch for:** do not validate intent. Blocking questions that mention "ignore previous instructions"
makes the assistant useless for discussing its own security.

### 7. Mask secrets on output

[`SecretMasker`](../rag/policy/controls/secret_masker.py). Last in the chain, always.

**Watch for:** keep a fingerprint rather than a featureless mask, or incidents become unanalysable.

### 8. Sanitize documents at ingestion

[`ContextSanitizer`](../rag/policy/controls/context_sanitizer.py). Unicode normalization and
invisible-character stripping are unambiguous wins. Instruction neutralization is the one most likely
to annoy users — it rewrites document text.

**Watch for:** neutralize, do not delete, or you break every document that discusses security.

### 9. Ground citations

[`CitationGrounder`](../rag/policy/controls/citation_grounder.py). Annotate rather than strip.

---

## What does not port directly

**The `SecurityPolicy` chain itself** assumes a synchronous pipeline with five fixed hook points. In
an async or streaming pipeline the response hook is the hard one: masking a streamed answer means
buffering enough to match a pattern across chunk boundaries, which partly defeats streaming.

**The magic-byte allowlist** covers PDF only. Add a signature for every format you accept — and note
that this repository *refuses* an allowed extension with no registered signature, precisely so
extending the allowlist cannot silently disable content checking.

**Nothing about authentication**, because there is none here.

---

## Things to add that this lab does not have

In roughly the order a real deployment needs them:

1. **Authentication**, then **per-principal document authorization** at `on_context_assembly`. That
   is the control that turns the retrieval filter from a relevance filter into a security boundary.
2. **Rate limiting**, keyed on the identity authentication gives you.
3. **Parser sandboxing.** Validation makes a file a *plausible* PDF, not a safe one.
4. **Audit logging** of who asked what, which this lab deliberately does not keep.
5. **Secrets management** for provider credentials.

The first three are stubbed in [`future_controls.py`](../rag/policy/controls/future_controls.py) with
what blocks each one.

---

## Testing your port

The test structure transfers even where the code does not:

- One suite per control, testing the attack **and** the legitimate input it must not break.
- A regression suite indexed by weakness, not by module, so a red build names the lesson that
  regressed.
- A chain-composition test asserting the chain is complete and correctly ordered.
- A parity test asserting hardening did not change the API.

That last one is the one people skip and then regret.
