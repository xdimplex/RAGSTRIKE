# Demo script

**~10 minutes live, or pre-recorded.** Everything below is real output; nothing is staged.

> **Record this in advance.** A scan is 5–40 seconds per payload, and a live audience will not sit
> through it. If you cut, put a visible marker on the cut — implying a scan is fast is a false claim
> about performance.

---

## Before you start

```bash
# terminal 1
cd VulnerableRAG && RAGSTRIKE_LAB_ACK=1 python -m profiles.vulnerable.main_api    # 9000
# terminal 2
cd SecureRAG     && RAGSTRIKE_LAB_ACK=1 python -m profiles.secure.main_api        # 9001
# terminal 3
ollama serve          # model already pulled
```

Both targets are already declared in `configs/targets.yaml` as `vulnerable-rag` and `secure-rag`.

Both `/health` endpoints answering. Corpus ingested on both — **identical corpus, or the comparison
means nothing**.

Font large enough to read. `clear` before you begin.

---

## 1 · The target is ordinary (60s)

```bash
curl -s http://127.0.0.1:9000/api/v1/chat -X POST \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the leave policy?"}' | jq -r .answer
```

> "A normal RAG system. Retrieves from the corpus, answers with the model. Nothing unusual."

Establish normal before you break it.

## 2 · Register with authorization (45s)

```bash
ragstrike targets --verify
```

Then open `configs/targets.yaml` on screen and point at the `authorization:` block:

```yaml
  - name: vulnerable-rag
    url: "http://127.0.0.1:9000"
    authorization:
      authorized_by: "local-operator"
      authorization_ref: "LOCAL-LAB"
      scope: "Local VulnerableRAG instance owned by the operator. Loopback only."
```

> "Every target carries who authorised it and against what reference. It's a persisted record, not a
> checkbox at run time — and it ends up in the report. Change that URL to anything non-loopback and
> the scan refuses. Scanning something you don't own isn't a configuration question."

**Editing the URL live and showing the refusal lands better than the bullet point.**

## 3 · What is about to run (45s)

```bash
ragstrike plugins
ragstrike plugins info prompt-injection
```

> "Nine packs: three offensive, five evaluation, one diagnostic that just proves the harness reaches
> the target. Each one is three files in a directory — manifest, plugin, payloads as YAML. Nothing in
> the framework knows their names; there's a test that fails if anything does."

## 4 · Scan (2 min — pre-recorded)

```bash
ragstrike plugins disable prompt-leakage
ragstrike plugins disable context-poisoning
ragstrike scan --target vulnerable-rag
```

Narrate over it:

> "Every payload is a full round trip through a local model — five to forty seconds each. This is the
> honest cost of testing a real pipeline instead of a mock."

Result: **FAIL**, with findings.

## 5 · Read one finding (2 min) — *the most important section*

There is no `ragstrike report` command yet, so open a **pre-generated** report:

```bash
start examples/example_reports/ragstrike-scan-example-0001.html
```

Say that it is a prepared report rather than the one that just ran — the audience will assume
otherwise, and correcting it afterwards costs more than saying it now.

Point at four things, in order:

**The finding.** Request, response, and **the name of the detector that fired**. A finding you cannot
trace to a rule is an assertion.

**The arithmetic.** The risk score with its calculation printed. > "You can redo this by hand. That's
the difference between a score you trust and one you accept."

**Coverage, beside the grade.** > "A grade from 40% coverage and one from 100% must not look the same."

**An `INCONCLUSIVE` row.** > "The pack couldn't tell. That's not a pass. Most tools have four statuses;
this has five, and the fifth keeps the other four honest."

## 6 · The differential — *the payoff* (2 min)

```bash
ragstrike scan --target secure-rag
```

**PASS.**

> "Same pack, same payloads, same corpus. Fails against the vulnerable target, passes against the
> hardened one. That's the control group — and it's what tells me the test measures the control rather
> than something incidental. A pack that fired on both would have found nothing, however many findings
> it printed."

Pause here. This is the moment the argument closes.

## 7 · Extensibility, if there is time (90s)

```bash
cp -r examples/custom_pack plugins/demo-pack
ragstrike plugins reload
ragstrike plugins
```

> "It's there. No registration, no framework edit."

## 8 · Close (30s)

```bash
ragstrike version    # 1.0.0, plugin API 1.0
```

> "One thing I'd rather say than have you find: it hasn't produced real findings yet. The full
> differential across both targets is a multi-hour job on this hardware and I haven't completed it.
> That's in the validation report in those words."

**Say this out loud.** It is the most credible thirty seconds in the demo.

---

## If something breaks

**Ollama unreachable** → the pack reports ERROR, not a false PASS. Point at that; it is a feature.

**A scan is slower than expected** → say so. Do not apologise for real timing.

**A finding you did not expect** → good. Open it and read the detector. If it fires on SecureRAG too,
say that it would be a false positive and that the differential is exactly what catches it.

**Nothing runs at all** → `examples/example_reports/` holds real generated output, and
`RAGSTRIKE_DASHBOARD__TRANSPORT=demo` shows the interface with labelled fixtures.
