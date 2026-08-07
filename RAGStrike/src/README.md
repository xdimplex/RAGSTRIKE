# `src` — Source Layout Root

> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

The `src/` layout marker. The importable package is `src/ragstrike/`.

Why `src/` rather than a flat layout: it makes an accidental import of the working directory impossible. Tests import the *installed* package, so a missing entry in `package-data` or a module that only works because it happened to be on `sys.path` fails locally instead of after release.

## Responsibilities

- Contain exactly one thing: the `ragstrike` package.

## Files that will exist here later

- `ragstrike/ — the package (see its README for the layer map)`

## This folder must NEVER contain

- A second top-level package.
- Any file at this level — not even `__init__.py`.
