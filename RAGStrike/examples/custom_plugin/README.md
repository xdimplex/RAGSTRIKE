# Example: writing a plugin

**A complete working pack already exists at [`../custom_pack/`](../custom_pack/)** — manifest,
plugin, payloads. Read that one to see a finished pack.

This directory is the **guide to copying it**: what each piece is for, which rules are enforced, and
what to verify before you ship. Deliberately no second copy of the code — two templates drift, and
then neither is trustworthy.

## The claim being demonstrated

**A new attack pack requires zero edits under `core/`.** Not "few". Zero.

That is enforced, not promised: a test parses every module under `src/ragstrike/` and asserts no
plugin name appears in engine code. If someone special-cases a pack in the engine, the build fails.

## Three files

```
plugins/my-pack/
├── metadata.yaml      what the engine reads BEFORE importing your code
├── plugin.py          the class
└── payloads/
    └── standard.yaml  your test cases, as DATA
```

Drop that directory into `plugins/` and run `ragstrike plugins`. It appears. There is no registration
step anywhere.

## Why the manifest comes first

The registry reads `metadata.yaml` and decides compatibility and capability fit **before importing
any plugin code** (ADR-003). A pack that declares an incompatible API version, or asks for a
capability the target lacks, is refused with a reason — rather than imported and then crashing.

That is also why a broken third-party pack cannot take the engine down at discovery time.

## Why payloads are data

`payloads/*.yaml`, never Python. Three reasons, in order of how much they matter:

1. **A payload file is reviewable by someone who does not read Python.** Security review of an attack
   corpus should not require a code review.
2. **Payloads are never evaluated** (ADR-016). They are loaded and sent. A payload format that could
   execute would make installing a pack equivalent to running arbitrary code — which is already true
   of `plugin.py`, and there is no reason to widen it.
3. Determinism. The same file produces the same scan.

## The lifecycle

Nine methods; you override the ones you need. The rest have working defaults.

| Method | When | Must be |
|---|---|---|
| `metadata()` | Discovery | Cheap, no I/O |
| `validate()` | `plugins validate` | Pure |
| `setup()` | Once per scan | — |
| `payloads()` | Once per scan | **Deterministic** |
| `execute()` | Per payload | The attack |
| `analyze()` | After execution | **Pure.** No network |
| `report()` | After analysis | — |
| `cleanup()` | Always, even on failure | Idempotent |
| `health()` | On demand | Never raises |

`payloads()` being deterministic is what makes a scan reproducible; `analyze()` being pure is what
keeps a verdict explainable.

## The rule most first packs get wrong

**Return `INCONCLUSIVE` when you cannot tell.**

The temptation is to return `PASS` when your detector did not fire. But "the target resisted" and
"nobody knows" are different claims, and reporting the second as the first is how a scanner produces
false confidence. If the response was empty, or the target ignored the payload entirely, or your
detector had nothing to calibrate against — say so.

## Verify

```bash
ragstrike plugins                    # does it appear?
ragstrike plugins validate my-pack   # every framework rule plus your own
ragstrike plugins info my-pack       # what the engine thinks it is
```

Then the [plugin checklist](../../docs/plugin-checklist.md) before you ship.

## Further reading

- [`../custom_pack/`](../custom_pack/) — the complete worked pack
- [`../../docs/plugin-development.md`](../../docs/plugin-development.md) — the full guide
- [`../../docs/plugin-lifecycle.md`](../../docs/plugin-lifecycle.md) — each method in detail
- [`../../docs/sdk-guide.md`](../../docs/sdk-guide.md) — the SDK helpers
- [`../../docs/plugin-testing-guide.md`](../../docs/plugin-testing-guide.md) — how to test one
