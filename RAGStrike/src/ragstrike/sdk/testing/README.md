# `sdk.testing` — Test Doubles

> **Layer:** cross-cutting · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md)
> **Status:** scaffold only — Phase 1 creates structure, not behaviour.

## Purpose

Scripted targets that let a pack be developed end to end with **no LLM, no network, and no Docker**. This is what makes pack development a fast loop instead of a slow one.

## Responsibilities

- FakeTarget — scripted responses.
- EchoTarget — returns the prompt.
- RefusingTarget — refuses everything, for false-positive testing.
- LeakyTarget — discloses planted canaries, for true-positive testing.
- FlakyTarget — configurable failure rate, for retry and exploitability testing.
- SlowTarget — for timeout testing.

## Files that will exist here later

- `fake_target.py`
- `leaky_target.py`
- `refusing_target.py`
- `flaky_target.py`
- `slow_target.py`

## This folder must NEVER contain

- Network access of any kind.
- Nondeterministic behaviour without an explicit seed.
