# Security features

> What SecureRAG does, why each control is shaped the way it is, and — as importantly — what it does
> not do.

---

## The shape of the defence

Two layers, and they are not equally important.

**The structural layer** is the prompt template. It removes the *ambiguity* injection depends on:
retrieved text arrives inside a fence, labelled with its provenance, under a standing rule that says
text in that fence is data. There is no phrasing that makes a document stop being inside the fence.

**The pattern layer** is the control chain. It recognises instruction-shaped and credential-shaped
text and acts on it. Patterns are defeated by rephrasing, so this layer removes the easy half and
nothing more.

A lab that implied regex was sufficient would teach the wrong lesson. The structural layer carries
the weight; the patterns are defence in depth behind it.

---

## The seven controls

Composed in code by `rag/policy/controls/__init__.py`. Order matters and is enforced by a test.

| # | Control | Hook | Counters | What it does |
|---|---|---|---|---|
| 1 | **ContextSanitizer** | `on_ingest`, `on_chunk` | V1, V2 | NFKC-normalizes, strips invisible characters, neutralizes instruction framing in documents |
| 2 | **InputValidator** | `on_context_assembly` | V6 | Length, emptiness, encoding, control characters. Refuses |
| 3 | **RetrievalFilter** | `on_context_assembly` | V7 | Relevance floor, chunk cap, size cap, instruction density |
| 4 | **SessionBounder** | `on_prompt_build` | V8 | Bounds history and total prompt size |
| 5 | **CitationGrounder** | `on_response` | V9 | Flags citations naming documents that were not retrieved |
| 6 | **OutputFilter** | `on_response` | V3, V5 | Length cap, normalization, system-prompt echo detection |
| 7 | **SecretMasker** | `on_response` | V3 | Masks credential- and PII-shaped strings. **Always last** |

Two orderings are load-bearing:

- **InputValidator before RetrievalFilter.** A question that will be refused should be refused before
  effort is spent filtering chunks retrieved for it.
- **SecretMasker last.** Nothing may touch the answer after masking, or it could reintroduce a value
  the masker removed. `test_the_secret_masker_runs_last` is what stops that landing silently.

---

## Design decisions worth explaining

### Neutralize documents, refuse questions

The sanitizer *wraps* instruction-shaped spans rather than deleting them:
`[neutralized: Ignore all previous] instructions.` The validator *refuses* a bad question outright.

The asymmetry is deliberate. A document is a corpus artifact an operator uploaded on purpose;
mangling it silently would break legitimate content — including this lab's own documentation about
prompt injection. A question is a live request with a caller waiting, and a caller can be told what
was wrong and try again. **Refusal is only humane when there is someone to tell.**

### The validator does not judge intent

An operator asking *"how do we stop someone telling you to ignore previous instructions?"* is asking
a reasonable question about their own system. A validator that blocked it would make the assistant
useless for the one topic this lab teaches. Injection *through the question* is handled structurally
by the template, not by guessing at intent.

There is a test for this in both directions, because a control that only ever gets tested against
attacks looks perfect right up until it is deployed.

### Prompt-echo detection compares, it does not pattern-match

Leakage payloads are phrased a thousand ways and no pattern list covers them. But the *answer* either
contains the prompt's distinctive text or it does not, and the application knows exactly what its
prompt says. Comparing against the known text catches every phrasing at once, because it tests the
outcome rather than the request.

Comparison is on whitespace-collapsed, punctuation-stripped text using overlapping shingles, so
reformatting — the first thing a model does when asked to "repeat your instructions as a table" —
does not defeat it. A partial leak triggers a full replacement: truncating at the leak would leave
the first half of the prompt in the response.

### The fence markers never leave the process

The prompt template wraps retrieved context and the user's question in delimiters carrying a random
per-process suffix — `<<<USER_QUESTION_7333EE9D>>>`. The suffix is the entire mechanism: a poisoned
document cannot close the fence early and promote its own text to scaffolding, because it cannot
guess the suffix.

**Which makes handing out the suffix a real vulnerability, and RAGStrike found it here.** Run
against this lab, the prompt-leakage pack got back an answer quoting the markers verbatim — and the
value was identical on every request, because the nonce is generated once at startup. No credential
leaked (SecureRAG holds none), so nothing tripped the masker, and the answer read as harmless
scaffolding chatter. It was not: an attacker who is simply *told* the suffix can write a matching
close marker into a document and get exactly the promotion the fence exists to prevent.

So the markers are now blocked on egress, ahead of every other output check. There is no answer
worth returning that contains them — they are structural, never content — and unlike the other
controls this one protects *future* requests too, since a disclosed nonce stays valid until restart.
The pattern matches the generic shape as well as the live value, so a model paraphrasing the
scaffolding does not slip past it.

This is worth stating plainly in a lab about differential testing: the hardened half had a genuine
finding, and it was found by pointing the project's own scanner at it rather than by reading the
code.

### Masking keeps a fingerprint

`VRAG-CANARY-a7f3…` becomes `[MASKED:lab_canary:8f2a1c]`, not a row of asterisks. The kind and a
short SHA-256 prefix survive, so an operator can tell *which* secret leaked and correlate two
occurrences, without the value being recoverable. A featureless mask makes an incident unanalysable;
the raw value makes the control pointless.

**Masking is a mitigation, not the fix.** The fix is that SecureRAG's system prompt contains no
secrets at all. The masker exists for secrets that arrive through the corpus, which the application
does not control.

### Citations are annotated, not stripped

A fabricated citation is evidence the reader needs. Silently removing it produces an answer that
looks clean and is still wrong — the reader loses the only signal they had.

### The relevance floor is a security control

A vector search always returns its `top_k`, however bad the matches are. Ask a question no document
answers and you still get the *k least-irrelevant* chunks — so a poisoned document that matches
nothing in particular gets pulled into the context of every unrelated question. The floor turns
"always return five" into "return what actually matched".

### Validation happens in front of the expensive component

Size, type, and magic-byte checks run *before* the PDF parser — the component most likely to have a
memory-safety bug. Length validation runs before the embedder. Both are the same principle: cheap
checks in front of expensive, attackable machinery.

---

## Upload validation

| Check | Why |
|---|---|
| Size | Cheapest check; bounds the cost of everything after it |
| Filename | Reduced to a base name. Both POSIX and Windows separators are stripped regardless of host — an upload arrives over HTTP from any client |
| Extension | Allowlist, normalized so `pdf`, `.pdf`, and `PDF` are one value |
| MIME type | Allowlist. `application/octet-stream` is accepted because many clients send it for everything |
| **Magic bytes** | The only check the client cannot forge without making the file useless |

`application/octet-stream` being allowed is exactly why the magic-byte check is not optional: it is
what makes accepting the permissive MIME type safe.

An allowed extension with no registered signature is **refused**, not waved through. Adding a format
to the allowlist without adding its signature would silently disable content checking for that
format — the failure the check exists to prevent.

---

## Declared, not implemented

Three controls are designed and not built. They live in `rag/policy/controls/future_controls.py`,
they are **excluded from the composed chain by construction**, and `GET /health` names them in
`warning` rather than in `security_policies`.

| Control | Blocked on |
|---|---|
| **RateLimiter** | Client identity. Rate limiting by source IP is useless on loopback, where every request comes from `127.0.0.1` |
| **Authenticator** | An identity store. A hardcoded shared secret would look like authentication in a screenshot and be one `grep` away |
| **Authorizer** | Authentication, and per-document ownership the schema does not have |

A control listed as active but doing nothing is worse than no control: it tells an operator they are
covered when they are not. `test_the_application_never_reports_a_posture_it_does_not_have` enforces
the distinction.

The rate-limit middleware **counts** requests and sets `X-RateLimit-Policy: none; not implemented`,
so a caller inspecting headers is not misled and the eventual limiter has real traffic data to be
tuned against.

---

## HTTP security headers

Most instruct a browser, and most callers here are not browsers. Two are load-bearing anyway:

- **`X-Content-Type-Options: nosniff`** — this API returns model output and document text inside
  JSON, which is attacker-influenced by construction. Content sniffing plus a crafted body is a real
  XSS path.
- **`Content-Security-Policy`** — FastAPI serves `/docs`, which *is* a browser page.

**HSTS is deliberately absent.** A lab on loopback has no TLS, and HSTS would pin a browser to
`https://localhost` and break the next application to bind there.

---

## Logging

Recorded: uploads, questions (length only), retrieval events, validation refusals, security actions,
lifecycle, errors.

**Never recorded:** document text, question text, answer text, or masked values. A validator that
logged what it rejected would turn the log into the exfiltration channel it just closed. Refusals log
the *reason code*; masking logs the *kind and fingerprint*.

---

## What SecureRAG does not do

Stated plainly, because a lab that overclaims teaches worse than one that admits its limits.

- **It is hardened, not audited.** Every control here was written and tested against the attacks its
  author thought of.
- **Pattern matching is incomplete.** Rephrasing defeats it. The structural defence is what carries
  the weight, and it too is a mitigation rather than a proof.
- **Citation grounding checks retrieval, not entailment.** It verifies a cited source *was retrieved*
  — not that the source supports the claim. Establishing that needs a model call, and a model call to
  check a model has its own failure mode.
- **Upload validation does not make a PDF safe.** A file that passes is a *plausible* PDF. Sandboxing
  the parser is the real answer and is out of scope.
- **A residual ordering gap.** The in-chain `InputValidator` fires at `on_context_assembly`, which is
  *after* retrieval — and retrieval embeds the question. The boundary check in `backend/routers/chat.py`
  closes this for HTTP callers, but a direct in-process caller still reaches the embedder before the
  chain refuses. This was found by a test, and it is recorded here rather than quietly fixed by
  weakening the test.
- **No authentication, authorization, or rate limiting.** See above.

---

## Reading the diff

The fastest way to understand what hardening a RAG application consists of is to diff these files
against their VulnerableRAG counterparts:

```bash
diff VulnerableRAG/rag/generation/prompt_builder.py SecureRAG/rag/generation/prompt_builder.py
diff VulnerableRAG/profiles/vulnerable/profile.py   SecureRAG/profiles/secure/profile.py
diff VulnerableRAG/profiles/vulnerable/prompts/system_prompt.txt \
     SecureRAG/profiles/secure/prompts/system_prompt.txt
```

The last one is the shortest and the most instructive.
