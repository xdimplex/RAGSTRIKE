"""Validation reporting: JSON for machines, Markdown for people.

WHY BOTH
    The JSON is what a CI job asserts on. The Markdown is what someone reads when it fails. Producing
    only one of them means either the pipeline parses prose or the human reads a nested object.

WHY THE MARKDOWN LEADS WITH WHAT DID NOT WORK
    A validation report that opens with a pass rate invites the reader to stop there. The mismatches
    and the benchmarks that did not run are the reason to read it at all, so they come first.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from validation.benchmarks.models import Status, ValidationSummary

REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"

_STATUS_MARK = {
    Status.VALIDATED: "PASS",
    Status.MISMATCH: "FAIL",
    Status.NOT_RUN: "SKIP",
    Status.UNDETERMINED: "----",
}


def write_json(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    return path


def _table(rows: list[list[str]], headers: list[str]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def render_markdown(
    summary: ValidationSummary,
    consistency: dict[str, Any],
    performance: dict[str, Any],
    *,
    environment: dict[str, str] | None = None,
) -> str:
    parts: list[str] = [
        "# RAGStrike validation report",
        "",
        f"> Generated {datetime.now(UTC).isoformat()}",
        "",
    ]

    if environment:
        parts += [
            "## Environment",
            "",
            _table([[k, v] for k, v in environment.items()], ["Item", "Value"]),
            "",
        ]

    # -- what did not work, first -------------------------------------------------------------
    mismatches = [r for r in summary.results if r.status is Status.MISMATCH]
    not_run = [r for r in summary.results if r.status is Status.NOT_RUN]
    undetermined = [r for r in summary.results if r.status is Status.UNDETERMINED]
    failed_checks = [c for c in consistency.get("checks", []) if c["status"] != "PASS"]

    parts += ["## What did not pass", ""]
    if not (mismatches or not_run or undetermined or failed_checks):
        parts += ["Nothing. Every consistency check passed and every benchmark matched.", ""]
    else:
        if failed_checks:
            parts += [
                "### Consistency checks",
                "",
                _table(
                    [[c["name"], c["detail"]] for c in failed_checks],
                    ["Check", "Detail"],
                ),
                "",
            ]
        if mismatches:
            parts += [
                "### Benchmark mismatches",
                "",
                "The framework did not behave as the dataset says it should.",
                "",
                _table(
                    [
                        [r.benchmark_id, r.target, r.expected.value, r.observed.value, r.detail]
                        for r in mismatches
                    ],
                    ["ID", "Target", "Expected", "Observed", "Detail"],
                ),
                "",
            ]
        if undetermined:
            parts += [
                "### Undetermined",
                "",
                "The framework declined to claim a result. Weaker evidence than a wrong claim, and "
                "reported separately from a mismatch for that reason.",
                "",
                _table(
                    [[r.benchmark_id, r.target, r.expected.value, r.detail] for r in undetermined],
                    ["ID", "Target", "Expected", "Detail"],
                ),
                "",
            ]
        if not_run:
            parts += [
                "### Did not run",
                "",
                "Environment gaps, not framework defects. Excluded from the pass rate.",
                "",
                _table(
                    [[r.benchmark_id, r.target, r.detail] for r in not_run],
                    ["ID", "Target", "Reason"],
                ),
                "",
            ]

    # -- totals ---------------------------------------------------------------------------------
    parts += [
        "## Totals",
        "",
        _table(
            [
                ["Benchmarks", str(summary.total)],
                ["Validated", str(summary.validated)],
                ["Mismatched", str(summary.mismatched)],
                ["Did not run", str(summary.not_run)],
                ["Pass rate (of those that ran)", f"{summary.pass_rate * 100:.1f}%"],
                ["Comparisons", str(len(summary.comparisons))],
                ["Separating the two targets", str(summary.separating)],
            ],
            ["Metric", "Value"],
        ),
        "",
    ]

    # -- comparison -----------------------------------------------------------------------------
    if summary.comparisons:
        parts += [
            "## VulnerableRAG vs SecureRAG",
            "",
            "`Separates` is the column that matters: a benchmark on which both halves agree has "
            "validated nothing about the difference between them.",
            "",
            _table(
                [
                    [
                        c.benchmark_id,
                        c.vulnerable.observed.value if c.vulnerable else "--",
                        c.secure.observed.value if c.secure else "--",
                        c.difference,
                        "yes" if c.separates else "no",
                        _STATUS_MARK.get(c.status, "?"),
                    ]
                    for c in summary.comparisons
                ],
                ["ID", "Vulnerable", "Secure", "Difference", "Separates", "Status"],
            ),
            "",
        ]

    # -- all results ----------------------------------------------------------------------------
    if summary.results:
        parts += [
            "## All benchmarks",
            "",
            _table(
                [
                    [
                        r.benchmark_id,
                        r.target,
                        ", ".join(r.plugins_executed) or "--",
                        r.expected.value,
                        r.observed.value,
                        _STATUS_MARK.get(r.status, "?"),
                        f"{r.execution_ms}",
                        r.timestamp,
                    ]
                    for r in summary.results
                ],
                ["ID", "Target", "Plugins", "Expected", "Observed", "Status", "ms", "Timestamp"],
            ),
            "",
        ]

    # -- consistency ----------------------------------------------------------------------------
    parts += [
        "## Consistency checks",
        "",
        _table(
            [
                [c["name"], c["status"], c["detail"], str(c["duration_ms"])]
                for c in consistency.get("checks", [])
            ],
            ["Check", "Status", "Detail", "ms"],
        ),
        "",
    ]

    # -- performance ----------------------------------------------------------------------------
    parts += [
        "## Performance",
        "",
        f"> {performance.get('caveat', '')}",
        "",
        _table(
            [
                [m["name"], f"{m['value']}", m["unit"], m["note"]]
                for m in performance.get("measurements", [])
            ],
            ["Measurement", "Value", "Unit", "Note"],
        ),
        "",
    ]

    return "\n".join(parts)


def write_report(
    summary: ValidationSummary,
    consistency: dict[str, Any],
    performance: dict[str, Any],
    *,
    directory: Path | None = None,
    environment: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    """Write both artifacts and return their paths."""
    root = directory or REPORT_DIR
    payload = {
        "validation": summary.to_dict(),
        "consistency": consistency,
        "performance": performance,
        "environment": environment or {},
    }
    json_path = write_json(payload, root / "validation-summary.json")
    markdown_path = root / "validation-summary.md"
    markdown_path.write_text(
        render_markdown(summary, consistency, performance, environment=environment),
        encoding="utf-8",
    )
    return json_path, markdown_path
