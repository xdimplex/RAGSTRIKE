"""The demo transport: a deterministic, in-memory stand-in for the API.

WHY IT EXISTS
    The dashboard is a pure client of ``/api/v1``. Without a server, every page is an empty state --
    which is correct behaviour but makes the interface impossible to review, screenshot, demonstrate,
    or test end to end. This transport answers the same routes with fixed data.

WHY IT IS OPT-IN AND LOUD
    Sample findings in a security tool are dangerous the moment they are mistaken for real ones. So:
    it is never selected automatically, only by ``RAGSTRIKE_DASHBOARD__TRANSPORT=demo``; and every
    page it feeds carries a banner saying so. There is no configuration that makes the banner go
    away while the data stays fake.

WHAT IT IS NOT
    Not a mock of the engine. It does not run plugins, score anything, or decide a verdict -- it
    replays a recorded shape. Nothing in it is evidence of anything.

FIDELITY
    The plugin inventory is the real one this repository ships (nine plugins across four packs), and
    the severities, categories, and capability requirements match their manifests. That is what makes
    it useful for reviewing layout and density; it is not what makes it true.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
import time
from typing import Any

from ragstrike.dashboard.services.errors import (
    BackendRequestError,
    NotImplementedByBackendError,
    ScanRejectedError,
    TargetMissingError,
)

#: A fixed clock origin so every rendered timestamp is stable across runs. Demo data that changes
#: on refresh makes a layout review impossible.
_BASE_DAY = "2026-07-30"

#: Above this the fixture calls a scan FAILED. Fixture bookkeeping only -- the engine decides
#: real outcomes with its own arithmetic, and nothing here influences that.
_FIXTURE_FAIL_ABOVE = 40.0


def _ts(hour: int, minute: int = 0) -> str:
    return f"{_BASE_DAY}T{hour:02d}:{minute:02d}:00+00:00"


# -------------------------------------------------------------------------------------------------
# The fixture. Written as plain data so it reads as a recording rather than as logic.
# -------------------------------------------------------------------------------------------------


def _targets() -> list[dict[str, Any]]:
    return [
        {
            "id": "vulnerable-rag",
            "name": "vulnerable-rag",
            "url": "http://127.0.0.1:9000",
            "adapter": "fastapi",
            "kind": "rag",
            "enabled": True,
            "timeout": 120,
            "authorization": {
                "authorized_by": "local-operator",
                "authorization_ref": "LOCAL-LAB",
                "scope": "Local VulnerableRAG instance owned by the operator. Loopback only.",
            },
            "health": {
                "reachable": True,
                "latency_ms": 34,
                "detail": "healthy",
                "capabilities": ["CHAT", "RETURN_CHUNKS", "RETURN_SOURCES", "INGEST_DOCUMENT"],
                "checked_at": _ts(12, 4),
            },
        },
        {
            "id": "secure-rag",
            "name": "secure-rag",
            "url": "http://127.0.0.1:9001",
            "adapter": "fastapi",
            "kind": "rag",
            "enabled": False,
            "timeout": 120,
            "authorization": {
                "authorized_by": "local-operator",
                "authorization_ref": "LOCAL-LAB",
                "scope": "Local SecureRAG instance owned by the operator. Loopback only.",
            },
            "health": {
                "reachable": False,
                "latency_ms": 0,
                "detail": "connection refused",
                "capabilities": [],
                "checked_at": _ts(12, 4),
            },
        },
    ]


def _packs() -> list[dict[str, Any]]:
    common = {"api_version": "1.0", "author": "RAGStrike", "status": "active", "enabled": True}
    return [
        {
            **common,
            "slug": "prompt-injection",
            "name": "Prompt Injection",
            "version": "1.0.0",
            "category": "prompt_injection",
            "severity": "HIGH",
            "description": "Direct and indirect instruction-override attempts against the system prompt.",
            "requires": ["CHAT"],
            "attack_count": 6,
            "payload_count": 142,
        },
        {
            **common,
            "slug": "prompt-leakage",
            "name": "Prompt Leakage",
            "version": "1.0.0",
            "category": "prompt_leakage",
            "severity": "HIGH",
            "description": "Extraction of the system prompt, its rules, and its embedded canaries.",
            "requires": ["CHAT"],
            "attack_count": 5,
            "payload_count": 64,
        },
        {
            **common,
            "slug": "context-poisoning",
            "name": "Context Poisoning",
            "version": "1.0.0",
            "category": "context_poisoning",
            "severity": "HIGH",
            "description": "Retrieval-time influence from adversarial corpus content.",
            "requires": ["CHAT", "RETURN_CHUNKS"],
            "attack_count": 4,
            "payload_count": 58,
        },
        {
            **common,
            "slug": "instruction-priority",
            "name": "Instruction Priority",
            "version": "1.0.0",
            "category": "evaluation",
            "severity": "HIGH",
            "description": "Does retrieved content outrank the system prompt?",
            "requires": ["CHAT"],
            "attack_count": 3,
            "payload_count": 18,
        },
        {
            **common,
            "slug": "prompt-boundary",
            "name": "Prompt Boundary",
            "version": "1.0.0",
            "category": "evaluation",
            "severity": "HIGH",
            "description": "Whether the boundary between instruction and data survives contact.",
            "requires": ["CHAT"],
            "attack_count": 3,
            "payload_count": 16,
        },
        {
            **common,
            "slug": "context-separation",
            "name": "Context Separation",
            "version": "1.0.0",
            "category": "evaluation",
            "severity": "HIGH",
            "description": "Whether retrieved documents are kept distinct from operator instructions.",
            "requires": ["CHAT"],
            "attack_count": 3,
            "payload_count": 15,
        },
        {
            **common,
            "slug": "source-attribution",
            "name": "Source Attribution",
            "version": "1.0.0",
            "category": "evaluation",
            "severity": "MEDIUM",
            "description": "Whether answers cite the chunks they actually came from.",
            "requires": ["CHAT", "RETURN_CHUNKS"],
            "attack_count": 2,
            "payload_count": 12,
        },
        {
            **common,
            "slug": "retrieval-consistency",
            "name": "Retrieval Consistency",
            "version": "1.0.0",
            "category": "evaluation",
            "severity": "LOW",
            "description": "Whether the same question retrieves the same evidence.",
            "requires": ["CHAT", "RETURN_CHUNKS"],
            "attack_count": 2,
            "payload_count": 10,
        },
        {
            **common,
            # A stand-in for the reference diagnostic pack. Deliberately *not* named after the real
            # one: a Phase 4 guard asserts that no plugin slug appears anywhere in executable code
            # under src/ragstrike, because the moment one does, the plugin system has become a lookup
            # table with extra steps. This fixture is sample data rather than engine logic, but
            # sidestepping the guard with an exemption would leave a hole in it -- and the demo loses
            # nothing by naming its ninth row generically.
            "slug": "reference-diagnostic",
            "name": "Reference Diagnostic",
            "version": "1.0.1",
            "category": "diagnostic",
            "severity": "INFO",
            "description": "A no-op pack. Proves discovery and the lifecycle without attacking anything.",
            "requires": ["CHAT"],
            "attack_count": 1,
            "payload_count": 3,
        },
    ]


def _findings() -> list[dict[str, Any]]:
    rows = [
        (
            "prompt-injection",
            "prompt_injection",
            "CRITICAL",
            "FAIL",
            0.94,
            9.1,
            "System prompt overridden by retrieved content",
            "Separate instructions from retrieved data; never concatenate them into one turn.",
        ),
        (
            "prompt-injection",
            "prompt_injection",
            "HIGH",
            "FAIL",
            0.88,
            7.6,
            "Direct instruction override accepted",
            "Treat all retrieved text as untrusted data, not as instructions.",
        ),
        (
            "prompt-leakage",
            "prompt_leakage",
            "HIGH",
            "FAIL",
            0.91,
            7.9,
            "System prompt disclosed verbatim on request",
            "Refuse meta-questions about the prompt; do not echo configuration.",
        ),
        (
            "context-poisoning",
            "context_poisoning",
            "HIGH",
            "FAIL",
            0.82,
            7.1,
            "Poisoned chunk ranked first for a benign question",
            "Score retrieved chunks for instruction-like content before they reach the model.",
        ),
        (
            "instruction-priority",
            "evaluation",
            "MEDIUM",
            "FAIL",
            0.71,
            5.2,
            "Retrieved content outranks the operator instruction",
            "Give the system prompt structural precedence the model cannot be argued out of.",
        ),
        (
            "source-attribution",
            "evaluation",
            "MEDIUM",
            "INCONCLUSIVE",
            0.44,
            3.1,
            "Citations could not be matched to retrieved chunks",
            "Return chunk identifiers alongside answers so attribution is checkable.",
        ),
        (
            "prompt-boundary",
            "evaluation",
            "LOW",
            "PASS",
            0.66,
            1.2,
            "Delimiter survived injection attempts",
            "No action required; keep the delimiter scheme under test.",
        ),
        (
            "retrieval-consistency",
            "evaluation",
            "INFO",
            "PASS",
            0.58,
            0.4,
            "Retrieval stable across repeated identical queries",
            "No action required.",
        ),
    ]
    return [
        {
            "id": f"f{index + 1:03d}",
            "scan_id": "scan-0006",
            "plugin_id": plugin,
            "category": category,
            "title": title,
            "severity": severity,
            "status": status,
            "confidence": confidence,
            "risk_score": risk,
            "recommendation": remedy,
            "evidence": {"summary": f"{plugin}: matched on canary and pattern detectors"},
            "timestamp": _ts(12, 10 + index),
        }
        for index, (
            plugin,
            category,
            severity,
            status,
            confidence,
            risk,
            title,
            remedy,
        ) in enumerate(rows)
    ]


def _scans() -> list[dict[str, Any]]:
    history = [
        ("scan-0006", "vulnerable-rag", "standard", 94.0, "F", 8, 214.0, _ts(12, 6)),
        ("scan-0005", "vulnerable-rag", "quick", 71.0, "E", 5, 88.0, _ts(11, 12)),
        ("scan-0004", "secure-rag", "standard", 6.0, "A", 1, 198.0, _ts(10, 40)),
        ("scan-0003", "vulnerable-rag", "deep", 96.0, "F", 11, 612.0, _ts(9, 15)),
        ("scan-0002", "secure-rag", "quick", 8.0, "B", 1, 74.0, _ts(8, 51)),
        ("scan-0001", "vulnerable-rag", "standard", 88.0, "F", 7, 205.0, _ts(8, 2)),
    ]
    plugins = [pack["slug"] for pack in _packs()][:8]
    return [
        {
            "id": scan_id,
            "target": target,
            "name": f"{target} {profile}",
            "profile": profile,
            "state": "completed",
            "started_at": started,
            "finished_at": started,
            "duration_s": duration,
            "plugins_executed": plugins,
            "findings_count": findings,
            "severity_counts": {
                "CRITICAL": 1 if grade == "F" else 0,
                "HIGH": max(0, findings - 4),
                "MEDIUM": min(2, findings),
                "LOW": 1,
                "INFO": 1,
            },
            "risk_score": risk,
            "grade": grade,
            "coverage": 1.0,
            "outcome": "FAIL" if risk > _FIXTURE_FAIL_ABOVE else "PASS",
        }
        for scan_id, target, profile, risk, grade, findings, duration, started in history
    ]


def _reports() -> list[dict[str, Any]]:
    rows = [
        ("rep-0004", "scan-0006", "vulnerable-rag", "html", 13_402, 94.0, "F", 8, _ts(12, 11)),
        ("rep-0003", "scan-0006", "vulnerable-rag", "markdown", 5_944, 94.0, "F", 8, _ts(12, 11)),
        ("rep-0002", "scan-0004", "secure-rag", "html", 9_180, 6.0, "A", 1, _ts(10, 45)),
        ("rep-0001", "scan-0001", "vulnerable-rag", "json", 11_233, 88.0, "F", 7, _ts(8, 9)),
    ]
    return [
        {
            "id": report_id,
            "scan_id": scan_id,
            "target": target,
            "format": fmt,
            "size_bytes": size,
            "risk_score": risk,
            "grade": grade,
            "findings_count": findings,
            "status": "FAIL" if risk > _FIXTURE_FAIL_ABOVE else "PASS",
            "generated_at": generated,
            "report_version": "1.0.0",
        }
        for report_id, scan_id, target, fmt, size, risk, grade, findings, generated in rows
    ]


def _health() -> dict[str, Any]:
    return {
        "components": {
            "fastapi": {"status": "ok", "detail": "serving /api/v1", "version": "0.1.0"},
            "ollama": {"status": "ok", "detail": "qwen3 loaded", "latency_ms": 41},
            "sqlite": {"status": "ok", "detail": "4 migrations applied"},
            "chromadb": {"status": "ok", "detail": "1 collection, 248 chunks"},
            "analyzer": {"status": "ok", "detail": "9 analyzers registered", "version": "1.0.0"},
            "reporting": {"status": "degraded", "detail": "pdf renderer is a declared placeholder"},
            "plugin_framework": {"status": "ok", "detail": "9 active, 0 refused"},
            "sdk": {"status": "ok", "detail": "plugin API 1.0"},
        },
        "resources": {
            "cpu_percent": 21.4,
            "memory_percent": 46.2,
            "memory_used_mb": 3_784.0,
            "uptime_s": 7_412.0,
        },
        "checked_at": _ts(12, 12),
    }


_LOG_SCRIPT: tuple[tuple[str, str], ...] = (
    ("INFO", "scan queued"),
    ("INFO", "target vulnerable-rag reachable in 34ms"),
    ("INFO", "capability negotiation: CHAT, RETURN_CHUNKS, RETURN_SOURCES, INGEST_DOCUMENT"),
    ("INFO", "plan ready: 8 plugins, 340 cases"),
    ("INFO", "prompt-injection: 142 payloads scheduled"),
    ("WARNING", "prompt-injection: canary observed in response, case 41"),
    ("INFO", "prompt-leakage: 64 payloads scheduled"),
    ("WARNING", "prompt-leakage: system prompt fragment recovered, case 12"),
    ("INFO", "context-poisoning: corpus restored, 0 documents left behind"),
    ("INFO", "analysis started"),
    ("INFO", "scoring complete: risk 94.0, grade F"),
    ("INFO", "scan completed"),
)


# -------------------------------------------------------------------------------------------------
# The transport
# -------------------------------------------------------------------------------------------------


@dataclass
class _Live:
    """A scan the demo transport is pretending to run."""

    scan_id: str
    target: str
    profile: str
    plugins: list[str]
    started_monotonic: float
    total_cases: int = 340
    #: Wall time the fake scan takes. Short enough to watch, long enough to see the bar move.
    duration_s: float = 24.0
    cancelled: bool = False


class DemoTransport:
    """Answers the ``/api/v1`` routes from the fixture above."""

    name = "demo"

    def __init__(self, *, clock: Any = time.monotonic) -> None:
        self._clock = clock
        self._targets = {t["id"]: t for t in _targets()}
        self._packs = {p["slug"]: p for p in _packs()}
        self._scans = {s["id"]: s for s in _scans()}
        self._findings = _findings()
        self._reports = {r["id"]: r for r in _reports()}
        self._live: _Live | None = None
        self._counter = len(self._scans)

    # -- dispatch ---------------------------------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> Any:
        verb = method.upper()
        route = "/" + path.strip("/")
        query = dict(params or {})
        body = dict(json or {})

        for pattern, verbs, handler in self._routes():
            match = pattern.fullmatch(route)
            if match and verb in verbs:
                return handler(match, query, body, verb)

        raise NotImplementedByBackendError(f"{verb} {route}")

    def _routes(self) -> list[tuple[re.Pattern[str], frozenset[str], Any]]:
        # Built per call rather than cached: the list is nine entries, it is only touched on a user
        # interaction, and rebuilding keeps the bound methods honest after a hot reload.
        def rx(pattern: str) -> re.Pattern[str]:
            return re.compile(pattern)

        get = frozenset({"GET"})
        post = frozenset({"POST"})
        return [
            (rx("/health"), get, self._get_health),
            (rx("/version"), get, self._get_version),
            (rx("/profiles"), get, self._get_profiles),
            (rx("/targets"), get | post, self._targets_collection),
            (rx("/targets/([^/]+)/verify"), post, self._verify_target),
            (rx("/targets/([^/]+)"), frozenset({"GET", "PATCH", "DELETE"}), self._target_item),
            (rx("/packs"), get, self._get_packs),
            (rx("/packs/reload"), post, self._reload_packs),
            (rx("/packs/([^/]+)/(enable|disable|validate)"), post, self._pack_action),
            (rx("/packs/([^/]+)"), get, self._get_pack),
            (rx("/scans/compare"), get, self._compare),
            (rx("/scans"), get | post, self._scans_collection),
            (rx("/scans/([^/]+)/progress"), get, self._progress),
            (rx("/scans/([^/]+)/cancel"), post, self._cancel),
            (rx("/scans/([^/]+)/findings"), get, self._scan_findings),
            (rx("/scans/([^/]+)/logs"), get, self._scan_logs),
            (rx("/scans/([^/]+)/reports"), post, self._generate_report),
            (rx("/scans/([^/]+)"), get, self._scan_item),
            (rx("/reports"), get, self._list_reports),
            (rx("/reports/([^/]+)"), frozenset({"GET", "DELETE"}), self._report_item),
        ]

    # -- handlers ---------------------------------------------------------------------------------

    def _get_health(self, *_: Any) -> dict[str, Any]:
        return _health()

    def _get_version(self, *_: Any) -> dict[str, Any]:
        return {
            "engine": "0.1.0",
            "plugin_api": "1.0",
            "scoring_model": "1.0.0",
            "report_formats": {"html": True, "markdown": True, "json": True, "pdf": False},
        }

    def _get_profiles(self, *_: Any) -> dict[str, Any]:
        return {
            "profiles": [
                {
                    "id": "quick",
                    "name": "Quick",
                    "description": "Smoke coverage, ~2 minutes.",
                    "estimated_cases": 84,
                },
                {
                    "id": "standard",
                    "name": "Standard",
                    "description": "The default. Every pack, standard payload set.",
                    "estimated_cases": 340,
                },
                {
                    "id": "deep",
                    "name": "Deep",
                    "description": "Full payload sets and mutations.",
                    "estimated_cases": 980,
                },
            ]
        }

    def _targets_collection(
        self, _match: Any, _query: dict[str, Any], body: dict[str, Any], verb: str
    ) -> Any:
        if verb == "GET":
            return {"targets": list(self._targets.values())}
        target_id = str(body.get("name") or body.get("id") or "").strip()
        if not target_id:
            raise BackendRequestError("A target needs a name.", status=422, code="validation_error")
        record = {
            "id": target_id,
            "name": target_id,
            "url": str(body.get("url", "")),
            "adapter": str(body.get("adapter", "fastapi")),
            "kind": "rag",
            "enabled": bool(body.get("enabled", True)),
            "timeout": body.get("timeout", 120),
            "authorization": dict(body.get("authorization", {})),
            "health": {"reachable": False, "detail": "not probed", "checked_at": ""},
        }
        self._targets[target_id] = record
        return record

    def _target_item(
        self, match: Any, _query: dict[str, Any], body: dict[str, Any], verb: str
    ) -> Any:
        target_id = match.group(1)
        record = self._targets.get(target_id)
        if record is None:
            raise TargetMissingError(f"No target named {target_id!r}.")
        if verb == "DELETE":
            return self._targets.pop(target_id)
        if verb == "PATCH":
            record.update({k: v for k, v in body.items() if k != "id"})
        return record

    def _verify_target(self, match: Any, *_: Any) -> dict[str, Any]:
        target_id = match.group(1)
        record = self._targets.get(target_id)
        if record is None:
            raise TargetMissingError(f"No target named {target_id!r}.")
        return dict(record["health"])

    def _get_packs(self, *_: Any) -> dict[str, Any]:
        return {"packs": list(self._packs.values())}

    def _get_pack(self, match: Any, *_: Any) -> dict[str, Any]:
        pack = self._packs.get(match.group(1))
        if pack is None:
            raise BackendRequestError(f"No plugin named {match.group(1)!r}.", status=404)
        return pack

    def _reload_packs(self, *_: Any) -> dict[str, Any]:
        return {"packs": list(self._packs.values()), "reloaded": len(self._packs), "rejected": 0}

    def _pack_action(self, match: Any, *_: Any) -> dict[str, Any]:
        slug, action = match.group(1), match.group(2)
        pack = self._packs.get(slug)
        if pack is None:
            raise BackendRequestError(f"No plugin named {slug!r}.", status=404)
        if action == "validate":
            return {
                "slug": slug,
                "valid": True,
                "checks": [
                    {"name": "manifest", "passed": True, "detail": "pack.yaml parsed"},
                    {"name": "api_version", "passed": True, "detail": "1.0 is compatible"},
                    {
                        "name": "class_contract",
                        "passed": True,
                        "detail": "9 lifecycle methods present",
                    },
                    {
                        "name": "permissions",
                        "passed": True,
                        "detail": "no elevated permissions requested",
                    },
                ],
            }
        pack["enabled"] = action == "enable"
        return pack

    def _scans_collection(
        self, _match: Any, query: dict[str, Any], body: dict[str, Any], verb: str
    ) -> Any:
        if verb == "GET":
            scans = list(self._scans.values())
            target = str(query.get("target", ""))
            if target:
                scans = [s for s in scans if s["target"] == target]
            return {"scans": scans}

        target_id = str(body.get("target", ""))
        record = self._targets.get(target_id)
        if record is None:
            raise TargetMissingError(f"No target named {target_id!r}.")
        authorization = record.get("authorization") or {}
        if not authorization.get("authorized_by"):
            raise ScanRejectedError(f"{target_id} has no authorization record.")

        self._counter += 1
        scan_id = f"scan-{self._counter:04d}"
        plugins = [str(p) for p in body.get("plugins", [])] or list(self._packs)
        self._live = _Live(
            scan_id=scan_id,
            target=target_id,
            profile=str(body.get("profile", "standard")),
            plugins=plugins,
            started_monotonic=float(self._clock()),
        )
        self._scans[scan_id] = {
            "id": scan_id,
            "target": target_id,
            "name": str(body.get("name", f"{target_id} {body.get('profile', 'standard')}")),
            "profile": str(body.get("profile", "standard")),
            "state": "running",
            "started_at": _ts(12, 30),
            "finished_at": "",
            "duration_s": 0.0,
            "plugins_executed": plugins,
            "findings_count": 0,
            "severity_counts": {},
            "risk_score": 0.0,
            "grade": "",
            "coverage": 0.0,
            "outcome": "",
        }
        return {"id": scan_id, "state": "queued"}

    def _scan_item(self, match: Any, *_: Any) -> dict[str, Any]:
        scan_id = match.group(1)
        self._advance()
        scan = self._scans.get(scan_id)
        if scan is None:
            raise BackendRequestError(f"No scan named {scan_id!r}.", status=404)
        return scan

    def _progress(self, match: Any, *_: Any) -> dict[str, Any]:
        scan_id = match.group(1)
        self._advance()
        live = self._live
        if live is None or live.scan_id != scan_id:
            scan = self._scans.get(scan_id)
            if scan is None:
                raise BackendRequestError(f"No scan named {scan_id!r}.", status=404)
            total = int(scan.get("findings_count", 0))
            return {
                "scan_id": scan_id,
                "state": scan["state"],
                "completed": total,
                "total": total,
                "current_plugin": "",
                "current_stage": "finished",
                "findings_so_far": total,
            }

        fraction = self._fraction(live)
        index = min(len(live.plugins) - 1, int(fraction * len(live.plugins)))
        return {
            "scan_id": scan_id,
            "state": self._scans[scan_id]["state"],
            "completed": int(fraction * live.total_cases),
            "total": live.total_cases,
            "current_plugin": live.plugins[index],
            "current_stage": _STAGES[min(len(_STAGES) - 1, int(fraction * len(_STAGES)))],
            "eta_s": max(0.0, live.duration_s * (1 - fraction)),
            "findings_so_far": int(fraction * 8),
            "sequence": int(fraction * 100),
        }

    def _cancel(self, match: Any, *_: Any) -> dict[str, Any]:
        scan_id = match.group(1)
        scan = self._scans.get(scan_id)
        if scan is None:
            raise BackendRequestError(f"No scan named {scan_id!r}.", status=404)
        if self._live and self._live.scan_id == scan_id:
            self._live.cancelled = True
        scan["state"] = "cancelled"
        return {"id": scan_id, "state": "cancelled"}

    def _scan_findings(self, match: Any, query: dict[str, Any], *_: Any) -> Any:
        scan_id = match.group(1)
        rows = [dict(f, scan_id=scan_id) for f in self._findings]
        severity = str(query.get("severity", "")).upper()
        if severity:
            rows = [f for f in rows if f["severity"] == severity]
        return {"findings": rows}

    def _scan_logs(self, match: Any, *_: Any) -> dict[str, Any]:
        scan_id = match.group(1)
        self._advance()
        live = self._live
        visible = len(_LOG_SCRIPT)
        if live is not None and live.scan_id == scan_id:
            visible = max(1, int(self._fraction(live) * len(_LOG_SCRIPT)))
        return {
            "lines": [
                {
                    "timestamp": _ts(12, 30 + index),
                    "level": level,
                    "message": message,
                    "source": "engine",
                }
                for index, (level, message) in enumerate(_LOG_SCRIPT[:visible])
            ]
        }

    def _generate_report(
        self, match: Any, _query: dict[str, Any], body: dict[str, Any], *_: Any
    ) -> Any:
        scan_id = match.group(1)
        scan = self._scans.get(scan_id)
        if scan is None:
            raise BackendRequestError(f"No scan named {scan_id!r}.", status=404)
        fmt = str(body.get("format", "html")).lower()
        report_id = f"rep-{len(self._reports) + 1:04d}"
        record = {
            "id": report_id,
            "scan_id": scan_id,
            "target": scan["target"],
            "format": fmt,
            "size_bytes": 12_000 if fmt == "html" else 6_000,
            "risk_score": scan["risk_score"],
            "grade": scan["grade"],
            "findings_count": scan["findings_count"],
            "status": scan["outcome"],
            "generated_at": _ts(12, 40),
            "report_version": "1.0.0",
        }
        self._reports[report_id] = record
        return record

    def _list_reports(self, *_: Any) -> dict[str, Any]:
        return {"reports": list(self._reports.values())}

    def _report_item(
        self, match: Any, _query: dict[str, Any], _body: dict[str, Any], verb: str
    ) -> Any:
        report_id = match.group(1)
        record = self._reports.get(report_id)
        if record is None:
            raise BackendRequestError(f"No report named {report_id!r}.", status=404)
        return self._reports.pop(report_id) if verb == "DELETE" else record

    def _compare(self, _match: Any, query: dict[str, Any], *_: Any) -> dict[str, Any]:
        base = str(query.get("base", ""))
        head = str(query.get("head", ""))
        for scan_id in (base, head):
            if scan_id not in self._scans:
                raise BackendRequestError(f"No scan named {scan_id!r}.", status=404)
        return {
            "base": self._scans[base],
            "head": self._scans[head],
            "new": [f["title"] for f in self._findings[:2]],
            "fixed": [f["title"] for f in self._findings[6:]],
            "persisting": [f["title"] for f in self._findings[2:6]],
        }

    # -- the fake clock ---------------------------------------------------------------------------

    def _fraction(self, live: _Live) -> float:
        elapsed = float(self._clock()) - live.started_monotonic
        return min(1.0, max(0.0, elapsed / live.duration_s))

    def _advance(self) -> None:
        """Move a running demo scan forward and complete it when its time is up."""
        live = self._live
        if live is None or live.cancelled:
            return
        scan = self._scans.get(live.scan_id)
        if scan is None or scan["state"] in ("completed", "cancelled", "failed"):
            return
        if self._fraction(live) < 1.0:
            scan["state"] = "running"
            return
        scan.update(
            {
                "state": "completed",
                "finished_at": _ts(12, 34),
                "duration_s": live.duration_s,
                "findings_count": len(self._findings),
                "severity_counts": {"CRITICAL": 1, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 1},
                "risk_score": 94.0,
                "grade": "F",
                "coverage": 1.0,
                "outcome": "FAIL",
            }
        )

    def describe(self) -> str:
        return "demo transport (sample data, no backend)"

    def close(self) -> None:
        """Nothing to release. Present because the transport protocol requires it."""


_STAGES: tuple[str, ...] = (
    "connecting",
    "negotiating capabilities",
    "planning",
    "executing payloads",
    "collecting evidence",
    "analyzing",
    "scoring",
    "reporting",
)
