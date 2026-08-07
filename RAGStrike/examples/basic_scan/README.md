# Example: a basic scan

Scan one target, read the result, generate a report.

## 1. Start a target

```bash
cd ../../VulnerableRAG
RAGSTRIKE_LAB_ACK=1 python -m profiles.vulnerable.main_api      # 9000
```

## 2. Check RAGStrike can reach it

```bash
ragstrike targets --verify
```

Expect `OK vulnerable-rag`. If not, [`troubleshooting.md`](../../docs/troubleshooting.md) is indexed
by symptom.

## 3. Scan

```bash
ragstrike scan --target vulnerable-rag
```

**This takes hours** with every pack enabled, because each payload is a model call. To bound it for a
first run, disable the heavy packs:

```bash
ragstrike plugins disable prompt-injection
ragstrike plugins disable prompt-leakage
ragstrike plugins disable context-poisoning
ragstrike scan --target vulnerable-rag        # now minutes
```

Re-enable them with `ragstrike plugins enable <slug>` when you have time to let it run.

## 4. Read the outcome

| Outcome | Means |
|---|---|
| `PASS` | The plugin tested for its weakness and did not find it |
| `FAIL` | It found it, with evidence |
| `INCONCLUSIVE` | **It could not tell.** Not the same as PASS |
| `ERROR` | The plugin itself failed |
| `SKIPPED` | The target lacks a capability the plugin needs |

`INCONCLUSIVE` and `SKIPPED` are the two that get misread. A skipped pack produces no findings, and
no findings looks like a clean result unless you read coverage alongside the grade.

## 5. Exit codes, for scripting

| Code | Meaning |
|---|---|
| 0 | Success, threshold met |
| 1 | Findings exceeded the threshold |
| 2 | Configuration or validation error |
| 3 | Target unreachable |
| 4 | Scan errored |
| 5 | Authorization missing |

Distinct codes let a pipeline tell "the application is insecure" from "the scanner is
misconfigured" — opposite actions.

## From Python

See [`scan.py`](scan.py). Same engine the CLI drives; no private API.
