# `configs/profiles` — Scan Profiles

> **Layer:** configuration · **SDD:** [`docs/SDD.md`](../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Named execution policies: which packs, which payload tiers, how many attempts, what concurrency, what budget, what seed. Precedence level 3.

## Responsibilities

- quick — ~90 cases, under 4 minutes, highest-impact categories.
- standard — ~400 cases, under 15 minutes, the default.
- deep — ~1200 cases, every pack and tier, five attempts per payload.
- Fix the seed so a profile produces a reproducible plan (SC4).

## Files that will exist here later

- `quick.yaml`
- `standard.yaml`
- `deep.yaml`

## This folder must NEVER contain

- A secret.
- A profile that disables the rate limiter or the authorization requirement.
