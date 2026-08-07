# Examples

Five worked examples, in the order they are worth reading.

| Directory | Shows | Needs a running target? |
|---|---|---|
| [`basic_scan/`](basic_scan/) | Scanning one target from the CLI and from Python | Yes |
| [`comparison_scan/`](comparison_scan/) | The differential: VulnerableRAG against SecureRAG | Yes, both |
| [`custom_plugin/`](custom_plugin/) | Writing an attack pack. **Zero edits to the framework** | No |
| [`custom_target/`](custom_target/) | Pointing RAGStrike at a RAG application that is not the lab | Depends |
| [`example_reports/`](example_reports/) | What a generated report actually looks like | No |

## Before any of these

```bash
pip install -e ".[dashboard,dev]"
python -m validation.runner --checks-only     # expect 10/10
```

If that reports ten passing checks, the installation is sound and every example below will run.

## A note on timing

Scan duration is dominated by the **target's** model, not by RAGStrike. On a local 4B model on CPU,
a single payload takes roughly 5–40 seconds, so a full scan is measured in hours. Every example that
scans says how long it takes and how to bound it.

That is a property of the lab hardware, not of the framework: RAGStrike's own overhead —
discovery, analysis, scoring, reporting — is milliseconds. See
[`../docs/validation-results.md`](../docs/validation-results.md) for the measurements.
