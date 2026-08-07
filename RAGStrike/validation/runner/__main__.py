"""The validation runner.

    python -m validation.runner                       # everything
    python -m validation.runner --checks-only         # no scans; fast, needs no target
    python -m validation.runner --targets vulnerable-rag secure-rag

WHAT "NO MANUAL INTERVENTION" MEANS HERE
    One command, and it either produces a report or explains why it could not. It never prompts, it
    never stops on the first failure, and a target that is down degrades that target's benchmarks to
    NOT_RUN rather than abandoning the run -- because half a comparison is still worth reading.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import platform
import sys

# The harness lives beside the package it validates rather than inside it: it is a development tool,
# not a shipped feature, and Phase 14 adds no core features. That means the repository root has to
# be importable when this is run as a module from anywhere.
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validation.benchmarks.models import (  # noqa: E402
    BenchmarkResult,
    Comparison,
    ValidationSummary,
)
from validation.runner import consistency, performance, report  # noqa: E402
from validation.runner.executor import ScanRecord, evaluate, run_scan  # noqa: E402
from validation.runner.loader import all_benchmarks, load_all  # noqa: E402

DEFAULT_TARGETS = ("vulnerable-rag", "secure-rag")


def _environment(targets: list[str]) -> dict[str, str]:
    from ragstrike import PLUGIN_API_VERSION, __version__

    return {
        "RAGStrike version": __version__,
        "Plugin API version": PLUGIN_API_VERSION,
        "Python": platform.python_version(),
        "Platform": f"{platform.system()} {platform.release()}",
        "Targets": ", ".join(targets) or "none",
    }


def _run_benchmarks(
    targets: list[str],
) -> tuple[list[BenchmarkResult], list[Comparison], dict[str, int]]:
    """Scan each target once, then judge every benchmark against those scans.

    Split out of ``main`` so the entry point stays a readable sequence of phases rather than one
    function doing orchestration, scanning, evaluation, and comparison at once.
    """
    datasets = load_all()
    benchmarks = all_benchmarks(datasets)
    print(f"\nBenchmarks: {len(benchmarks)} across {len(datasets)} dataset(s)")

    records: dict[str, ScanRecord] = {}
    durations: dict[str, int] = {}
    for target in targets:
        print(f"\n  Scanning {target} ...")
        record = run_scan(target)
        records[target] = record
        durations[target] = record.duration_ms
        if record.ok:
            print(f"    {len(record.results)} plugin result(s) in {record.duration_ms}ms")
        else:
            print(f"    could not scan: {record.error}")

    results = [
        evaluate(benchmark, target, records[target])
        for benchmark in benchmarks
        for target in benchmark.targets
        if target in records
    ]

    by_id: dict[str, dict[str, BenchmarkResult]] = {}
    for result in results:
        by_id.setdefault(result.benchmark_id, {})[result.target] = result

    comparisons = [
        Comparison(
            benchmark_id=benchmark.id,
            description=benchmark.description,
            vulnerable=by_id.get(benchmark.id, {}).get("vulnerable-rag"),
            secure=by_id.get(benchmark.id, {}).get("secure-rag"),
        )
        for benchmark in benchmarks
    ]
    return results, comparisons, durations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validation.runner", description=__doc__)
    parser.add_argument(
        "--targets",
        nargs="*",
        default=list(DEFAULT_TARGETS),
        help="Target names from configs/targets.yaml. Default: the lab pair.",
    )
    parser.add_argument(
        "--checks-only",
        action="store_true",
        help="Run consistency checks and performance measurements; skip the scans.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Report directory.")
    args = parser.parse_args(argv)

    targets: list[str] = list(args.targets)
    started = datetime.now(UTC).isoformat()

    print("RAGStrike validation")
    print("=" * 78)

    # -- consistency first ------------------------------------------------------------------------
    # A benchmark mismatch caused by a broken analyzer is a confusing way to discover the analyzer
    # is broken, so the machinery is checked before anything is measured with it.
    print("\nConsistency checks")
    check_results = consistency.run_all(targets if not args.checks_only else [])
    for result in check_results:
        print(f"  {'PASS' if result.passed else 'FAIL'}  {result.name}: {result.detail}")
    consistency_summary = consistency.summarize(check_results)

    # -- benchmarks -------------------------------------------------------------------------------
    results: list[BenchmarkResult] = []
    comparisons: list[Comparison] = []
    scan_durations: dict[str, int] = {}

    if args.checks_only:
        datasets = load_all()
        print("\nBenchmarks skipped (--checks-only)")
        print(
            f"  {len(all_benchmarks(datasets))} benchmark(s) across "
            f"{len(datasets)} dataset(s) would run"
        )
    else:
        results, comparisons, scan_durations = _run_benchmarks(targets)

    summary = ValidationSummary(
        results=tuple(results),
        comparisons=tuple(comparisons),
        started_at=started,
        finished_at=datetime.now(UTC).isoformat(),
    )

    # -- performance ------------------------------------------------------------------------------
    print("\nPerformance")
    measurements = performance.measure_all(scan_durations)
    for measurement in measurements:
        print(f"  {measurement.name}: {measurement.value:.1f} {measurement.unit}")
    performance_summary = performance.summarize(measurements)

    # -- report -----------------------------------------------------------------------------------
    json_path, markdown_path = report.write_report(
        summary,
        consistency_summary,
        performance_summary,
        directory=args.output,
        environment=_environment(targets),
    )

    print("\n" + "=" * 78)
    print(f"Consistency: {consistency_summary['passed']}/{consistency_summary['total']} passed")
    if summary.total:
        print(
            f"Benchmarks:  {summary.validated} validated, {summary.mismatched} mismatched, "
            f"{summary.not_run} did not run  ({summary.pass_rate * 100:.1f}% of those that ran)"
        )
        print(f"Separating:  {summary.separating}/{len(summary.comparisons)} comparisons")
    print(f"\nReport: {markdown_path}")
    print(f"        {json_path}")

    # Exit non-zero on a real failure -- a broken check or a mismatch -- but not on NOT_RUN, which
    # is an environment gap rather than a framework defect.
    failed = consistency_summary["failed"] > 0 or summary.mismatched > 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
