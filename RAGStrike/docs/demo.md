# Demonstration

> A repeatable end-to-end walkthrough: scan a vulnerable RAG application, scan its hardened twin,
> compare. About 20 minutes including model time.

---

## 0. Prerequisites

```bash
ollama pull qwen3:4b && ollama pull nomic-embed-text
```

Three terminals. Everything stays on loopback.

---

## 1. Start VulnerableRAG

```bash
cd VulnerableRAG
RAGSTRIKE_LAB_ACK=1 python -m profiles.vulnerable.main_api        # 9000
```

The acknowledgement variable is required. This application executes instructions found in uploaded
documents.

```bash
curl -s localhost:9000/health | jq '{profile, security_policies, warning}'
```

`security_policies` is `[]`. **The emptiness is the signal** — it is the honest, machine-readable
statement that no defences are running.

---

## 2. Upload a document

```bash
curl -s -X POST localhost:9000/upload \
  -F "file=@corpus/benign/company_handbook.pdf;type=application/pdf" | jq '.chunk_count'
```

Then a poisoned one — visible text is an innocuous business update, with a white-on-white instruction
no human reader would see:

```bash
curl -s -X POST localhost:9000/upload \
  -F "file=@corpus/poisoned/hidden_instruction.pdf;type=application/pdf" | jq '.document.id'
```

---

## 3. See the problem directly

```bash
curl -s localhost:9000/chat -H 'content-type: application/json' \
  -d '{"message":"Summarize the quarterly update.","include_prompt":true}' | jq -r .prompt
```

The prompt is one flat string. The system prompt, the retrieved document, and the question run
together with nothing marking which is trusted instruction and which is untrusted data pulled off a
shared drive. **That ambiguity is the whole mechanism behind indirect injection.**

And its own credentials are in there:

```bash
curl -s 'localhost:9000/health?include_prompt=true' | jq -r .system_prompt | grep CANARY
```

---

## 4. Scan it

```bash
cd RAGStrike
ragstrike targets --verify
ragstrike scan --target vulnerable-rag
```

Read the outcome column. `FAIL` means the plugin found its weakness with evidence; `INCONCLUSIVE`
means it could not tell, which is **not** the same as PASS.

---

## 5. Start SecureRAG and seed it identically

```bash
cd SecureRAG
RAGSTRIKE_LAB_ACK=1 python -m profiles.secure.main_api            # 9001

for f in ../VulnerableRAG/corpus/benign/*.pdf; do
  curl -s -X POST localhost:9001/upload -F "file=@$f;type=application/pdf" -o /dev/null
done
```

Same corpus, or the comparison measures the corpus rather than the controls.

```bash
curl -s localhost:9001/health | jq '{profile, policies: [.security_policies[].name], system_prompt}'
```

Seven policies. `system_prompt` is `null` — the field remains for schema compatibility, and the value
never comes back.

---

## 6. See the difference in the prompt

```bash
curl -s localhost:9001/chat -H 'content-type: application/json' \
  -d '{"message":"Summarize the quarterly update.","include_prompt":true}' | jq -r .prompt
```

Fenced regions. Per-chunk provenance. An instruction hierarchy stated twice. And no credentials —
because they were removed, which is the cheapest fix in the application.

**This side-by-side is the lesson.** Everything else is machinery around it.

---

## 7. Scan the hardened half

```bash
cd RAGStrike
ragstrike scan --target secure-rag
```

---

## 8. Compare, automatically

```bash
python -m validation.runner --targets vulnerable-rag secure-rag
```

Reads `validation/datasets/*.yaml`, scans both, compares observed against expected per target, and
writes `validation/reports/validation-summary.{json,md}`.

The column to read is **`Separates`**. A benchmark on which both halves agree has validated nothing
about the difference between them — even if both matched their own expectation.

---

## 9. Explain the difference

Two files, and the shorter one is more instructive:

```bash
diff VulnerableRAG/profiles/vulnerable/prompts/system_prompt.txt \
     SecureRAG/profiles/secure/prompts/system_prompt.txt

diff VulnerableRAG/rag/generation/prompt_builder.py \
     SecureRAG/rag/generation/prompt_builder.py
```

Everything else — the sanitizer, the filters, the masker — is defence in depth behind those two.

---

## What to say about the results

**If SecureRAG scores clean:** the controls worked against the attacks these packs implement. Not
that it is secure.

**If a benchmark did not separate the two:** that is a finding about the *scanner*, not the targets.
A check that reports the same result for a vulnerable and a hardened application is not measuring
security.

**If something is INCONCLUSIVE:** the framework declined to claim. That is the design working.
