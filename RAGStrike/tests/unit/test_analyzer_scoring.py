"""Scoring and confidence tests.

Every number a report shows comes from these two modules, so the properties worth pinning are the
ones a reader would rely on: that scores are reproducible by hand, that uncertainty lowers risk
rather than being ignored, and that only established findings contribute.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ragstrike.analyzers.base.finding import Finding
from ragstrike.analyzers.base.observation import Observation
from ragstrike.analyzers.confidence.confidence_engine import (
    ConfidenceConfig,
    ConfidenceEngine,
    load_confidence_config,
)
from ragstrike.analyzers.evidence.evidence_engine import EvidenceEngine, NormalizedEvidence
from ragstrike.analyzers.scoring.score_engine import (
    ScoreEngine,
    ScoringConfig,
    load_scoring_config,
)
from ragstrike.models.values.enums import PluginOutcome, Severity

SHIPPED = Path("configs") / "analyzer"


def finding(**kwargs) -> Finding:
    defaults = {
        "id": Finding.new_id(),
        "scan_id": "s1",
        "plugin_id": "p",
        "category": "prompt_injection",
        "status": PluginOutcome.FAIL,
        "severity": Severity.HIGH,
        "confidence": 1.0,
        "risk_score": 8.0,
    }
    defaults.update(kwargs)
    return Finding(**defaults)


# -- finding score ------------------------------------------------------------------------------------


def test_a_finding_score_is_severity_times_confidence() -> None:
    """Reproducible by hand from the finding's own fields, which is what makes it defensible."""
    engine = ScoreEngine()

    assert engine.score_finding(Severity.HIGH, 1.0, PluginOutcome.FAIL) == 8.0
    assert engine.score_finding(Severity.HIGH, 0.5, PluginOutcome.FAIL) == 4.0


def test_uncertainty_lowers_risk() -> None:
    """A critical finding nobody is sure of should not outrank a certain high-severity one."""
    engine = ScoreEngine()

    uncertain_critical = engine.score_finding(Severity.CRITICAL, 0.3, PluginOutcome.FAIL)
    certain_high = engine.score_finding(Severity.HIGH, 1.0, PluginOutcome.FAIL)

    assert uncertain_critical < certain_high


@pytest.mark.parametrize(
    "status",
    [PluginOutcome.PASS, PluginOutcome.INCONCLUSIVE, PluginOutcome.ERROR, PluginOutcome.SKIPPED],
)
def test_only_failures_contribute_risk(status: PluginOutcome) -> None:
    """A PASS found nothing; an INCONCLUSIVE established nothing. Letting either contribute would
    put a number in a report that no observation supports."""
    assert ScoreEngine().score_finding(Severity.CRITICAL, 1.0, status) == 0.0


def test_info_severity_scores_zero() -> None:
    assert ScoreEngine().score_finding(Severity.INFO, 1.0, PluginOutcome.FAIL) == 0.0


# -- category score -------------------------------------------------------------------------------------


def test_a_category_with_no_failures_scores_zero() -> None:
    score = ScoreEngine().score_category("prompt_injection", [finding(status=PluginOutcome.PASS)])

    assert score.score == 0.0
    assert score.failed == 0


def test_a_category_takes_its_worst_finding() -> None:
    engine = ScoreEngine()

    score = engine.score_category(
        "prompt_injection", [finding(risk_score=3.0), finding(risk_score=8.0)]
    )

    assert score.score >= 8.0


def test_additional_failures_raise_a_category_but_only_slightly() -> None:
    """Ten mediums are worse than one medium, but not worse than a critical."""
    engine = ScoreEngine()

    one = engine.score_category("c", [finding(risk_score=5.0)])
    several = engine.score_category("c", [finding(risk_score=5.0)] * 4)

    assert several.score > one.score
    assert several.score < 10.0


def test_a_category_score_is_capped_at_ten() -> None:
    engine = ScoreEngine()

    score = engine.score_category("c", [finding(risk_score=10.0)] * 10)

    assert score.score == 10.0


def test_the_worst_severity_is_reported() -> None:
    engine = ScoreEngine()

    score = engine.score_category(
        "c", [finding(severity=Severity.LOW), finding(severity=Severity.CRITICAL)]
    )

    assert score.worst_severity is Severity.CRITICAL


# -- scan score ------------------------------------------------------------------------------------------


def test_an_empty_scan_scores_zero() -> None:
    assert ScoreEngine().score_scan([]).score == 0.0


def test_a_scan_averages_its_categories() -> None:
    """A mean rather than a max: one broken category among ten is a different situation from ten
    broken categories, and a max cannot tell them apart."""
    engine = ScoreEngine()

    findings = [
        finding(category="a", risk_score=10.0),
        finding(category="b", status=PluginOutcome.PASS, risk_score=0.0),
    ]

    assert 0.0 < engine.score_scan(findings).score < 10.0


def test_category_weights_are_applied() -> None:
    weighted = ScoreEngine(ScoringConfig(category_weights={"a": 1.0, "b": 0.0})).score_scan(
        [finding(category="a", risk_score=10.0), finding(category="b", risk_score=0.0)]
    )
    unweighted = ScoreEngine().score_scan(
        [finding(category="a", risk_score=10.0), finding(category="b", risk_score=0.0)]
    )

    assert weighted.score > unweighted.score


def test_an_unweighted_category_still_counts() -> None:
    """A new pack contributes the day it ships rather than scoring zero until someone adds it."""
    engine = ScoreEngine(ScoringConfig(category_weights={"known": 1.0}))

    score = engine.score_scan([finding(category="brand_new", risk_score=10.0)])

    assert score.score > 0.0


def test_a_scan_score_records_its_model_version() -> None:
    """A number from six months ago has to stay interpretable."""
    assert ScoreEngine().score_scan([finding()]).model_version


def test_scoring_is_deterministic() -> None:
    engine = ScoreEngine()
    findings = [finding(category="a"), finding(category="b", severity=Severity.LOW)]

    assert engine.score_scan(findings).score == engine.score_scan(findings).score


# -- scoring config -----------------------------------------------------------------------------------------


def test_the_shipped_scoring_config_loads() -> None:
    config = load_scoring_config(SHIPPED / "scoring.yaml")

    assert config.weight_of(Severity.CRITICAL) > config.weight_of(Severity.HIGH)
    assert config.model_version


def test_severity_weights_are_ordered_sensibly() -> None:
    config = load_scoring_config(SHIPPED / "scoring.yaml")
    weights = [
        config.weight_of(s)
        for s in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO)
    ]

    assert weights == sorted(weights, reverse=True)


def test_a_missing_scoring_file_falls_back_to_defaults(tmp_path: Path) -> None:
    assert load_scoring_config(tmp_path / "nope.yaml").weight_of(Severity.HIGH) > 0


def test_partial_scoring_config_keeps_unspecified_defaults(tmp_path: Path) -> None:
    path = tmp_path / "scoring.yaml"
    path.write_text("severity_weights:\n  HIGH: 9.5\n", encoding="utf-8")

    config = load_scoring_config(path)

    assert config.weight_of(Severity.HIGH) == 9.5
    assert config.weight_of(Severity.CRITICAL) == 10.0


# -- confidence ------------------------------------------------------------------------------------------------


def observation(**kwargs) -> Observation:
    defaults = {
        "plugin_id": "p",
        "scan_id": "s1",
        "category": "prompt_injection",
        "reported_status": PluginOutcome.FAIL,
        "reported_confidence": 0.8,
        "evidence": {"confidence": 0.8, "results": [{"status": "FAIL", "evidence": {}}]},
    }
    defaults.update(kwargs)
    return Observation(**defaults)


def test_evidence_raises_confidence() -> None:
    """The judgement the defaults encode: a plugin showing its working is more trustworthy than one
    asserting a number."""
    engine = ConfidenceEngine()
    obs = observation()

    with_evidence = engine.compute(obs, EvidenceEngine().normalize(obs))
    without = engine.compute(obs, NormalizedEvidence())

    assert with_evidence.score > without.score


def test_no_evidence_incurs_a_penalty() -> None:
    result = ConfidenceEngine().compute(observation(), NormalizedEvidence())

    assert "no_evidence_penalty" in result.components


def test_an_errored_run_lowers_confidence() -> None:
    engine = ConfidenceEngine()
    evidence = EvidenceEngine().normalize(observation())

    clean = engine.compute(observation(), evidence)
    errored = engine.compute(observation(error="boom"), evidence)

    assert errored.score < clean.score


def test_corroboration_is_capped() -> None:
    """Ten detectors agreeing is not meaningfully more convincing than three, and without a ceiling
    a noisy pack would outrank a careful one on volume alone."""
    engine = ConfidenceEngine()
    obs = observation()

    three = engine.compute(obs, NormalizedEvidence(signals=tuple({"d": i} for i in range(3))))
    twenty = engine.compute(obs, NormalizedEvidence(signals=tuple({"d": i} for i in range(20))))

    assert three.score == twenty.score


def test_confidence_is_clamped_to_the_unit_interval() -> None:
    engine = ConfidenceEngine()
    evidence = EvidenceEngine().normalize(observation())

    high = engine.compute(observation(reported_confidence=5.0), evidence, modifier=2.0)
    low = engine.compute(observation(reported_confidence=-1.0), evidence, modifier=-5.0)

    assert high.score == 1.0
    assert low.score == 0.0


def test_rule_modifiers_are_applied() -> None:
    engine = ConfidenceEngine()
    evidence = EvidenceEngine().normalize(observation())

    base = engine.compute(observation(), evidence)
    boosted = engine.compute(observation(), evidence, modifier=0.1)

    assert boosted.score > base.score


@pytest.mark.parametrize(("score", "band"), [(0.9, "high"), (0.5, "medium"), (0.1, "low")])
def test_bands_follow_thresholds(score: float, band: str) -> None:
    assert ConfidenceEngine().band_for(score) == band


def test_bands_are_configurable() -> None:
    engine = ConfidenceEngine(ConfidenceConfig(high_threshold=0.2, medium_threshold=0.1))

    assert engine.band_for(0.25) == "high"


def test_confidence_components_explain_the_score() -> None:
    """A number a reader cannot decompose is one they cannot argue with."""
    obs = observation()

    result = ConfidenceEngine().compute(obs, EvidenceEngine().normalize(obs))

    assert result.components
    assert pytest.approx(result.score, abs=0.001) == max(
        0.0, min(1.0, sum(result.components.values()))
    )


def test_the_shipped_confidence_config_loads() -> None:
    config = load_confidence_config(SHIPPED / "confidence.yaml")

    assert config.high_threshold > config.medium_threshold


def test_a_missing_confidence_file_falls_back_to_defaults(tmp_path: Path) -> None:
    assert load_confidence_config(tmp_path / "nope.yaml").plugin_weight > 0
