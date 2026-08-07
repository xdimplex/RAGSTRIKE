# `reporters` — Reporting Engine

> **SDD reference:** [SDD §19](../../../docs/SDD.md)
> **Full documentation:** [`docs/reporting-engine.md`](../../../docs/reporting-engine.md)
> **Phase:** 11 · **Status:** implemented.

## Purpose

Transforms the standardized `Finding` objects the Analyzer Engine produces into professional
security reports.

**One model, N renderers.** Every computation happens once, in the builders; a renderer only chooses
how to present what it is given. That guarantees the HTML, JSON, and Markdown outputs agree about
the same scan, and makes adding a format a change that touches no arithmetic anywhere.

It never talks to a plugin, and it never renders a UI.

## Layout

```
reporters/
├── models/            ReportModel and its ten sections; format-independent
├── base/              BaseRenderer contract, StoredReport, ports
├── builders/          ReportBuilder + ExecutiveSummaryBuilder — all computation
├── statistics/        StatisticsBuilder
├── timeline/          TimelineBuilder
├── charts/            ChartDataBuilder — data, never images
├── validators/        ReportValidator
├── engine/            ReportEngine + ReportRegistry
├── exporters/         ExportManager — the only component that does I/O
├── templates/         TemplateManager + AssetManager
├── html/ json/ markdown/ pdf/    one renderer each
├── service.py         the five-operation internal API
└── config.py          builds a service from configs/reporting/
```

> The phase brief names this package `reporting/`. It is built here instead — the Phase 1 scaffold,
> the name in the layer contract, and the home SDD §19 designates. A second package alongside would
> have left two reporting packages and an orphaned scaffold.

## Layer position

Its own row, **above `analyzers`** and **below `database`**.

Phase 1 listed reporters and analyzers as siblings, and import-linter treats same-row modules as
mutually independent — which forbade the one dependency this package exists to have. The dependency
is real and one-directional: reporting reads findings, and the analyzer must never know a report
exists.

Persistence is a port (`ReportRepository`) that the database layer implements, so report generation
stays a pure transformation, testable with no database attached.

## Formats

| Format | State |
|---|---|
| `html` | Self-contained, inlined CSS, everything escaped |
| `json` | The complete model |
| `markdown` | Truncates past a configured limit, and says so |
| `pdf` | **Declared placeholder — raises rather than producing anything** |

Adding a format is a class plus a registration. Nothing in the engine names a format, and a test
enforces that.

## This folder must NEVER contain

- An import of `ragstrike.database` — including from inside a function. grimp reads the whole AST,
  and a deferred import is the same dependency, just harder to see. This caught a real violation
  during Phase 11.
- An import of any pack or plugin.
- Computation inside a renderer. If two formats would need the same number, it belongs in the model.
- An unescaped value in HTML output. Report content is attacker-influenced by construction.
- A remote asset reference. A report that phones home when opened is a tracking pixel.
- A templating engine that can evaluate expressions. Templates are formatted, never evaluated.
