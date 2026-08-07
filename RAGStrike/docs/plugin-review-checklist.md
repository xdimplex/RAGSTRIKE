# Plugin review checklist

For whoever reviews a pack before it lands. Written as questions to ask the *code*, because a
reviewer who only reads the README reviews the intent rather than the artifact.

---

## Safety — refuse the pack if any of these fail

- [ ] Does anything **write to the target**? Uploads, deletes, state changes. If yes, is it declared
      `destructive` and does `cleanup()` genuinely undo it?
- [ ] Does any payload contain a **real** credential, hostname, or personal detail? Lab secrets must
      be synthetic, high-entropy, and canary-tagged
- [ ] Does the pack request **elevated permissions**? If yes, is the reason specific and necessary?
- [ ] Could a payload **exfiltrate** something real if it succeeded, rather than proving success with
      a meaningless canary?
- [ ] Does anything reach a host other than the configured target?

## Correctness

- [ ] Is `payloads()` deterministic? Look for `random`, `time`, `set` iteration, `dict` ordering
      assumptions
- [ ] Is `analyze()` pure? Any network call, clock read, or randomness makes a verdict unreproducible
- [ ] Does `cleanup()` run on the exception path, and is it idempotent?
- [ ] Can `health()` raise?

## Honesty — the section that matters most

- [ ] **Does the pack ever return PASS when it simply did not detect anything?** This is the most
      common and most damaging defect. Absence of evidence is `INCONCLUSIVE`
- [ ] Is confidence capped when the detector is uncalibrated?
- [ ] Does the README state what the pack **cannot** establish?
- [ ] Does any finding claim more than its evidence supports?

## Evidence

- [ ] Does every FAIL carry request, response, and the detector that fired?
- [ ] Is evidence redacted rather than omitted?
- [ ] Do any log lines contain document text, answer text, or a secret value?

## Tests

- [ ] Is there a test for the attack **failing** against a hardened target?
- [ ] Is there a test for the INCONCLUSIVE path?
- [ ] Do the tests run with no network and no model?
- [ ] Would the tests fail if the detector were deleted? **A test that passes against a no-op
      implementation is testing nothing**

## Boundaries

- [ ] Zero edits under `src/ragstrike/core/`
- [ ] No import from another pack
- [ ] Nothing in the engine names this pack

## Recommendations

- [ ] Does each one name a **change**, not a principle? "Validate input" is not actionable;
      "delimit retrieved context and state that it is data" is
- [ ] Is the text retrieved from a catalog rather than generated?

---

## Reviewer's note

The easiest pack to approve is one that finds a lot. Be most sceptical of exactly that one: a pack
that fires often is more likely to be matching something incidental than to have found more real
weaknesses than its peers.

Run it against **SecureRAG**. If it fires there too, it is not measuring what it claims.
