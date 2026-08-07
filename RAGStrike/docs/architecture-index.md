# Architecture index

Where each architectural question is answered. **One canonical location per topic** — if two documents
disagree, the one named here wins.

---

## Start here

| If you want to | Read |
|---|---|
| Understand the design in 10 minutes | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) |
| Understand it completely | [`SDD.md`](SDD.md) — the source of truth |
| Know why a decision was made | [`annex-c-adrs.md`](annex-c-adrs.md) — 24 ADRs |
| Know where a file goes | [`annex-a-directory-structures.md`](annex-a-directory-structures.md) |
| Know what is not done | [`limitations.md`](limitations.md) |

## By question

| Question | Answer |
|---|---|
| What are the layers, and what enforces them? | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §1 · `.importlinter` |
| Why Clean Architecture? | ADR-001 |
| How are plugins discovered? | ADR-002, ADR-003 · [`plugin-development.md`](plugin-development.md) |
| Why is the manifest read before the code? | ADR-003 |
| Why are payloads YAML? | ADR-016 |
| What is the plugin lifecycle? | [`plugin-lifecycle.md`](plugin-lifecycle.md) |
| How does a target get abstracted? | ADR-008 |
| Why separate attack from detection? | ADR-004 |
| How is a verdict decided? | ADR-005 (canaries) · ADR-006 (aggregation) |
| How is risk scored? | ADR-011 · [`analyzer-engine.md`](analyzer-engine.md) |
| Why is coverage reported? | ADR-020 |
| How does evidence survive a detector change? | ADR-012 |
| Where does redaction happen? | ADR-013 |
| Why one report model, many renderers? | [`reporting-engine.md`](reporting-engine.md) |
| Where do recommendations come from? | ADR-019 |
| Why does the dashboard not import the engine? | ADR-010 · ADR-021 |
| Why is the API not implemented? | ADR-021 · [D-03](technical-debt.md) |
| Why two lab repositories? | ADR-009, amended by **ADR-022** |
| Why is `NOT_RUN` not a mismatch? | ADR-023 |
| Why ship with known mypy errors? | **ADR-024** · [`technical-debt.md`](technical-debt.md) |
| Why no database ORM? | ADR-007 |
| Why single-process asyncio? | ADR-018 |
| Why SSE for progress? | ADR-014 |
| Why two version numbers? | ADR-015 · [`versioning-policy.md`](versioning-policy.md) |
| Why is authorization persisted? | ADR-017 |

## Package boundaries

Every package with a README states its responsibility **and what it must never contain**. The second
half is the load-bearing one — it is what has actually caught mistakes.

29 packages have no README ([D-02](technical-debt.md)); their parents do, and every module has a
docstring.

## The measured state

[`audit-report.md`](audit-report.md) — structure, cycles, dead code, coverage, tool results.
Regenerate the structural half:

```bash
python -c "from validation.runner.audit import collect; print(collect().to_dict())"
```

## Amending

A decision changes by a **superseding ADR appended to Annex C**, never an edit. ADR-022 amends ADR-009
that way, and ADR-009's original reasoning is still readable — which is what made the amendment a
decision rather than a drift.
