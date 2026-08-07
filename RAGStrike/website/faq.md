# FAQ

*Project-level questions. Operational ones are in [`../docs/faq.md`](../docs/faq.md); symptoms are in
[`../docs/known-issues.md`](../docs/known-issues.md).*

---

**Can I point it at my production RAG system?**

Not without changing the configuration deliberately, and you should think hard first. Default policy
accepts `127.0.0.1` and `localhost` only, and every scan needs a persisted authorization record.
Scanning a system you do not own is not a configuration question.

**Has it found real vulnerabilities?**

**Not yet, and the documentation says so.** The framework is built, tested, and instrumented; the full
differential run against the live lab is a multi-hour job that has not been completed.
[`validation-results.md`](../docs/validation-results.md) records this rather than implying otherwise.

Publishing a tool whose claims exceed its evidence is the failure mode this project has spent the most
effort avoiding.

**Why ship a lab instead of just a scanner?**

Because without a hardened reference target, a false positive and a finding look identical. The
differential is what makes a result checkable — a pack that fires on both targets is measuring
something other than the control it claims to measure.

**Why is it slow?**

Every payload is a full RAG round trip through a local model: 5–40 seconds on CPU. There is no
shortcut that preserves the result — a cached or mocked response tests the harness, not the target.

Scope with `--plugins`, or use GPU inference.

**Why does the dashboard say BACKEND OFFLINE?**

`/api/v1` is a scaffold. The dashboard is an HTTP client by design (ADR-010) and refuses to
manufacture data it does not have. Demo mode exists and is labelled as demo. See
[D-03](../docs/technical-debt.md).

**Why is `INCONCLUSIVE` a status?**

Because "the target resisted" and "the pack could not tell" are different claims, and reporting the
second as the first is exactly how a scanner produces false confidence. Most tools have four outcomes;
this one has five, and the fifth is the one that keeps the other four honest.

**Are plugins sandboxed?**

No. Installing a pack grants it the trust of installing a Python package, because it is one. This is
documented rather than papered over — a declared sandbox that does not exist would be worse than
none. Roadmap item R-07.

**Why Streamlit?**

The UI is a read-only view over an API. Streamlit's constraints do not bind here, and the layer
contract (ADR-010) means replacing it later touches no engine code. Recorded with alternatives in the
SDD.

**Can I add my own attack pack?**

Yes, with **zero framework edits** — enforced by a test that fails if any plugin name appears in
engine code. Three files in `plugins/`, and `ragstrike plugins` finds it. See
[`custom_plugin/`](../examples/custom_plugin/).

**Is it a replacement for a pentest?**

No. It tests a defined set of RAG-specific weakness classes with defined payloads. Absence of findings
is not proof of security, and every report says so in its Methodology section.

**Licence?**

Apache-2.0. Dependency licences are reviewed in
[`third-party-attribution.md`](../docs/third-party-attribution.md).

**Why 24 ADRs for a solo project?**

Because a decision whose reasoning is not written down gets re-litigated or accidentally reversed.
ADR-009 was later amended by ADR-022, and being able to read the original argument is what made the
amendment a decision rather than a drift.
