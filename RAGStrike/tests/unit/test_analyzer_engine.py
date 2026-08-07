"""Evidence, recommendation, validation, registry, and end-to-end engine tests.

The claim under test throughout: the engine converts raw plugin results into findings **without
knowing anything about any plugin**, and the analyzer -- not the plugin -- authors the verdict.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ragstrike.analyzers.base.analyzer import BaseAnalyzer
from ragstrike.analyzers.base.finding import Finding
from ragstrike.analyzers.base.observation import Observation
from ragstrike.analyzers.config import build_engine
from ragstrike.analyzers.engine import (
    ANALYZER_VERSION,
    AnalyzerEngine,
    StandardAnalyzer,
    outcome_counts,
)
from ragstrike.analyzers.evidence.evidence_engine import EvidenceEngine
from ragstrike.analyzers.recommendations.recommendation_engine import (
    RecommendationCatalog,
    RecommendationEngine,
    load_recommendation_catalog,
)
from ragstrike.analyzers.registry.analyzer_registry import AnalyzerRegistry
from ragstrike.analyzers.validators.validation_engine import ValidationEngine
from ragstrike.models.entities.scan import PluginResult
from ragstrike.models.values.enums import PluginOutcome, Severity

SHIPPED = Path("configs") / "analyzer"


def observation(**kwargs) -> Observation:
    defaults = {
        "plugin_id": "prompt-injection",
        "scan_id": "s1",
        "category": "prompt_injection",
        "reported_status": PluginOutcome.FAIL,
        "reported_confidence": 0.9,
        "evidence": {
            "confidence": 0.9,
            "results": [{"status": "FAIL", "evidence": {"signals": [{"detector": "canary"}]}}],
        },
    }
    defaults.update(kwargs)
    return Observation(**defaults)


# -- evidence normalization -------------------------------------------------------------------------


def test_evidence_is_normalized_into_one_shape() -> None:
    normalized = EvidenceEngine().normalize(observation())

    assert normalized.signals
    assert normalized.cases
    assert normalized.timing


def test_sources_are_collected_from_whichever_key_a_pack_used() -> None:
    """Packs were written independently; the engine translates rather than demanding one spelling."""
    engine = EvidenceEngine()

    from_retrieved = engine.normalize(
        observation(evidence={"retrieved_sources": ["a.pdf"], "results": []})
    )
    from_sources = engine.normalize(observation(evidence={"sources": ["a.pdf"], "results": []}))

    assert from_retrieved.sources == ("a.pdf",)
    assert from_sources.sources == ("a.pdf",)


def test_sources_are_deduplicated_in_first_seen_order() -> None:
    normalized = EvidenceEngine().normalize(
        observation(evidence={"sources": ["b.pdf", "a.pdf", "b.pdf"], "results": []})
    )

    assert normalized.sources == ("b.pdf", "a.pdf")


def test_chunk_dicts_are_reduced_to_their_identifying_field() -> None:
    normalized = EvidenceEngine().normalize(
        observation(evidence={"sources": [{"source_name": "a.pdf"}], "results": []})
    )

    assert normalized.sources == ("a.pdf",)


def test_unrecognised_evidence_is_preserved_verbatim() -> None:
    """Nothing is discarded just because this engine did not anticipate it."""
    normalized = EvidenceEngine().normalize(
        observation(evidence={"something_new": {"a": 1}, "results": []})
    )

    assert normalized.structured["something_new"] == {"a": 1}


def test_normalization_never_invents_a_section() -> None:
    """An absent section stays absent rather than being defaulted to something plausible."""
    normalized = EvidenceEngine().normalize(observation(evidence={}))

    assert normalized.sources == ()
    assert normalized.is_empty


def test_signals_are_collected_from_both_shapes_in_use() -> None:
    engine = EvidenceEngine()

    accumulator = engine.normalize(
        observation(evidence={"signals": {"count": 1, "items": [{"d": 1}]}, "results": []})
    )
    per_case = engine.normalize(
        observation(evidence={"results": [{"evidence": {"signals": [{"d": 2}]}}]})
    )

    assert accumulator.signals
    assert per_case.signals


def test_normalized_evidence_is_json_serializable() -> None:
    json.dumps(EvidenceEngine().normalize(observation()).to_dict())


# -- recommendations ------------------------------------------------------------------------------------


def test_a_pack_supplied_recommendation_wins() -> None:
    """A pack that shipped advice for its own failure modes knows more about them than a
    severity-keyed default."""
    engine = RecommendationEngine(load_recommendation_catalog(SHIPPED / "recommendations.yaml"))

    entry = engine.recommend(
        plugin_id="prompt-injection",
        category="prompt_injection",
        severity=Severity.HIGH,
        plugin_supplied="Enforce an instruction hierarchy",
    )

    assert entry.title == "Enforce an instruction hierarchy"
    assert entry.scope == "plugin-supplied"


def test_lookup_falls_back_from_category_to_severity() -> None:
    catalog = RecommendationCatalog.from_mapping(
        {"by_severity": {"HIGH": {"title": "severity advice"}}}
    )

    entry = RecommendationEngine(catalog).recommend(
        plugin_id="unknown", category="unknown", severity=Severity.HIGH
    )

    assert entry.title == "severity advice"


def test_plugin_scope_beats_category_scope() -> None:
    catalog = RecommendationCatalog.from_mapping(
        {
            "by_plugin": {"p": {"title": "plugin advice"}},
            "by_category": {"c": {"title": "category advice"}},
        }
    )

    entry = RecommendationEngine(catalog).recommend(
        plugin_id="p", category="c", severity=Severity.HIGH
    )

    assert entry.title == "plugin advice"


def test_an_unmatched_lookup_still_returns_something_actionable() -> None:
    entry = RecommendationEngine().recommend(plugin_id="x", category="y", severity=Severity.LOW)

    assert entry.title
    assert "recommendations.yaml" in entry.remediation


def test_the_shipped_catalog_covers_every_severity() -> None:
    catalog = load_recommendation_catalog(SHIPPED / "recommendations.yaml")

    for severity in Severity:
        assert severity.value in catalog.by_severity, f"no entry for {severity.value}"


def test_recommendations_are_deterministic() -> None:
    """Retrieved, never generated -- so identical inputs give identical advice, every time."""
    engine = RecommendationEngine(load_recommendation_catalog(SHIPPED / "recommendations.yaml"))
    args = {"plugin_id": "x", "category": "prompt_injection", "severity": Severity.HIGH}

    assert engine.recommend(**args) == engine.recommend(**args)


# -- validation ------------------------------------------------------------------------------------------


def test_a_valid_observation_passes() -> None:
    assert ValidationEngine().validate(observation()).valid


def test_a_missing_plugin_id_is_rejected() -> None:
    report = ValidationEngine().validate(observation(plugin_id=""))

    assert not report.valid
    assert any(e.field == "plugin_id" for e in report.errors)


def test_a_missing_scan_id_is_rejected() -> None:
    assert not ValidationEngine().validate(observation(scan_id="")).valid


def test_a_missing_category_is_a_warning_not_a_rejection() -> None:
    """Category-scoped rules will not match, which is a coverage gap rather than an error."""
    report = ValidationEngine().validate(observation(category=""))

    assert report.valid
    assert any(w.field == "category" for w in report.warnings)


def test_an_out_of_range_confidence_warns_and_is_clamped_later() -> None:
    report = ValidationEngine().validate(observation(reported_confidence=5.0))

    assert report.valid
    assert any(w.field == "reported_confidence" for w in report.warnings)


def test_every_rejection_explains_itself() -> None:
    """A malformed observation silently dropped reads exactly like a clean result."""
    report = ValidationEngine().validate(observation(plugin_id="", scan_id=""))

    assert all(e.field and e.reason for e in report.errors)


def test_validate_all_returns_both_halves() -> None:
    """Filtering silently would make a validator that drops its input indistinguishable from one
    that found nothing wrong."""
    accepted, rejected = ValidationEngine().validate_all([observation(), observation(plugin_id="")])

    assert len(accepted) == 1
    assert len(rejected) == 1


# -- registry ----------------------------------------------------------------------------------------------


class Specialist(BaseAnalyzer):
    name = "specialist"
    handles = ("prompt_injection",)

    def analyze(self, observation: Observation) -> Finding:  # pragma: no cover - not exercised
        raise NotImplementedError


class Generalist(BaseAnalyzer):
    name = "generalist"
    handles = ()

    def analyze(self, observation: Observation) -> Finding:  # pragma: no cover - not exercised
        raise NotImplementedError


def test_an_analyzer_registers_and_resolves() -> None:
    registry = AnalyzerRegistry()
    registry.register(Generalist())

    assert registry.for_category("anything").name == "generalist"


def test_a_specialist_beats_a_generalist() -> None:
    registry = AnalyzerRegistry()
    registry.register(Generalist())
    registry.register(Specialist())

    assert registry.for_category("prompt_injection").name == "specialist"
    assert registry.for_category("other").name == "generalist"


def test_a_duplicate_name_is_refused() -> None:
    """Silently overwriting would make "which analyzer ran" depend on registration order, and the
    symptom would be subtly wrong findings rather than an error anyone notices."""
    registry = AnalyzerRegistry()
    registry.register(Generalist())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(Generalist())


def test_a_duplicate_can_be_replaced_deliberately() -> None:
    registry = AnalyzerRegistry()
    registry.register(Generalist())

    registry.register(Generalist(), replace=True)

    assert len(registry) == 1


def test_an_unnamed_analyzer_is_refused() -> None:
    class Nameless(BaseAnalyzer):
        name = ""

        def analyze(self, observation: Observation) -> Finding:  # pragma: no cover
            raise NotImplementedError

    with pytest.raises(ValueError, match="non-empty name"):
        AnalyzerRegistry().register(Nameless())


def test_an_empty_registry_resolves_to_nothing() -> None:
    assert AnalyzerRegistry().for_category("x") is None


def test_the_decorator_registers_at_import_time() -> None:
    registry = AnalyzerRegistry()

    @registry.analyzer
    class Decorated(BaseAnalyzer):
        name = "decorated"

        def analyze(self, observation: Observation) -> Finding:  # pragma: no cover
            raise NotImplementedError

    assert "decorated" in registry


def test_registry_listing_is_deterministic() -> None:
    registry = AnalyzerRegistry()
    registry.register(Specialist())
    registry.register(Generalist())

    assert registry.names() == ["generalist", "specialist"]


# -- the engine, end to end ---------------------------------------------------------------------------------------


def test_the_engine_produces_a_finding_with_every_required_field() -> None:
    finding = AnalyzerEngine().analyze_one(observation())

    assert finding is not None
    for attribute in (
        "id",
        "scan_id",
        "plugin_id",
        "category",
        "status",
        "severity",
        "confidence",
        "risk_score",
        "evidence",
        "recommendation",
        "references",
        "timestamp",
        "notes",
    ):
        assert hasattr(finding, attribute), f"finding missing {attribute}"


def test_an_invalid_observation_produces_no_finding() -> None:
    assert AnalyzerEngine().analyze_one(observation(plugin_id="")) is None


def test_rejected_observations_are_reported_not_dropped() -> None:
    """A scan that silently analyzed eight of ten plugins looks exactly like one that analyzed all
    ten."""
    report = AnalyzerEngine().analyze([observation(), observation(plugin_id="")])

    assert len(report.findings) == 1
    assert len(report.rejected) == 1


def test_the_analyzer_authors_the_verdict_not_the_plugin() -> None:
    """The claim the whole phase rests on, end to end: a plugin reporting FAIL with no evidence is
    graded INCONCLUSIVE, with the disagreement recorded."""
    engine, _ = build_engine(SHIPPED)

    finding = engine.analyze_one(observation(reported_status=PluginOutcome.FAIL, evidence={}))

    assert finding is not None
    assert finding.status is PluginOutcome.INCONCLUSIVE
    assert finding.metadata["plugin_reported_status"] == PluginOutcome.FAIL.value
    assert finding.metadata["overrode_plugin"] is True


def test_a_finding_records_which_rules_produced_it() -> None:
    """A verdict nobody can trace is one nobody can argue with."""
    engine, _ = build_engine(SHIPPED)

    finding = engine.analyze_one(observation())

    assert finding is not None
    assert finding.metadata["matched_rules"]
    assert finding.notes


def test_every_finding_carries_the_analyzer_version() -> None:
    finding = AnalyzerEngine().analyze_one(observation())

    assert finding is not None
    assert finding.analyzer_version == ANALYZER_VERSION


def test_the_engine_needs_no_knowledge_of_any_plugin() -> None:
    """A category nobody anticipated still produces a finding."""
    engine, _ = build_engine(SHIPPED)

    finding = engine.analyze_one(observation(category="a_pack_from_2027", plugin_id="future"))

    assert finding is not None
    assert finding.status is PluginOutcome.FAIL


def test_an_observation_is_built_from_a_stored_plugin_result() -> None:
    """The bridge that makes "no plugin changes" true: Observation is derived from the entity the
    packs already write."""
    result = PluginResult(
        id="r1",
        scan_id="s1",
        plugin_slug="prompt-injection",
        plugin_version="1.0.0",
        outcome=PluginOutcome.FAIL,
        summary="1/4 payloads returned FAIL",
        evidence={"confidence": 0.9, "results": [{"status": "FAIL", "evidence": {}}]},
        elapsed_ms=120,
    )

    observation = Observation.from_plugin_result(result, category="prompt_injection")

    assert observation.plugin_id == "prompt-injection"
    assert observation.reported_confidence == 0.9
    assert observation.case_results


def test_a_non_numeric_stored_confidence_does_not_break_analysis() -> None:
    result = PluginResult(
        id="r1",
        scan_id="s1",
        plugin_slug="p",
        plugin_version="1.0.0",
        outcome=PluginOutcome.FAIL,
        evidence={"confidence": "very sure"},
    )

    assert Observation.from_plugin_result(result).reported_confidence == 0.0


def test_the_report_exposes_structured_objects_only() -> None:
    """The interface for the future Reporting Engine -- no HTML, no PDF, no formatting decisions."""
    report = AnalyzerEngine().analyze([observation()])

    payload = report.to_dict()

    json.dumps(payload)
    assert "findings" in payload
    assert "score" in payload


def test_coverage_distinguishes_undetermined_from_clean() -> None:
    """A scan where six of ten were inconclusive is a different statement from one where all ten
    reached a verdict."""
    engine, _ = build_engine(SHIPPED)

    report = engine.analyze(
        [
            observation(),
            observation(plugin_id="p2", reported_status=PluginOutcome.FAIL, evidence={}),
        ]
    )

    assert report.coverage == 0.5


def test_outcome_counts_include_every_status() -> None:
    """A missing key forces every consumer to write .get(status, 0), and one that forgets shows a
    blank where a zero belongs."""
    counts = outcome_counts([AnalyzerEngine().analyze_one(observation())])

    assert set(counts) == {o.value for o in PluginOutcome}


def test_a_custom_analyzer_can_be_registered_without_engine_changes() -> None:
    class Custom(StandardAnalyzer):
        name = "custom"
        handles = ("prompt_injection",)

    registry = AnalyzerRegistry()
    registry.register(Custom())

    finding = AnalyzerEngine(registry=registry).analyze_one(observation())

    assert finding is not None


# -- configuration ---------------------------------------------------------------------------------------------------


def test_the_shipped_configuration_loads_completely() -> None:
    _, report = build_engine(SHIPPED)

    assert report.fully_configured, f"missing={report.missing} skipped={report.skipped_rules}"


def test_a_missing_config_directory_degrades_rather_than_aborting(tmp_path: Path) -> None:
    """A tool that refuses to analyze because one YAML file is absent is one that does not get
    run -- but the fallback is reported, never hidden."""
    engine, report = build_engine(tmp_path)

    assert report.missing
    assert engine.analyze_one(observation()) is not None


def test_building_an_engine_does_not_mutate_global_state() -> None:
    from ragstrike.analyzers.registry.analyzer_registry import registry as global_registry

    before = len(global_registry)
    build_engine(SHIPPED)

    assert len(global_registry) == before
