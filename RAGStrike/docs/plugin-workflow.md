# Plugin development workflow

From idea to shipped pack.

---

## 1. Decide what you are claiming

Before any code: **what would prove this weakness exists, and what would prove it does not?**

If you cannot answer the second half, you will write a pack that reports FAIL whenever it is
uncertain — and a scanner that cannot be wrong is a scanner nobody can trust.

Write the claim down in one sentence. It becomes the pack description.

## 2. Scaffold

```bash
cp -r examples/custom_pack plugins/my-pack
```

Or use the SDK scaffolder — see [`sdk-guide.md`](sdk-guide.md).

## 3. Write the manifest first

Not the code. The manifest is what the engine reads to decide whether to import you at all, and
writing it first forces the capability question early: what does the target actually have to support?

```bash
ragstrike plugins            # does it appear?
ragstrike plugins info my-pack
```

At this point the pack does nothing and that is correct.

## 4. Write payloads as data

Start with three: one that should clearly succeed, one that should clearly fail, one ambiguous.

The third is the important one. It is what forces you to design the INCONCLUSIVE path instead of
discovering it in production.

## 5. Implement `execute()`

One payload in, one raw result out. **No judgement here** — do not decide PASS or FAIL in `execute`.
Collect the evidence and hand it on.

Separating execution from analysis is what lets the replay harness re-analyze stored evidence without
re-attacking the target.

## 6. Implement `analyze()`

Pure. Given the recorded response, decide the outcome.

Because it is pure, you can test it against a fixture with no target running — which is what makes a
detector change verifiable in seconds instead of minutes.

## 7. Test against both halves of the lab

```bash
ragstrike scan --target vulnerable-rag
ragstrike scan --target secure-rag
```

**A pack that fires on both has found nothing.** It is measuring something other than the security
control it claims to measure, and this is the step that catches it.

## 8. Validate

```bash
ragstrike plugins validate my-pack
```

Framework rules — folder shape, manifest fields, API compatibility, class contract — plus your own
`validate()`.

## 9. Checklist and review

[`plugin-checklist.md`](plugin-checklist.md), then [`plugin-review-checklist.md`](plugin-review-checklist.md)
if someone else is reviewing.

---

## What not to do

**Do not edit the engine.** If your pack needs a change under `core/`, that is a design conversation,
not a patch — and a test will fail if you special-case a plugin name there.

**Do not import from another pack.** Packs are independent; the layer contract enforces it.

**Do not make `analyze()` call a model.** A verdict that changes between runs cannot be reproduced,
and reproducibility is the property the whole scoring model depends on.

**Do not report PASS on absence of evidence.** This is the one that matters most.
