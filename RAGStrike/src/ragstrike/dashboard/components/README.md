# `dashboard.components` — Reusable UI Components

> **Layer:** Layer 4 · **SDD:** [`docs/SDD.md`](../../../../docs/SDD.md) · **Guide:** [`docs/dashboard.md`](../../../../docs/dashboard.md)
> **Status:** implemented in Phase 12.

## Purpose

Shared building blocks, so a severity badge looks and means the same on every page it appears on.

Every component here is a **pure function returning an HTML string**, except the three in
`controls.py` that need real Streamlit widgets. That is not an aesthetic preference: it is what lets
the component tests assert on exact markup instead of screenshots, and what keeps the whole library
importable in an environment with no Streamlit installed.

## The sixteen

| Component | Module |
|---|---|
| Status Card, Metric Card, Plugin Card, Target Card, Report Card | `cards.py` |
| Risk Badge, Severity Badge (plus grade badge and the grade hero) | `badges.py` |
| Progress Bar (plus the live scan panel and severity bars) | `progress.py` |
| Log Viewer | `log_viewer.py` |
| Timeline | `timeline.py` |
| Notification Toast, Loading Overlay, Empty State (plus error panels and banners) | `feedback.py` |
| Search Bar, Filter Panel, Confirmation Dialog | `controls.py` |
| Escaping and tag assembly | `html.py` |

## Two rules that are load-bearing

**Escape everything.** These components render with `unsafe_allow_html=True`, and much of what they
render is attacker-influenced by design — payload text, target responses, plugin descriptions from
third-party packs. A component that fails to escape has an XSS hole whose exploit is the tool's own
test corpus. `html.escape` is applied exactly once, at the point a value becomes an attribute or text.

**Colour means something.** An operator reads colour before text, so an unknown severity renders
informational rather than red (unknown is not severe), INCONCLUSIVE renders as a warning rather than
grey (a result that needs attention), and no two severities share a colour within a palette.

## This folder must NEVER contain

- API calls — components render what they are given.
- A colour literal. Ask the `Palette` for one; a test enforces it.
- Rendering a grade without its coverage fraction (ADR-020).
