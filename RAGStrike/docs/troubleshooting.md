# Troubleshooting

---

## `ragstrike plugins` shows nothing

Discovery searches `./plugins`, `./packs`, and `./src/ragstrike/attacks` **relative to the repository
root**, not to your shell's working directory. Run from the repository root, or pass
`--config /absolute/path/to/configs/config.yaml`.

If plugins appear under "refused", the reason is in the table. Common causes:

| Reason | Fix |
|---|---|
| API version incompatible | The pack declares a `requires_api` this engine does not satisfy |
| Elevated permissions | The pack asks for network or filesystem access; set `plugins.allow_elevated_permissions` if you trust it |
| Manifest invalid | `ragstrike plugins validate <slug>` names the failing rule |

---

## A scan refuses to start

| Message | Cause |
|---|---|
| "authorization" (exit 5) | The target has no authorization record in `configs/targets.yaml` |
| "out of scope" | Non-loopback target. Needs **both** `allow_remote_targets: true` and an `allowed_hosts` entry |
| "unreachable" (exit 3) | `ragstrike targets --verify` will say which target and why |

---

## Every plugin returns INCONCLUSIVE

Usually the target is answering but saying nothing useful — a stopped Ollama behind a running API
produces exactly this. Check the target's own health endpoint first:

```bash
curl -s localhost:9000/health | jq '.components'
```

INCONCLUSIVE is the correct outcome here, not a bug: the framework could not tell, and it says so
rather than guessing PASS.

---

## Scans are very slow

Scan time is dominated by the **target's model**, not by RAGStrike. A 4B model on CPU can take
several seconds per payload, and a standard profile issues hundreds.

- Use `--profile quick` for a smoke run
- Run Ollama on a GPU
- Reduce `retrieval.top_k` on the target

`python -m validation.runner` separates framework time from target time, so you can see which is
which.

---

## `lint-imports` fails to run

On Windows, Smart App Control can block `_rustgrimp*.pyd` — the native extension `grimp` uses. The
symptom is a refusal to load rather than a Python error, and the CodeIntegrity event log records it.

This is an OS policy, not a project bug. Either disable Smart App Control (a system-wide, irreversible
setting — your call), or run the gate in CI where the policy does not apply.

---

## The dashboard shows "BACKEND OFFLINE"

Expected. The `/api/v1` server is not implemented yet — see [`limitations.md`](limitations.md). The
dashboard is a complete client written against the published contract, and it shows an honest offline
state rather than fabricating data.

```bash
RAGSTRIKE_DASHBOARD__TRANSPORT=demo streamlit run src/ragstrike/dashboard/app.py
```

---

## A PDF uploads to VulnerableRAG but not to SecureRAG

That is the validation layer working. SecureRAG checks size, extension, MIME type, and **magic
bytes** before the parser. The error envelope names which check refused:

```json
{"error": {"code": "invalid_document", "message": "...does not contain a PDF signature...",
           "hint": "The file may be renamed, corrupt, or truncated."}}
```

---

## The two halves of the lab disagree about something other than security

That is drift, and it is the failure ADR-009 warned about. Run:

```bash
cd SecureRAG && pytest tests/parity
```

The suite asserts both applications expose the same endpoints with the same response schemas.
`SecureRAG/docs/compatibility-guide.md` lists every file that is *supposed* to differ; anything else
is drift.

---

## Where to look

| Symptom | First place |
|---|---|
| Anything at all | `logs/ragstrike.jsonl`, filtered by scan id |
| A finding you doubt | The report's Evidence section — request, response, detector, arithmetic |
| A score you doubt | The report's Risk Analysis section reproduces the calculation |
| Framework health | `python -m validation.runner --checks-only` |


---

# Additions at v1.0.0

Symptoms that came up during the pre-release audit, and the answers that were not obvious.

## "It found nothing, so the target is secure"

**The most dangerous misreading available**, and it is not an error message — it is a conclusion you
reach on your own.

Check three things before believing it:

1. **Coverage**, printed beside the grade. A scan that skipped six packs and found nothing is not a
   clean scan.
2. **`SKIPPED` rows and their reasons.** A pack skipped for a missing capability produced no findings
   because it never ran.
3. **`INCONCLUSIVE` rows.** The pack could not tell. That is not a pass.

Then run the same scan against **SecureRAG**. If it also finds nothing there, you have learned
nothing about either target.

## A pack fires against SecureRAG too

Two possibilities, and they call for opposite actions:

- **A false positive.** The detector is matching something incidental
- **A real gap in SecureRAG.** The control does not cover this case

**Do not assume which.** Open the finding and read the detector and the response. This ambiguity is
precisely why the lab pair exists — without SecureRAG you would never have seen the question.

## `lint-imports` fails after a refactor

**That is a design failure, not a lint failure.** The fix is almost never to edit `.importlinter`.

Two causes cover nearly every case:

- **Sibling import.** Modules on the same contract row are peers and may not import each other
- **An indirect chain.** `a → b → c` breaks a contract even though no single import looks wrong

A function-level import does not escape it: `grimp` reads the AST, not the runtime. If you deferred an
import to break the cycle, the contract still sees it.

## The audit reports a cycle

Check which field. `import_time_cycles` can deadlock and needs fixing. `deferred_cycles` exist only
through a `TYPE_CHECKING` block or a function-level import — both are the *standard resolutions* for a
cycle, they cannot deadlock, and there is exactly one, in `plugins/base/`, with a comment saying so.

## `bandit` reports something in code you did not touch

Six known false positives, each annotated at the site with its reason. `B105 hardcoded_password` is
skipped project-wide because this framework's outcome vocabulary literally contains the word `PASS`.

**A new finding is not one of these.** Read it rather than adding a skip.

## Windows: a ctypes call returns 0 or garbage

Declare `argtypes` and `restype`. Without them a 64-bit `HANDLE` is truncated to `int` and the call
fails silently — which is exactly how peak-memory measurement read 0 for a while.

## A scan produces something you do not believe

Run `dummy-attack` first. It is the diagnostic pack: it passes everywhere, and a FAIL from it means
the harness is broken rather than the target.

## More

[`known-issues.md`](known-issues.md) — symptom, cause, workaround.
[`limitations.md`](limitations.md) — what the framework does not attempt.
[`technical-debt.md`](technical-debt.md) — what is owed and why.
