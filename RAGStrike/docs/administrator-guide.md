# Administrator guide

> Configuration, safety policy, storage, and logging.

---

## Configuration precedence

```
built-in defaults  ->  configs/config.yaml  ->  RAGSTRIKE_* environment  ->  CLI flags
```

Nested keys use a double underscore: `RAGSTRIKE_ENGINE__MAX_CONCURRENCY=8`.

Validation happens once, at startup, and fails fast with the exact field path. A scan runs for
minutes; discovering at minute nine that a value was the wrong type is not acceptable.

**Never put a secret in `configs/config.yaml`.** It is committed. Secrets come from the environment.

---

## The safety policy

Three settings, and they are why a fresh install can only reach the local machine:

```yaml
safety:
  require_authorization: true
  allow_remote_targets: false
  allowed_hosts: ["localhost", "127.0.0.1", "::1"]
```

Reaching a non-loopback host requires **both** `allow_remote_targets: true` **and** an entry in
`allowed_hosts`. Either alone is refused. The check lives in `target_adapters.build_adapter`, so
every path — scan, `targets --verify`, any future caller — passes through it and none can skip it.

`require_authorization` is not a formality. A target without an authorization record cannot be
scanned, and the record is carried into every report, so a report always says who authorized the
testing that produced it.

---

## Plugin management

Discovery is automatic: drop a directory containing `pack.yaml` into any of
`./plugins`, `./packs`, or `./src/ragstrike/attacks` and it appears. There is no registration step
anywhere in the engine.

```bash
ragstrike plugins                  # health table
ragstrike plugins enable <slug>    # persists to configs/plugins.yaml
ragstrike plugins disable <slug>
ragstrike plugins validate         # every rule against every plugin
ragstrike plugins reload
```

A plugin requesting network egress or filesystem writes is **refused** unless
`plugins.allow_elevated_permissions: true`. v1 does not sandbox at the OS level — declaring
permissions makes intent auditable, which is a weaker guarantee, stated honestly.

---

## Storage

| Path | Holds |
|---|---|
| `data/scans.db` | SQLite: scans, results, findings, reports |
| `reports/` | Rendered reports |
| `logs/` | JSON-lines application logs |

Migrations are **append-only** by design and run automatically at startup. `MIGRATIONS` in
`database/migrations/runner.py` is never reordered or edited in place — a database that has already
applied migration 3 must see the same migration 3 forever.

---

## Logging

```yaml
logging:
  level: INFO
  log_dir: "./logs"
  json_lines: true
```

JSON lines by default, so logs are greppable and machine-readable. Every record carries the scan id
where one exists.

---

## Operational checks

```bash
python -m validation.runner --checks-only
```

Ten consistency checks covering configuration, discovery, the SDK, the analyzer, findings, reports,
the database, logging, the dashboard, and target communication. Fast, needs no target, and is the
right thing to run after an upgrade or a configuration change.
