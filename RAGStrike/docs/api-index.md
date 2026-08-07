# API reference index

Three surfaces. **Only two of them answer.**

---

## 1 · CLI — complete

The full product surface. Everything works here.

| Command | Does |
|---|---|
| `ragstrike version` | Engine version and plugin API version |
| `ragstrike targets` | List targets from `configs/targets.yaml` |
| `ragstrike targets --verify` | Probe each target and report reachability |
| `ragstrike plugins` · `plugins list` | Discovered packs, active and refused |
| `ragstrike plugins info SLUG` | Full metadata for one pack |
| `ragstrike plugins validate [SLUG]` | Framework rules plus the pack's own |
| `ragstrike plugins enable SLUG` · `disable SLUG` | Persists to `configs/plugins.yaml` |
| `ragstrike plugins reload` | Force re-discovery |
| `ragstrike scan --target NAME` | Run a scan |

Scan options: `--config` · `--targets` · `--fail-on-findings / --no-fail-on-findings`.

**There is no `targets add` and no `scan --plugins`.** Targets are declared in
`configs/targets.yaml`, each with an `authorization:` block carrying `authorized_by`,
`authorization_ref`, and `scope` — a persisted record, which is what ADR-017 requires. Scope a scan by
disabling packs (`ragstrike plugins disable <slug>`), which also persists.

**There is no `ragstrike report` command.** The reporting engine is a library; the CLI surface for it
was never wired. Generate reports from Python — [`../examples/example_reports/README.md`](../examples/example_reports/README.md)
has the working snippet. Recorded in [`limitations.md`](limitations.md) and
[`roadmap-v2.md`](roadmap-v2.md).

**SDD §CLI specifies a larger surface** — `targets add|show|remove`, `report`, `history`. That is the
design; the table above is the implementation. Where they differ, the table is what runs.

`--help` on any command. [`user-guide.md`](user-guide.md) has the worked flows.

## 2 · Plugin API — stable, versioned independently

`PLUGIN_API_VERSION` — currently **1.0**, moving independently of `__version__` (ADR-015).

**The nine-method lifecycle:** `metadata` · `validate` · `setup` · `payloads` · `execute` · `analyze`
· `report` · `cleanup` · `health`.

Two invariants a pack must hold: **`payloads()` deterministic** and **`analyze()` pure**. Everything
reproducible about a scan follows from those two.

| Type | For |
|---|---|
| `BaseAttack` | The pack base class |
| `PluginMetadata` | What `metadata.yaml` becomes |
| `Payload` | One test case |
| `PluginOutcome` | `PASS · FAIL · INCONCLUSIVE · ERROR · SKIPPED` |
| `Finding` | A standardized result |
| `Capability` | What a target supports |

References: [`plugin-development.md`](plugin-development.md) ·
[`plugin-lifecycle.md`](plugin-lifecycle.md) · [`sdk-guide.md`](sdk-guide.md) ·
[`../examples/custom_pack/`](../examples/custom_pack/)

## 3 · HTTP `/api/v1` — **not implemented**

Routing exists; handlers do not. [D-03](technical-debt.md).

The dashboard already codes against this contract through a transport Protocol (ADR-021), so
implementing the handlers requires **no dashboard change**. Until then the dashboard reports
`BACKEND OFFLINE` rather than inventing data.

Planned shape, for whoever implements it:

```
GET  /api/v1/health
GET  /api/v1/targets           POST /api/v1/targets
GET  /api/v1/plugins
GET  /api/v1/scans             POST /api/v1/scans
GET  /api/v1/scans/{id}
GET  /api/v1/scans/{id}/events     (SSE — ADR-014)
GET  /api/v1/scans/{id}/findings
GET  /api/v1/reports/{id}
```

**Breaking this surface later requires `/api/v2`**, not a framework major bump — the version is in the
path for exactly that reason ([`versioning-policy.md`](versioning-policy.md)).

## Not a public API

Internal module paths. `from ragstrike.analyzers.rules.engine import ...` may move in a patch release;
use package-level exports.

## The lab applications

VulnerableRAG and SecureRAG expose an **identical** HTTP surface, checked by reading `/openapi.json`
from both and failing on divergence. Their own repositories document it.
