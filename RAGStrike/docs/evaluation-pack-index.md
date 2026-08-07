# Evaluation pack index

The five non-offensive packs, and the categories they cover.

**They do not attack.** They ask what the system does, and whether it is the sort of thing a hardened
system does. An attack pack proves a weakness; an evaluation pack characterises a posture.

Detail: [`evaluation-plugins.md`](evaluation-plugins.md). All five in [`plugin-index.md`](plugin-index.md).

---

## Categories

### Prompt-structure integrity

Whether the pipeline keeps *instructions* and *retrieved text* distinguishable — the property whose
absence makes prompt injection possible in the first place.

| Pack | Asks |
|---|---|
| `prompt-boundary` | Is there a delimiter at all? |
| `context-separation` | Is retrieved content kept out of the instruction region? |
| `instruction-priority` | Can text inside a document outrank the system prompt? |

Three packs for one property because the property fails in three independent ways, and a system can
have any one of them and not the others.

### Answer provenance

| Pack | Asks |
|---|---|
| `source-attribution` | Does an answer name the sources it came from? |

Unattributed answers make a fabricated claim indistinguishable from a retrieved one — which is a
security property, not a UX one, because it is what makes a poisoned corpus undetectable downstream.

### Retrieval stability

| Pack | Asks |
|---|---|
| `retrieval-consistency` | Do paraphrases of one question retrieve the same material? |

Unstable retrieval makes every other result noisier: a scan that retrieves different chunks each run
cannot attribute a change to a control.

---

## How to read an evaluation result

**A FAIL here is not a proven exploit.** It says a property a hardened system holds is absent. Whether
that is exploitable depends on the deployment — an internal tool with a trusted corpus has a different
risk profile from one ingesting user uploads.

Attack packs prove; evaluation packs indicate. **The reports keep them in separate categories for
exactly that reason.**

`retrieval-consistency` carries LOW severity because it measures a quality property with security
consequences rather than a security control directly.

## Coverage

| Property | Covered |
|---|---|
| Prompt-structure integrity | ✅ three packs |
| Answer provenance | ⚠️ attribution only |
| Retrieval stability | ✅ |
| **Citation grounding** | ❌ `citation-verification` declared, not implemented |
| **Answer faithfulness** | ❌ `hallucination-evaluation` declared, not implemented |
| **Retrieval integrity** | ❌ `retrieval-integrity` declared, not implemented |

**Three of the categories a complete evaluation suite would cover are not implemented.** They are in
the Annex B catalog with their detectors specified. Listed here so the gap is a known gap.

## Running them

```bash
ragstrike plugins disable prompt-injection
ragstrike plugins disable prompt-leakage
ragstrike plugins disable context-poisoning
ragstrike scan --target vulnerable-rag
```

Scoping is done by disabling packs, not by a `--plugins` flag — `scan` has no such option, and the
disable persists to `configs/plugins.yaml`.

They are considerably faster than the attack packs — fewer payloads, and no adversarial variation.

**Run them against SecureRAG too.** An evaluation pack that reports the same posture for both targets
is not measuring the control it names.
