# The RAGStrike Dashboard

> **Phase 12** · Layer 4 (Interface) · [ADR-010](annex-c-adrs.md), [SDD §24](SDD.md)

The Streamlit interface. Nine pages, sixteen reusable components, seven services, one theme system,
and a hard architectural rule: **it never imports the engine.**

---

## 1. Architecture

### The rule that shapes everything else

`ragstrike.dashboard` may not import `core`, `models`, `database`, `scheduler`, `analyzers`,
`plugins`, or `target_adapters`. This is ADR-010, and it is machine-enforced — `lint-imports`
contract 3 fails CI on violation.

It is stricter than it first looks. The contract catches **indirect** chains, so this breaks it:

```
dashboard.services  ->  reporters.service  ->  analyzers.base.finding  ->  models.values.enums
```

Importing the reporting engine to reach a `Finding` is as much a violation as importing
`ragstrike.models` directly. The practical consequence: the dashboard reaches the engine across a
**process boundary** or not at all.

Three reasons this is the right constraint rather than an inconvenience:

| | |
|---|---|
| **Streamlit's execution model** | The whole script re-runs on every widget interaction. Engine state held in that process is lost or duplicated. |
| **The API stays provably complete** | The reference UI cannot cheat by reaching past it. |
| **The dashboard is replaceable** | And the engine can run on a different machine. |

### The layers

```
pages/          one module per page, one render(context) each
  ↓
layouts/        the shell: stylesheet, sidebar, banners, toasts, error boundary
components/     pure HTML builders, no Streamlit
widgets/        composite views that need pandas or Altair
  ↓
services/       the only route to the engine — seven services over one transport
state/          typed, key-checked session state
theme/          palettes, tokens, the generated stylesheet
navigation/     the route registry and the router
  ↓
transport       HTTP to /api/v1  ·  or the demo fixture
```

Dependencies point downward. A page may call a service; a service may never render.

### The transport, and an honest gap

The dashboard is written against `/api/v1` **exactly as SDD §22.2 specifies it** — same paths, same
verbs, same error envelope.

**That API is not implemented yet.** `src/ragstrike/api/` is still the Phase 1 scaffold. This phase
implements the client, not the server, because building the server here would merge two phases.

The consequence is designed for rather than hidden:

- **`http`** — the default. Against a running API, everything works. Against no API, every page shows
  the `BACKEND OFFLINE` banner and a specific empty state. That is the brief's "Backend Offline"
  requirement, and it is the honest state of the system today.
- **`demo`** — opt-in, via `RAGSTRIKE_DASHBOARD__TRANSPORT=demo`. A deterministic in-memory fixture
  answering the same routes, so the interface can be demonstrated, reviewed, and tested end to end.
  It carries a **`DEMO MODE`** banner on every page, derived from the transport rather than from a
  setting, so no configuration makes the banner go away while the data stays fake.

Demo mode is never inferred. An operator gets sample data only by asking for it by name.

Two endpoints the dashboard needs are extensions beyond SDD §22.2, and are documented as such:
`GET /scans/{id}/progress` (the polling companion to the SSE stream, since the brief specifies
polling) and `POST /packs/{slug}/{enable|disable|validate}` plus `POST /packs/reload` (the Plugins
page operations the brief names). Both are marked in `services/demo.py`.

---

## 2. Folder responsibilities

| Folder | Owns | Never contains |
|---|---|---|
| `pages/` | One module per page, exposing `render(context)`. | Requests, colours, business logic. |
| `components/` | Pure functions returning HTML strings. | Streamlit, except the three widgets in `controls.py`. |
| `widgets/` | Charts and tables — the parts that need pandas or Altair. | Anything a plain string could express. |
| `layouts/` | The application shell and the error boundary. | Page content. |
| `navigation/` | The route registry and the router. | Streamlit (the registry is importable anywhere). |
| `services/` | Every call to the backend, and the DTOs. | Any UI, enforced by a test. |
| `state/` | The session-state key registry and typed accessor. | Anything a page could hold locally. |
| `theme/` | Palettes, tokens, the generated stylesheet. | — |
| `assets/` | The wordmark, as inline SVG. | Remote URLs; a fetched logo is a tracking pixel. |
| `config.py` | Reading `RAGSTRIKE_DASHBOARD__*`. | Engine configuration. |
| `context.py` | The `PageContext` every page receives. | — |
| `app.py` | Session bootstrap and render order. | Anything else. |

Tests live in the repository's `tests/` tree, not inside the package, matching every other subsystem:
`tests/unit/test_dashboard_*.py` and `tests/integration/test_dashboard_integration.py`.

---

## 3. The pages

| Page | Responsibility |
|---|---|
| **Dashboard** | Posture overview: version, status, counts, last scan, recent findings, activity, quick actions. |
| **Scan Center** | The one page that starts work. Target, profile, categories, plugins, name → START SCAN → live progress, stage, current plugin, estimate, logs, cancel. |
| **Targets** | Configured targets, health, adapter, authorization record. Add, edit, delete, test connection. |
| **Plugins** | Installed inventory with versions, categories, severities. Enable, disable, reload, validate, metadata. |
| **Reports** | Generated reports. Search, filter, sort, open, export, delete. |
| **Scan History** | Every previous scan. Detail, replay, generate report, compare. |
| **Settings** | Session preferences, and the effective configuration read-only. |
| **System Status** | Eight subsystems, host resources, uptime, versions. |
| **About** | What the tool claims, what it does not, and what is permanently out of scope. |

### Decisions worth knowing

**START SCAN is disabled until authorization is confirmed.** This is a *second* gate. The backend
enforces each target's own authorization record independently and refuses regardless of what the UI
sends (ADR-017). The redundancy is deliberate: the cost is one checkbox, and the failure it prevents
is scanning a system nobody agreed to have scanned.

**The Targets page does not enforce scope.** Local-only is enforced in
`target_adapters.build_adapter`, where every path — scan, verify, CLI — passes through it and none
can skip it. The page *shows* the policy: non-local targets get a visible warning and the add form
states the rule before submission. A second implementation here would be a second opinion, and the
failure mode of two opinions about "is this host allowed" is that the permissive one wins by
accident.

**Comparison is a backend call.** Diffing two scans looks like set arithmetic on finding titles and
is not: finding identity is the analyzer's rule, and cross-scoring-model comparison is refused rather
than approximated (ADR-011).

**Every grade renders with its coverage.** ADR-020. A grade computed from half the intended cases is
a different claim from one computed from all of them.

---

## 4. Component guide

Sixteen components, all **pure functions returning HTML strings** — which is why the component tests
assert on markup rather than screenshots, and why the whole library imports without Streamlit.

| Component | Module | Function |
|---|---|---|
| Status Card | `cards.py` | `status_card` |
| Metric Card | `cards.py` | `metric_card` |
| Progress Bar | `progress.py` | `progress_bar` |
| Plugin Card | `cards.py` | `plugin_card` |
| Target Card | `cards.py` | `target_card` |
| Report Card | `cards.py` | `report_card` |
| Risk Badge | `badges.py` | `risk_badge` |
| Severity Badge | `badges.py` | `severity_badge` |
| Log Viewer | `log_viewer.py` | `log_viewer` |
| Timeline | `timeline.py` | `timeline` |
| Search Bar | `controls.py` | `search_bar` |
| Filter Panel | `controls.py` | `filter_panel` |
| Confirmation Dialog | `controls.py` | `confirmation_dialog` |
| Notification Toast | `feedback.py` | `toast` |
| Loading Overlay | `feedback.py` | `loading_overlay` |
| Empty State | `feedback.py` | `empty_state` |

### Escaping is not optional here

Every component renders with `unsafe_allow_html=True`, and much of what it renders is
**attacker-influenced by design**: payload text, target responses, plugin descriptions from
third-party packs, finding titles built from matched spans. A dashboard that pretty-prints an
injection payload without escaping has an XSS hole whose exploit is literally the tool's own corpus.

`components/html.py` escapes exactly once, at the point a value becomes an attribute. A test asserts
that a `<script>` tag comes out inert from every component that takes text.

### Colour carries meaning

An operator reads colour before text, so the mappings are total and deliberate:

- Every severity has its own colour; a test asserts no two share one within a palette.
- An **unknown** severity renders informational, never red — an unrecognised value is *unknown*, not
  *severe*, and painting it red manufactures alarm from a version mismatch.
- **INCONCLUSIVE** is warning-coloured, not grey. "We could not tell" needs attention; greying it out
  is how it gets read as "fine".
- Cards carry colour on a left rail rather than as a fill, so twelve HIGH findings stay scannable
  instead of turning the page into a warning light.

### Empty states are a real component

Most of this dashboard is empty most of the time — no scans yet, no reports yet, no backend yet. An
empty region with nothing in it is indistinguishable from a broken one, so every list renders an
empty state saying which it is and what to do next. That single decision is most of what the brief's
error-handling section asks for.

---

## 5. Navigation guide

One registry, in `navigation/routes.py`. The sidebar, the router, Home's quick actions, and
global-search results all read it. Written four times it drifts within a week.

```python
Route(
    id="reports",
    title="Reports",
    icon="▤",
    group="Analyse",
    module="ragstrike.dashboard.views.reports",
    summary="Generated reports, searchable and exportable.",
    needs_backend=True,
)
```

- Groups render in `NAV_GROUPS` order; empty groups are omitted rather than left as bare headings.
- `needs_backend=False` marks the four pages that work offline — Home, Settings, System Status, and
  About. System Status is on that list because "is the backend down" is precisely what it answers.
- An unknown page id falls back to Home rather than raising. A bookmark from a version with different
  pages should land somewhere useful.
- The router imports page modules **lazily**, and a page that fails to import is *reported*, not
  raised — so a broken Reports page still leaves the sidebar working and the operator able to
  navigate away.

Streamlit's built-in `st.navigation` is deliberately not used: it keys off files in a `pages/`
directory and owns routing, which would make two sources of truth for what pages exist.

---

## 6. Theme guide

Every colour comes from a `Palette`. Nothing hardcodes a hex value outside `theme/` — a test walks
the whole package and fails on a colour literal anywhere else. That is what makes "Future Custom
Themes" a data change rather than a search-and-replace across forty files.

```python
DARK = Palette(name="dark", dark=True, background="#0b0f14", ..., critical="#ff4d4f")
PALETTES = {"dark": DARK, "light": LIGHT}
```

**Adding a theme** is one `Palette` plus one registry entry. No component changes, because components
never name a colour — they ask the palette for one.

- `theme/palette.py` — the colours, plus the semantic lookups (`severity_colour`, `outcome_colour`,
  `grade_colour`) that map the engine's string vocabulary onto them without importing its enums.
- `theme/tokens.py` — spacing, radius, and type scale. Palette-independent: dark and light differ in
  colour, not in rhythm.
- `theme/styles.py` — generates the `:root` custom-property block and the component CSS. Switching
  theme is one re-render with different variables; no component knows a theme exists.

A stale or misspelled theme name falls back to dark rather than raising. It should not be the reason
an operator cannot open the tool.

---

## 7. State management guide

Streamlit re-runs the whole script on every interaction, so anything surviving a click lives in
`st.session_state`. Left alone, that is a global dictionary with hand-typed string keys, and the
first typo is a silent no-op.

**One key registry, one typed accessor.**

```python
class StateKey(StrEnum):
    CURRENT_PAGE = "rs.current_page"
    CURRENT_SCAN = "rs.current_scan"
    ...
```

`AppState` wraps *any* mutable string-keyed mapping — `st.session_state` in the app, a plain `dict`
in tests. That one indirection is why the state layer is exhaustively testable without a server.

A test exercises every mutator and then asserts that nothing outside `STATE_KEYS` was written. That
is the brief's "do not duplicate state", made checkable.

Other properties worth knowing:

- **Reads survive a stale session.** A value of the wrong shape falls back to the default rather than
  raising — a session that outlived a code change should not crash the page opened to diagnose it.
- **Toasts drain exactly once.** With Streamlit's re-run model, an undrained toast repeats on every
  interaction and reads as the app being stuck.
- **Confirmations live in state, not locals.** Streamlit discards locals between re-runs, which is
  precisely the property that would turn "confirm delete" into "delete".
- **Filters are namespaced per page inside one entry**, so per-page filters do not mean per-page keys.
- **Preferences and settings are separate.** Settings are configuration the environment could also
  supply; preferences are UI choices that never affect what a scan does.

### Live updates

Polling, per the brief — no WebSockets. One request per re-run on the configured interval, and
`should_poll()` stops it the moment the scan reaches a terminal state. A poller that keeps asking
after a scan has finished is a busy loop nobody notices until it has run on a laptop for eight hours.

ADR-014 chose SSE for browser clients; Streamlit is not the browser here — the Python process is the
client, and it re-runs on a timer regardless.

---

## 8. Developer guide

### Run it

```bash
streamlit run src/ragstrike/dashboard/app.py
```

Against a running API. To explore the interface without one:

```bash
RAGSTRIKE_DASHBOARD__TRANSPORT=demo streamlit run src/ragstrike/dashboard/app.py
```

Install the extra first if you have not: `pip install -e ".[dashboard]"`.

### Configuration

Every field is `RAGSTRIKE_DASHBOARD__<FIELD>`. Nothing raises on a bad value — a dashboard that
refuses to start because an interval was set to `"fast"` is one the operator cannot use to find out
what went wrong.

| Variable | Default | Meaning |
|---|---|---|
| `API_BASE_URL` | `http://127.0.0.1:8000/api/v1` | Where the API listens. |
| `TRANSPORT` | `http` | `http` or `demo`. |
| `REQUEST_TIMEOUT_S` | `15` | Per-request timeout. |
| `THEME` | `dark` | `dark` or `light`. |
| `LOG_LEVEL` | `INFO` | Filters the log viewer only. |
| `DEFAULT_TARGET` | — | Preselected in Scan Center. |
| `REFRESH_INTERVAL_S` | `3` | Live-scan poll interval. |
| `PLUGIN_REFRESH_INTERVAL_S` | `60` | Plugin inventory refresh. |
| `REPORT_FORMAT` | `html` | Default export format. |

### Test it

```bash
pytest tests/unit/test_dashboard_*.py tests/integration/test_dashboard_integration.py
```

Eight suites, 398 tests. The unit suites need no Streamlit server; the integration suite drives the
real Streamlit runtime through `AppTest` against the demo transport.

### The gate

```bash
lint-imports
```

Contract 3 — *Dashboard never imports the engine* — is the one that proves this phase did not cheat.

---

## 9. Extension guide

### Add a page

1. Write `pages/your_page.py` with one `render(context: PageContext) -> None`.
2. Add a `Route` to `navigation/routes.py`.

Nothing else changes. The sidebar, router, and search pick it up from the registry. A test
parametrizes over `ROUTES` and will fail if the module is missing or has no `render`.

### Add a component

Write a pure function returning HTML in `components/`, take a `Palette` if it needs colour, and
escape every interpolated value with `components.html.escape`. Export it from
`components/__init__.py`.

### Add a theme

One `Palette` in `theme/palette.py` plus its registry entry. The colour-literal test will tell you if
you missed a slot.

### Add a filter facet

One field on `FilterState` and one predicate in `services/filters.py`. Every page that passes rows
through `apply_filters` gets it.

### Add a service call

A method on the relevant service in `services/`. Pages never build requests. If a page needs data no
service exposes, the service grows a method — not the page.

---

## 10. What this phase does not do

Stated plainly, because a subsystem's limits belong next to its documentation:

- **The `/api/v1` server does not exist.** This phase built the client. Without a backend the
  dashboard runs and every page shows an honest offline state; it does not fabricate data.
- **The demo transport is not a mock of the engine.** It runs no plugins, scores nothing, and decides
  no verdicts. It replays a recorded shape. Nothing in it is evidence of anything.
- **Findings are reached through their scan**, not as a top-level searchable collection — global
  search covers reports, plugins, targets, and scan history, and a scan hit navigates to its findings.
- **`GET /config`** is called for the Settings page's engine-configuration panel and is not part of
  SDD §22.2. Until a backend serves it, the panel says so rather than implying the engine has no
  configuration.
