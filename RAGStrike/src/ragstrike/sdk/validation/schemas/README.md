# `sdk.validation.schemas` — JSON Schemas

> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

JSON Schema for every YAML contract a pack ships. These let CI validate manifests without a Python environment capable of importing the pack — which is the whole point of manifest-first loading.

## Responsibilities

- One schema per contract: pack manifest, attack definition, payload set, detector binding, recommendation entry.
- Versioned alongside `PLUGIN_API_VERSION`.
- Produce errors precise enough to name the file, line, and field.

## Files that will exist here later

- `pack_manifest.schema.json`
- `attack.schema.json`
- `payload_set.schema.json`
- `detector.schema.json`
- `recommendation.schema.json`

## This folder must NEVER contain

- A schema change without a Plugin API version bump.
- Permissive schemas — `additionalProperties: true` hides typos in a contributor's manifest.
