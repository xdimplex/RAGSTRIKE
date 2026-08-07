# Plugin Lifecycle

The framework calls plugin methods in a fixed order. This is that order, and the invariants each
step depends on.

---

## The two lifecycles

A plugin lives through **two** lifecycles:

* **Registration** — happens once, when the framework starts. It decides whether the plugin
  becomes a runnable thing at all.
* **Per-scan** — happens once per scan the plugin participates in. It runs the actual attack.

They are separate because their failure modes are separate. A plugin that fails registration is
refused and never runs. A plugin that fails per-scan may still run in the next scan (its
`healthcheck()` might report healthy against a different target).

---

## Registration

```
              +---------------------+
              |  discover(directories, entry points)  |
              +---------------------+
                        │
                        ▼
                 read metadata.yaml
                (no plugin code imported)
                        │
                        ▼
            +--------------------------+
            |  framework validation    |
            |  - folder shape          |
            |  - manifest fields       |
            |  - API compatibility     |
            +--------------------------+
                        │  passes
                        ▼
                   import module
                        │
                        ▼
            +--------------------------+
            |  class validation        |
            |  - inherits BaseAttack   |
            |  - implements required   |
            +--------------------------+
                        │  passes
                        ▼
              build PluginContext
              (config from plugins.yaml)
                        │
                        ▼
                   instantiate
                        │
                        ▼
              +------------------+
              |  plugin.validate() |  ← plugin's own rules
              +------------------+
                        │  passes
                        ▼
              register as ACTIVE
                        │
                        ▼
              publish LOADED event
```

**A failure at any step is not fatal to the framework.** The plugin is recorded in
`PluginHealth.rejected` with a machine-readable reason, and `ragstrike plugins list` shows it in
the refused table. A security tool that refuses to start because one optional extension is
malformed simply will not be run.

---

## Per-scan

Called once per plugin, per scan, by `ScanScheduler._run_one`:

```
                publish STARTED event
                        │
                        ▼
                   healthcheck()
                        │
              healthy? │  no ─────► SKIPPED result (with rule detail)
                        │                          │
                       yes                         ▼
                        │           publish FINISHED event
                        ▼
                     setup()
                        │
                        ▼
     ┌────────────────────────────────┐
     │  try:                          │
     │      payloads = payloads()     │
     │      records  = execute(...)   │  ← the only I/O
     │      analysis = analyze(...)   │  ← pure
     │      recommendation = ...      │
     │  finally:                      │
     │      cleanup()   ← ALWAYS      │
     └────────────────────────────────┘
                        │
              success ──┤── error
                        │       │
                        │       ▼
                        │  publish FAILED event
                        │  return ERROR result
                        ▼
              publish FINISHED event
              return PASS/FAIL result
```

### Invariants

1. **Cleanup always runs.** Even when `execute()` raised, even when the scan was cancelled.
   The `finally` block is the isolation boundary; a plugin that leaks state on error is a plugin
   that corrupts the next scan.

2. **Cleanup errors do not change the outcome.** A leaking cleanup must not turn a passing scan
   into an errored one. Per-cleanup failures are logged; the outcome is what the plugin's
   `analyze()` decided.

3. **Healthcheck exceptions are ERRORs, not SKIPs.** A crashing healthcheck is a plugin bug.
   Reporting it as SKIPPED would hide it. Reporting it as ERROR surfaces it in the results.

4. **Cancellation propagates.** `asyncio.CancelledError` is a control-flow signal, not a plugin
   failure. Swallowing it would hang a scan.

5. **Events fire even on failure.** A subscriber can rely on STARTED then (FINISHED or FAILED).
   The scheduler emits FAILED on any exception path and FINISHED on any completed path.

---

## Coverage semantics

| Outcome | Counts as executed? | Meaning |
|---|---|---|
| `PASS` | yes | Target resisted this attack. |
| `FAIL` | yes | Target is vulnerable. |
| `ERROR` | yes | The plugin or transport broke. Says nothing about security. |
| `SKIPPED` | **no** | A coverage gap. The scan report shows it separately from executed cases. |

`SKIPPED` is subdivided in the log by *why*: capability mismatch (target does not offer what the
attack needs), or healthcheck refusal (the plugin cannot help against this target today). An
operator can tell "we did not test this" from "we tested it and nothing happened", which are very
different claims about security posture.

---

## Events

Every plugin lifecycle stage emits an event. The default engine ships with a no-op bus, so no
subscribers exist yet — but the vocabulary is fixed so that later phases can add them without a
plumbing change.

| Event | When |
|---|---|
| `plugin.loaded` | Registration succeeded. |
| `plugin.enabled` | Operator ran `ragstrike plugins enable`. |
| `plugin.disabled` | Operator ran `ragstrike plugins disable`, or the plugin was refused because `plugins.yaml` disabled it. |
| `plugin.updated` | Reserved. Fires when a plugin's version changes across discoveries. |
| `plugin.started` | The scheduler is about to run this plugin. |
| `plugin.finished` | The plugin completed (any outcome). |
| `plugin.failed` | An exception escaped a plugin method the scheduler wraps. |

Subscribers implement the `EventBus` protocol (`src/ragstrike/plugins/events.py`); `InMemoryBus`
is provided for tests.
