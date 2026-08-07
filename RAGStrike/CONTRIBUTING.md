# Contributing to RAGStrike

Thank you for considering a contribution. This document covers the workflow, the standards, and the
two contribution paths that matter most: attack packs and target adapters.

Read [`ARCHITECTURE.md`](ARCHITECTURE.md) first — it takes ten minutes and will save you a rejected
pull request.

---

## Ground rules

1. **The SDD is the source of truth.** [`docs/SDD.md`](docs/SDD.md) and its annexes define the
   architecture. If your change contradicts it, that is fine — but it needs a **superseding ADR** in
   [`docs/annex-c-adrs.md`](docs/annex-c-adrs.md), not a quiet deviation. ADRs are immutable once
   accepted; they are superseded, never edited.
2. **The dependency rule is not negotiable.** It is enforced by `lint-imports` in CI. A pull request
   that adds an exception to `.importlinter` needs a very good argument in the body.
3. **No new dependency without justification** in the pull request description. Prefer the standard
   library. Heavy or optional integrations go in `[project.optional-dependencies]`, never in the base
   install.

---

## Setup

```bash
git clone https://github.com/OWNER/ragstrike.git
cd ragstrike
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev,dashboard]"
pre-commit install
```

Verify:

```bash
pytest && lint-imports && mypy src && ruff check . && black --check .
```

Full instructions, including the Docker lab, are in [`INSTALL.md`](INSTALL.md).

---

## Workflow

Trunk-based on `main` with short-lived branches.

| Prefix | For |
|---|---|
| `feat/` | New capability |
| `fix/` | Bug fix |
| `docs/` | Documentation only |
| `pack/` | A new or updated attack pack |
| `adapter/` | A new or updated target adapter |
| `refactor/` | No behaviour change |

**Commits follow [Conventional Commits](https://www.conventionalcommits.org/):**
`feat(scheduler): add topological ordering for dependent cases`

Pull requests are squash-merged. Releases follow SemVer with a maintained
[`CHANGELOG.md`](CHANGELOG.md).

Note that the **Plugin API is versioned separately** from the application (ADR-015). A change to
anything under `plugins/base/` or `core/contracts/` may require a `PLUGIN_API_VERSION` bump even when
the application version does not move.

---

## Definition of Done

A pull request is ready when all of these are true:

- [ ] Implementation complete — no `TODO` left in the merged path
- [ ] Tests added; new public behaviour is covered
- [ ] `mypy --strict` clean
- [ ] `ruff` and `black` clean
- [ ] `lint-imports` passes
- [ ] Coverage gate met (85% in `core/`, 70% overall)
- [ ] Documentation updated, including the relevant folder `README.md`
- [ ] `CHANGELOG.md` entry added under *Unreleased*
- [ ] No new dependency, or one justified in the description
- [ ] No secrets, real endpoints, or real personal data anywhere in the diff

---

## Contributing an attack pack

This is the contribution path the project is designed around. **You should never need to modify the
core to add an attack.** If you find yourself editing something under `src/ragstrike/core/`, stop and
open an issue — that is a gap in the plugin architecture and we want to know about it.

### The path

```bash
ragstrike sdk new-pack my-technique     # produces a valid, test-passing skeleton
```

1. **Declare, do not code.** Attacks, payloads, detector bindings, and recommendations are YAML.
   Payloads are **data** rendered by a non-evaluating engine (ADR-016) — this is what lets security
   researchers who are not Python developers contribute, and it keeps the scanner's own attack
   surface small.
2. **Bind existing detectors before writing new ones.** The built-in catalog in
   `analyzers/detectors/` covers most cases, and improving a shared detector improves every pack that
   binds it. Most packs need no detector code at all.
3. **Prefer a canary.** If your technique can be proven by planting a high-entropy token and finding
   it where it should not be, do that. It converts an unanswerable semantic question into a string
   check with essentially zero false positives (ADR-005).
4. **Set `attempts` honestly.** LLM behaviour is stochastic. A single trial is a coin flip, not a
   measurement, and the scoring model uses `successes/attempts` as exploitability.
5. **Run the conformance suite** — offline, with the SDK test doubles. No LLM, no network, no Docker:
   ```bash
   pytest tests/contract/test_pack_conformance.py -k my-technique
   ```
6. **Validate in both directions.** This is the requirement people forget:
   - It **must** produce findings against VulnerableRAG
   - It **must** produce **zero** findings against SecureRAG

   A pack that fires on a hardened target is a false positive, and false positives are how security
   tools get switched off. Both directions are merge gates.

### Review criteria

- The technique is publicly documented and attributable
- Payloads are non-destructive (`destructive: false`)
- Detectors have bounded, tested false-positive behaviour
- Elevated permissions (`network_egress`, `filesystem_write`) are justified, or absent
- Payload text licensing is clear
- The pack declares its capabilities and its OWASP/ATLAS/CWE mapping

---

## Contributing a target adapter

Same principle: adapters live in `target_adapters/<name>/` and require no core change.

- Implement the `TargetAdapter` port plus the capability protocols you **genuinely** support.
  Overstating a capability is worse than omitting it — the scheduler trusts the declaration, and a
  false one corrupts the coverage accounting that every grade is qualified by.
- Pass the SDK **adapter conformance suite**. That suite is how Liskov substitutability is enforced
  rather than assumed.
- Implement `reset_session` if the provider supports it. Fresh-session semantics are what stop an
  early jailbreak from contaminating three hundred later cases and inflating the score.
- Keep provider libraries as optional extras with lazy imports.

---

## Coding standards

Full detail in [SDD §36](docs/SDD.md). The rules that come up most in review:

| Rule | Requirement |
|---|---|
| Types | Mandatory everywhere. `mypy --strict` is a gate. Bare `Any` needs an inline justification. |
| Data | Frozen dataclasses for domain objects; Pydantic **only** at API and config boundaries. |
| Async | `async def` for all I/O. No blocking calls on the event loop. |
| Module size | Soft cap 400 lines, hard cap 600. Exceeding it is a design smell, reviewed as one. |
| Function size | Soft cap 50 lines, complexity ≤ 10. |
| Naming | Domain vocabulary: `AttackCase`, `Probe`, `Signal`, `Finding`. **No** `Manager`, `Helper`, `Util`, `Processor`, or `Handler` in class names. |
| Imports | Absolute only. `ragstrike.logging` shadows the stdlib, so this matters. |
| Errors | Everything derives from `RAGStrikeError`. No bare `except Exception` outside the executor's isolation guard. |
| Logging | Structured fields, never f-strings — the message stays constant and greppable. |
| Comments | Explain *why*. The code already says *what*. |

### One convention worth memorizing

`CaseState.SUCCEEDED` means **the attack succeeded** — the target is vulnerable. State is always from
the attacker's frame; report language is always from the defender's frame ("Vulnerable"). The
translation happens in exactly one place, `reporters/strings/`. Getting this backwards in a new
module is the single most common review comment.

---

## Reporting bugs and proposing features

Use the issue templates. For attack techniques, use the **Attack Pack Proposal** template — it asks
for the detection strategy up front, because "how would we know it worked?" is the hard part and is
better answered before code is written.

## Code of Conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
