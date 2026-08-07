# Elevator pitch

---

## 30 seconds

> RAG systems have an attack surface chatbots don't: retrieved documents end up inside the prompt, so
> anyone who can get text into the corpus can get text into the model's instructions. RAGStrike tests
> for that — but the part I care about is that it ships with **two** lab targets, one vulnerable and
> one hardened. Run the same attack against both. If it fires on both, the test is measuring something
> other than the control, and you've just caught your own false positive. Without that, a scanner's
> findings aren't checkable.

## 10 seconds

> A security scanner for RAG pipelines, shipped with a hardened reference target so you can tell a
> real finding from a false positive.

## One line

> RAG security testing where the findings are checkable.

---

## If they ask one follow-up

**"What makes it different?"**

> Three things, and they're all about honesty rather than coverage. It has a fifth outcome status —
> `INCONCLUSIVE` — because "the target resisted" and "the test couldn't tell" are different facts and
> most tools merge them. Coverage is printed next to every grade, so a scan of 40% of the surface
> doesn't read like a scan of all of it. And the risk arithmetic is reproduced in the report, so you
> can check the number by hand instead of trusting it.

**"Has it found anything?"**

> Not yet, and that's in the docs. The framework's built and tested — 1,327 tests, six architectural
> contracts enforced by the build — but the full differential run is a multi-hour job on CPU that I
> haven't completed. The validation report says exactly that rather than implying otherwise.

That answer is the point. A tool that overstates its evidence is the thing this project is built
against.
