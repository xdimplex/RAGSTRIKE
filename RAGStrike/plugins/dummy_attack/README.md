# Dummy Attack

The reference plugin. It validates the scan lifecycle end to end and always returns PASS.

## What it does

Nothing security-relevant, deliberately. It sends one benign question to the target, records the
response, and reports that the framework's plan/execute/analyze/store path works.

## Why it exists

A framework validated only by a working exploit is a framework whose failure modes you discover
later, in the dark. This plugin proves the engine before any real attack is written.

## Copying it

1. Copy this directory, rename it, change ``plugin.slug`` in ``metadata.yaml``.
2. Replace ``payloads()``, ``analyze()``, and ``recommendation()`` with your real attack.
3. Drop the folder into ``plugins/``. Nothing in the engine changes.

Read ``docs/plugin-development.md`` at the repository root for the full guide.
