# Example: the comparison scan

Scan both halves of the lab and compare. **This is the example that demonstrates what the project is
for** — everything else is machinery around making this comparison trustworthy.

## Why it needs two applications

A scanner that reports findings tells you nothing on its own: you cannot tell a true positive from a
false one without something known-good to compare against.

VulnerableRAG and SecureRAG are identical except for their security controls — same pipeline, same
model, same corpus, same API. So a difference in results is attributable to the controls and nothing
else. That is the only condition under which "RAGStrike found 12 issues" means anything.

## 1. Start both

```bash
cd ../../VulnerableRAG && RAGSTRIKE_LAB_ACK=1 python -m profiles.vulnerable.main_api   # 9000
cd ../../SecureRAG     && RAGSTRIKE_LAB_ACK=1 python -m profiles.secure.main_api       # 9001
```

## 2. Seed both with the *same* corpus

```bash
cd ../../VulnerableRAG
for f in corpus/benign/*.pdf; do
  curl -s -X POST localhost:9000/upload -F "file=@$f;type=application/pdf" -o /dev/null
  curl -s -X POST localhost:9001/upload -F "file=@$f;type=application/pdf" -o /dev/null
done
```

**Do not skip this.** A differential over different corpora measures the corpora. Confirm:

```bash
curl -s localhost:9000/documents | jq '{count, total_chunks}'
curl -s localhost:9001/documents | jq '{count, total_chunks}'
```

Both must match.

## 3. See the difference before scanning anything

```bash
curl -s localhost:9000/chat -H 'content-type: application/json' \
  -d '{"message":"What is the remote work policy?","include_prompt":true}' | jq -r .prompt

curl -s localhost:9001/chat -H 'content-type: application/json' \
  -d '{"message":"What is the remote work policy?","include_prompt":true}' | jq -r .prompt
```

One is a flat string with credentials in it. The other is fenced, labelled, attributed, and
credential-free. **Thirty seconds, and it explains the whole project better than any diagram.**

## 4. Run the automated comparison

```bash
cd ../../RAGStrike
python -m validation.runner --targets vulnerable-rag secure-rag
```

Writes `validation/reports/validation-summary.{json,md}`.

## 5. Read the right column

Not the pass rate — **`Separates`**.

A benchmark on which both halves agree has validated nothing about the difference between them, even
when both matched their own expectation. A run where nothing separated the two targets has
established nothing, and the report says so rather than burying it in a percentage.

## What this costs

Hours per target on CPU. Overnight is the realistic answer, or use GPU-backed inference. To get the
mechanism working end to end in minutes first, disable the heavy packs as in
[`../basic_scan/`](../basic_scan/) — you will see `NOT_RUN` for most benchmarks, with the reason
stated, which is the honest partial result rather than a fabricated one.
