# `dashboard` — Streamlit UI (Layer 4)

> **Layer:** 4 — Interface  ·  **SDD reference:** [SDD §24](../../../docs/SDD.md), [ADR-010](../../../docs/annex-c-adrs.md)
> **Status:** implemented in Phase 12 — full guide in [`docs/dashboard.md`](../../../docs/dashboard.md).

## Purpose

Nine pages, and a **pure HTTP client of the API**. It may not import `core`, `models`, `database`, or
any other engine package — import-linter contract 3 fails CI if it does, and the contract catches
*indirect* chains too, so reaching a `Finding` through the reporting engine breaks it just as surely
as importing `ragstrike.models`.

The reason is structural: Streamlit re-runs its entire script on every widget interaction, so engine
state held in that process is either lost or duplicated. Forcing the UI through the API also proves
the API is complete and keeps the dashboard replaceable.

## Run it

```bash
streamlit run src/ragstrike/dashboard/app.py
```

The `/api/v1` server is not implemented yet, so without one every page shows the `BACKEND OFFLINE`
banner and a specific empty state — the honest state of the system, not a failure. To explore the
interface with sample data:

```bash
RAGSTRIKE_DASHBOARD__TRANSPORT=demo streamlit run src/ragstrike/dashboard/app.py
```

Demo mode carries a `DEMO MODE` banner on every page, derived from the transport rather than from a
setting. No configuration removes the banner while the data stays fake.

## Responsibilities

- Render the nine pages: Dashboard, Scan Center, Targets, Plugins, Reports, Scan History, Settings,
  System Status, About.
- Talk to the engine exclusively through `services/`, which talks exclusively through a transport.
- Show coverage alongside every grade — a grade without its coverage is misleading (ADR-020).
- Require the authorization confirmation before enabling START SCAN (ADR-017).

## Layout

| Folder | Responsibility |
|---|---|
| `pages/` | One module per page, each exposing a single `render(context)`. |
| `components/` | Sixteen reusable components — pure functions returning HTML, no Streamlit. |
| `widgets/` | Charts and tables, the parts that need pandas or Altair. |
| `layouts/` | The shell: stylesheet, sidebar, banners, toast queue, error boundary. |
| `navigation/` | The route registry and the router. |
| `services/` | Seven services over one transport. The only route to the engine. |
| `state/` | The session-state key registry and its typed accessor. |
| `theme/` | Palettes, design tokens, and the generated stylesheet. |
| `assets/` | The wordmark, inline. |
| `app.py` | Session bootstrap and render order. |
| `config.py` | `RAGSTRIKE_DASHBOARD__*`. |
| `context.py` | The `PageContext` every page receives. |

Tests live in the repository's `tests/` tree like every other subsystem —
`tests/unit/test_dashboard_*.py` and `tests/integration/test_dashboard_integration.py`.

## This folder must NEVER contain

- `from ragstrike.core import ...` or any other engine import. This is machine-enforced.
- Business logic, scoring, or analysis. A page that decides a verdict is a second opinion about the
  one thing the engine exists to decide.
- Direct database or filesystem access.
- A colour literal outside `theme/`. A test enforces this; it is what makes adding a theme a data
  change rather than a search-and-replace.
- An unescaped interpolation into HTML. Payloads and target responses reach these components
  verbatim, so an unescaped one turns the tool's own corpus into an XSS payload.
