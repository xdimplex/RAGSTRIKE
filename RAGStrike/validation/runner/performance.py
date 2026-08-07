"""Performance measurements.

WHAT THESE NUMBERS ARE
    Single-sample measurements from one machine, taken to establish an order of magnitude and to
    catch a regression that changes one. They are **not** a benchmark suite in the competitive sense:
    there is no warm-up, no repetition, and no statistical treatment, because the useful signal here
    is "startup went from 2s to 40s", not "startup is 1.9% slower".

    Stating that plainly matters. A table of precise-looking milliseconds invites comparison it
    cannot support.

WHAT IS AND IS NOT ATTRIBUTABLE TO RAGSTRIKE
    Scan duration is dominated by the target's model. On a local 4B model on CPU, a single payload
    can take seconds, and the framework's own overhead is lost in the noise. The measurements
    separate framework time (discovery, analysis, reporting) from target time (the scan) for exactly
    this reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


@dataclass(frozen=True, slots=True)
class Measurement:
    name: str
    value: float
    unit: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 3),
            "unit": self.unit,
            "note": self.note,
        }


def measure_startup() -> Measurement:
    """Cold import of the CLI in a fresh interpreter.

    A subprocess rather than an in-process timer: by the time this module runs, ragstrike is already
    imported, and re-importing would measure a warm module cache rather than what an operator waits
    for.
    """
    started = time.perf_counter()
    subprocess.run(
        [sys.executable, "-c", "import ragstrike.cli.main"],
        check=False,
        capture_output=True,
    )
    return Measurement(
        "Startup time", (time.perf_counter() - started) * 1000, "ms", "cold import, fresh process"
    )


def measure_plugin_discovery() -> Measurement:
    from ragstrike import PLUGIN_API_VERSION
    from ragstrike.core.config.loader import REPO_ROOT, load_settings
    from ragstrike.plugins.registry.plugin_registry import PluginRegistry

    settings = load_settings()
    started = time.perf_counter()
    health = PluginRegistry(
        settings.plugins,
        api_version=PLUGIN_API_VERSION,
        plugin_config_path=REPO_ROOT / "configs" / "plugins.yaml",
    ).discover()
    elapsed = (time.perf_counter() - started) * 1000
    return Measurement(
        "Plugin discovery time", elapsed, "ms", f"{len(health.active)} plugin(s), first import"
    )


def measure_analyzer() -> Measurement:
    """Analysis of a synthetic observation set. Arithmetic only -- no model call by design."""
    from datetime import datetime as dt

    from ragstrike.analyzers.base.finding import Finding
    from ragstrike.models.values.enums import PluginOutcome, Severity
    from ragstrike.reporters.builders.report_builder import ReportContext
    from ragstrike.reporters.engine.report_engine import ReportEngine

    findings = [
        Finding(
            id=f"f{i}",
            scan_id="s1",
            plugin_id="prompt-injection",
            category="prompt_injection",
            status=PluginOutcome.FAIL,
            severity=Severity.HIGH,
            confidence=0.9,
            risk_score=7.2,
            timestamp=dt.now(UTC),
            analyzer_version="1.0.0",
        )
        for i in range(50)
    ]
    engine = ReportEngine()
    started = time.perf_counter()
    engine.generate(findings, ReportContext(scan_id="s1"))
    return Measurement(
        "Analyzer/report-model duration",
        (time.perf_counter() - started) * 1000,
        "ms",
        "50 findings, deterministic arithmetic",
    )


def measure_report_generation() -> Measurement:
    from datetime import datetime as dt

    from ragstrike.analyzers.base.finding import Finding
    from ragstrike.models.values.enums import PluginOutcome, Severity
    from ragstrike.reporters.builders.report_builder import ReportContext
    from ragstrike.reporters.engine.report_engine import ReportEngine

    findings = [
        Finding(
            id=f"f{i}",
            scan_id="s1",
            plugin_id="prompt-injection",
            category="prompt_injection",
            status=PluginOutcome.FAIL,
            severity=Severity.HIGH,
            confidence=0.9,
            risk_score=7.2,
            timestamp=dt.now(UTC),
            analyzer_version="1.0.0",
        )
        for i in range(50)
    ]
    engine = ReportEngine()
    generated = engine.generate(findings, ReportContext(scan_id="s1"))
    started = time.perf_counter()
    rendered = engine.render_all(generated)
    elapsed = (time.perf_counter() - started) * 1000
    total = sum(len(body) for body in rendered.values())
    return Measurement(
        "Report generation time",
        elapsed,
        "ms",
        f"{len(rendered)} format(s), {total:,}B total",
    )


def measure_dashboard_load() -> Measurement:
    """Time to build the dashboard's service container and resolve every page.

    Not a browser render. The Streamlit server's paint time is Streamlit's business; what belongs to
    this project is how long its own wiring takes.
    """
    from ragstrike.dashboard.navigation.router import resolve
    from ragstrike.dashboard.navigation.routes import ROUTES
    from ragstrike.dashboard.services import build_services_with
    from ragstrike.dashboard.services.demo import DemoTransport

    started = time.perf_counter()
    build_services_with(DemoTransport())
    for route in ROUTES:
        resolve(route.id)
    return Measurement(
        "Dashboard wiring time",
        (time.perf_counter() - started) * 1000,
        "ms",
        f"{len(ROUTES)} page module(s) imported",
    )


def measure_memory() -> Measurement:
    """Peak resident memory of this process.

    ``psutil`` is not a dependency of this project, so this falls back to the standard library and
    says so rather than reporting a number it did not measure.
    """
    try:
        import resource  # POSIX only

        peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return Measurement("Peak memory", peak_kb / 1024, "MB", "resource.getrusage")
    except ImportError:
        pass

    try:
        import ctypes
        import ctypes.wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.wintypes.DWORD),
                ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        # argtypes matter here: without them ctypes truncates the HANDLE on 64-bit Windows, the
        # call fails, and the measurement silently reports zero. A zero that looks like a
        # measurement is worse than an honest "not measurable".
        get_process = ctypes.windll.kernel32.GetProcessHandle if False else ctypes.windll.kernel32.GetCurrentProcess  # type: ignore[attr-defined]
        get_process.restype = ctypes.c_void_p
        get_info = ctypes.windll.psapi.GetProcessMemoryInfo  # type: ignore[attr-defined]
        get_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.wintypes.DWORD]
        get_info.restype = ctypes.wintypes.BOOL
        if not get_info(get_process(), ctypes.byref(counters), counters.cb):
            return Measurement("Peak memory", 0.0, "MB", "GetProcessMemoryInfo failed")
        return Measurement(
            "Peak memory", counters.PeakWorkingSetSize / 1024 / 1024, "MB", "GetProcessMemoryInfo"
        )
    except Exception:
        return Measurement("Peak memory", 0.0, "MB", "not measurable without psutil")


def measure_cpu() -> Measurement:
    """CPU time consumed by this process so far. Not a percentage -- a total."""
    import os

    times = os.times()
    return Measurement(
        "CPU time", times.user + times.system, "s", "user+system for the validation process"
    )


def measure_database(path: Path | None = None) -> Measurement:
    from ragstrike.core.config.loader import load_settings

    database_path = path or load_settings().storage.database_path
    if not database_path.exists():
        return Measurement("Database size", 0.0, "MB", "no database yet")
    size = database_path.stat().st_size / 1024 / 1024
    return Measurement("Database size", size, "MB", str(database_path))


def measure_all(scan_durations: dict[str, int] | None = None) -> list[Measurement]:
    """Every measurement. ``scan_durations`` comes from the benchmark run, if one happened."""
    measurements = [
        measure_startup(),
        measure_plugin_discovery(),
        measure_analyzer(),
        measure_report_generation(),
        measure_dashboard_load(),
        measure_memory(),
        measure_cpu(),
        measure_database(),
    ]

    for target, duration in (scan_durations or {}).items():
        measurements.append(
            Measurement(
                f"Scan duration ({target})",
                duration,
                "ms",
                "dominated by the target's model, not by framework overhead",
            )
        )
    if not scan_durations:
        measurements.append(Measurement("Scan duration", 0.0, "ms", "no scan in this run"))

    return measurements


def summarize(measurements: list[Measurement]) -> dict[str, Any]:
    return {
        "measured_at": datetime.now(UTC).isoformat(),
        "caveat": (
            "Single-sample measurements from one machine. Useful for order of magnitude and for "
            "catching a regression that changes one; not for fine-grained comparison."
        ),
        "measurements": [m.to_dict() for m in measurements],
    }
