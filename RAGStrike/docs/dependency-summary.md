# Dependency summary

> Every runtime dependency, why it is here, and what it would cost to remove.

---

## Runtime — core

| Package | Purpose | Replaceable? |
|---|---|---|
| `httpx` | HTTP client for target adapters | Yes, but async + sync in one API is why it was chosen |
| `pydantic` | Configuration and API boundary validation | No. Validation-at-the-boundary is an architectural commitment |
| `pydantic-settings` | Environment-variable layering | Yes, with effort |
| `pyyaml` | Config, manifests, payloads, rules, datasets | No. Everything data-driven is YAML |
| `typer` | CLI | Yes |
| `rich` | Terminal output | Yes, cosmetic |
| `aiosqlite` | Async SQLite | No, given the async engine |
| `jinja2` | Present as a transitive dependency | **Deliberately unused for report templates** — see below |
| `packaging` | Version comparison for the plugin API | No |

### Why templates use `str.Template` and not Jinja

Jinja is already installed. Report templates use `string.Template` anyway, because it understands
`$name` and nothing else. A report template is a file an operator edits, and a templating language
that can execute turns styling a report into a code-execution surface.

## Runtime — optional

| Extra | Packages | For |
|---|---|---|
| `dashboard` | `streamlit`, `pandas`, `altair` | The UI. Not needed for the CLI |
| `pdf` | `weasyprint` | Declared; the PDF renderer is not implemented |
| `openai` | `openai` | Adapter, not built |
| `langchain` | `langchain-core` | Adapter, not built |
| `llamaindex` | `llama-index-core` | Adapter, not built |

## Development

`pytest` (+`asyncio`, `cov`, `timeout`), `hypothesis`, `respx`, `black`, `ruff`, `mypy`,
`import-linter`, `bandit`, `pip-audit`, `pre-commit`, `types-pyyaml`, `mkdocs-material`.

**`import-linter` is not optional in spirit.** It enforces the dependency rule as a merge gate; a
build without it is not running the architecture's own tests.

## The lab

VulnerableRAG and SecureRAG add `fastapi`, `uvicorn`, `chromadb`, `pypdf`,
`langchain-text-splitters`, and `python-multipart`. They are separate repositories with their own
`pyproject.toml`; RAGStrike does not depend on them.

## Supply-chain posture

- **Pinned by lower bound, not upper.** `uv.lock` records exact resolved versions
- `pip-audit` runs in CI
- `bandit` runs over `src/`
- **Plugins run with full process trust.** Installing an attack pack is equivalent to installing any
  Python package. Subprocess isolation is a v2 item, and this is an accepted risk rather than an
  oversight
