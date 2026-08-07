# `sdk.interfaces` — SDK Protocols

> **Layer:** cross-cutting (development-time) · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/sdk-guide.md`](../../../../docs/sdk-guide.md)
> **Status:** implemented — Phase 5.

## Purpose

`Protocol` definitions formalizing what a request builder, response parser, result builder, and validator *are*, independent of the SDK's own concrete implementations. Not a second engine contract — `BaseAttack` remains the only thing the engine actually checks.

## Responsibilities

- Declare `RequestBuilderProtocol`, `ResponseParserProtocol`, `ResultBuilderProtocol`, `ValidatorProtocol` so tests can substitute fakes and alternate implementations can satisfy the shape without subclassing the SDK's concrete classes.

## Key exports

| Name | What it is |
|---|---|
| `RequestBuilderProtocol` | Anything with `.build() -> TargetRequest`. |
| `ResponseParserProtocol` | Anything with `.text()/.json()/.chunks()/.sources()/.error()`. |
| `ResultBuilderProtocol` | Anything with `.build() -> <result>`. |
| `ValidatorProtocol` | Anything callable as `(value) -> bool`. |

## This folder must NEVER contain

- Enforcement. These are typing aids for testing and alternate implementations, not a contract the registry or scheduler checks against.
