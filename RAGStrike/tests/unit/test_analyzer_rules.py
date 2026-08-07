"""Rule engine tests.

The rule engine is what makes the analyzer, rather than a plugin, the author of a finding. The
tests that matter most are the ones proving a rule can *disagree* with a plugin -- if it cannot,
the engine is just copying verdicts through with extra steps.
"""

from __future__ import annotations

from pathlib import Path

from ragstrike.analyzers.base.observation import Observation
from ragstrike.analyzers.rules.rule_engine import (
    Condition,
    Rule,
    RuleEngine,
    RuleSet,
    load_ruleset,
)
from ragstrike.models.values.enums import PluginOutcome, Severity

SHIPPED_RULES = Path("configs") / "analyzer" / "rules.yaml"


def observation(**kwargs) -> Observation:
    defaults = {
        "plugin_id": "p",
        "scan_id": "s1",
        "category": "prompt_injection",
        "reported_status": PluginOutcome.FAIL,
        "reported_confidence": 0.9,
        "evidence": {"confidence": 0.9},
    }
    defaults.update(kwargs)
    return Observation(**defaults)


def rule(rule_id: str, **kwargs) -> Rule:
    return Rule(id=rule_id, **kwargs)


# -- conditions -------------------------------------------------------------------------------------


def test_eq_and_ne() -> None:
    facts = {"category": "prompt_injection"}

    assert Condition("category", "eq", "prompt_injection").evaluate(facts)
    assert not Condition("category", "ne", "prompt_injection").evaluate(facts)


def test_numeric_comparisons() -> None:
    facts = {"failure_ratio": 0.75}

    assert Condition("failure_ratio", "gt", 0.5).evaluate(facts)
    assert Condition("failure_ratio", "gte", 0.75).evaluate(facts)
    assert Condition("failure_ratio", "lt", 0.9).evaluate(facts)
    assert not Condition("failure_ratio", "lt", 0.5).evaluate(facts)


def test_membership() -> None:
    facts = {"category": "prompt_leakage"}

    assert Condition("category", "in", ["prompt_leakage", "prompt_injection"]).evaluate(facts)
    assert Condition("category", "not_in", ["context_poisoning"]).evaluate(facts)


def test_contains_is_case_insensitive() -> None:
    assert Condition("target", "contains", "LOCALHOST").evaluate({"target": "http://localhost"})


def test_exists() -> None:
    assert Condition("error", "exists", True).evaluate({"error": "boom"})
    assert Condition("error", "exists", False).evaluate({"error": None})


def test_an_unknown_operator_never_matches() -> None:
    """Rather than raising mid-analysis. A rule that cannot be evaluated should be inert, not fatal
    to every other finding in the scan."""
    assert not Condition("category", "wat", "x").evaluate({"category": "x"})


def test_a_missing_field_does_not_raise() -> None:
    assert not Condition("nonexistent", "gt", 5).evaluate({})


def test_a_non_numeric_value_compares_as_zero() -> None:
    """A rule comparing a missing or malformed field against a threshold should simply not match."""
    assert not Condition("failure_ratio", "gt", 0.5).evaluate({"failure_ratio": "nonsense"})


# -- rule matching -----------------------------------------------------------------------------------


def test_all_conditions_must_hold() -> None:
    engine = RuleEngine(
        RuleSet(
            rules=(
                rule(
                    "both",
                    conditions=(
                        Condition("reported_status", "eq", "FAIL"),
                        Condition("failure_ratio", "gt", 0.9),
                    ),
                    severity=Severity.CRITICAL,
                ),
            )
        )
    )

    outcome = engine.evaluate(observation())

    assert "both" not in outcome.matched


def test_applies_to_scopes_a_rule_to_categories() -> None:
    engine = RuleEngine(
        RuleSet(
            rules=(
                rule(
                    "leakage-only",
                    applies_to=("prompt_leakage",),
                    conditions=(Condition("reported_status", "eq", "FAIL"),),
                    severity=Severity.CRITICAL,
                ),
            )
        )
    )

    assert not engine.evaluate(observation(category="prompt_injection")).matched
    assert engine.evaluate(observation(category="prompt_leakage")).matched == ("leakage-only",)


def test_an_empty_applies_to_matches_every_category() -> None:
    engine = RuleEngine(
        RuleSet(rules=(rule("any", conditions=(Condition("reported_status", "eq", "FAIL"),)),))
    )

    assert engine.evaluate(observation(category="brand_new")).matched == ("any",)


def test_higher_priority_wins() -> None:
    engine = RuleEngine(
        RuleSet(
            rules=(
                rule("low", priority=1, severity=Severity.LOW),
                rule("high", priority=99, severity=Severity.CRITICAL),
            )
        )
    )

    outcome = engine.evaluate(observation())

    assert outcome.matched == ("high",)
    assert outcome.severity is Severity.CRITICAL


def test_stop_false_lets_evaluation_continue() -> None:
    engine = RuleEngine(
        RuleSet(
            rules=(
                rule("first", priority=10, stop=False, confidence_modifier=0.1),
                rule("second", priority=5, severity=Severity.HIGH),
            )
        )
    )

    outcome = engine.evaluate(observation())

    assert outcome.matched == ("first", "second")
    assert outcome.confidence_modifier == 0.1


# -- the analyzer overriding the plugin ----------------------------------------------------------------


def test_a_rule_can_override_a_plugin_reported_status() -> None:
    """The property this whole phase rests on. Without it the analyzer is a pass-through."""
    engine = RuleEngine(
        RuleSet(
            rules=(
                rule(
                    "downgrade",
                    conditions=(Condition("has_evidence", "eq", False),),
                    status=PluginOutcome.INCONCLUSIVE,
                ),
            )
        )
    )

    outcome = engine.evaluate(observation(reported_status=PluginOutcome.FAIL, evidence={}))

    assert outcome.status is PluginOutcome.INCONCLUSIVE
    assert outcome.overrode_plugin is True


def test_an_override_is_recorded_in_the_notes() -> None:
    """An operator reading a finding deserves to know the analyzer disagreed with the plugin."""
    engine = RuleEngine(RuleSet(rules=(rule("flip", status=PluginOutcome.INCONCLUSIVE),)))

    outcome = engine.evaluate(observation(reported_status=PluginOutcome.FAIL))

    assert "overrides plugin-reported" in outcome.notes


def test_agreeing_with_the_plugin_is_not_an_override() -> None:
    engine = RuleEngine(RuleSet(rules=(rule("agree", status=PluginOutcome.FAIL),)))

    assert engine.evaluate(observation(reported_status=PluginOutcome.FAIL)).overrode_plugin is False


# -- the fallback ---------------------------------------------------------------------------------------


def test_with_no_rules_the_plugin_status_stands() -> None:
    """An empty rules file must still produce usable findings. Degrading to "trust the plugin" is
    recoverable; degrading to "no finding" is a silent loss of coverage."""
    outcome = RuleEngine().evaluate(observation(reported_status=PluginOutcome.FAIL))

    assert outcome.status is PluginOutcome.FAIL
    assert outcome.matched == ()


def test_the_default_severity_applies_when_no_rule_sets_one() -> None:
    engine = RuleEngine(RuleSet(default_severity=Severity.LOW))

    assert engine.evaluate(observation()).severity is Severity.LOW


# -- facts ------------------------------------------------------------------------------------------------


def test_facts_expose_the_documented_fields() -> None:
    facts = RuleEngine.facts_for(observation())

    for name in (
        "plugin_id",
        "category",
        "reported_status",
        "reported_confidence",
        "failure_ratio",
        "has_error",
        "has_evidence",
    ):
        assert name in facts


def test_failure_ratio_is_computed_from_cases() -> None:
    obs = observation(
        evidence={
            "results": [
                {"status": "FAIL"},
                {"status": "FAIL"},
                {"status": "PASS"},
                {"status": "PASS"},
            ]
        }
    )

    assert RuleEngine.facts_for(obs)["failure_ratio"] == 0.5


# -- loading ------------------------------------------------------------------------------------------------


def test_the_shipped_ruleset_loads_cleanly() -> None:
    ruleset = load_ruleset(SHIPPED_RULES)

    assert ruleset.rules
    assert ruleset.skipped == ()


def test_shipped_rule_ids_are_unique() -> None:
    ids = [r.id for r in load_ruleset(SHIPPED_RULES).rules]

    assert len(ids) == len(set(ids))


def test_a_malformed_rule_is_skipped_not_fatal(tmp_path: Path) -> None:
    """One bad rule must not disable grading entirely."""
    path = tmp_path / "rules.yaml"
    path.write_text(
        "rules:\n"
        "  - id: good\n    conditions: [{field: category, operator: eq, value: x}]\n"
        "  - id: bad\n    conditions: [{field: category, operator: nonsense, value: x}]\n",
        encoding="utf-8",
    )

    ruleset = load_ruleset(path)

    assert [r.id for r in ruleset.rules] == ["good"]
    assert len(ruleset.skipped) == 1


def test_a_rule_with_no_id_is_skipped(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text("rules:\n  - description: nameless\n", encoding="utf-8")

    assert load_ruleset(path).rules == ()


def test_a_missing_file_yields_an_empty_ruleset(tmp_path: Path) -> None:
    """The engine's fallback keeps producing findings, so a missing file degrades rather than
    aborting."""
    assert load_ruleset(tmp_path / "nope.yaml").rules == ()


def test_json_is_accepted_too(tmp_path: Path) -> None:
    """The brief requires YAML and JSON. safe_load parses both, so one path serves them."""
    path = tmp_path / "rules.json"
    path.write_text(
        '{"rules": [{"id": "j1", "severity": "HIGH", "conditions": []}]}', encoding="utf-8"
    )

    assert [r.id for r in load_ruleset(path).rules] == ["j1"]


def test_rules_are_never_executed_as_code(tmp_path: Path) -> None:
    """A rules file is untrusted input. Nothing in it is eval'd, so a value that looks like code is
    just a string that fails to match."""
    path = tmp_path / "rules.yaml"
    path.write_text(
        "rules:\n  - id: inert\n"
        "    conditions: [{field: category, operator: eq, value: \"__import__('os').system('x')\"}]\n",
        encoding="utf-8",
    )

    engine = RuleEngine(load_ruleset(path))

    assert engine.evaluate(observation()).matched == ()


# -- the shipped rules, end to end ----------------------------------------------------------------------------


def test_an_errored_run_is_never_graded_as_a_security_verdict() -> None:
    """ERROR describes the run, not the target. Rewriting it into PASS or FAIL would be a lie."""
    engine = RuleEngine(load_ruleset(SHIPPED_RULES))

    outcome = engine.evaluate(observation(error="connection refused"))

    assert outcome.status is PluginOutcome.ERROR


def test_a_failure_with_no_evidence_is_downgraded() -> None:
    engine = RuleEngine(load_ruleset(SHIPPED_RULES))

    outcome = engine.evaluate(observation(reported_status=PluginOutcome.FAIL, evidence={}))

    assert outcome.status is PluginOutcome.INCONCLUSIVE


def test_a_highly_reliable_injection_escalates_to_critical() -> None:
    """Reliability is part of severity: "works every time" and "worked once in ten" are different
    findings."""
    engine = RuleEngine(load_ruleset(SHIPPED_RULES))
    obs = observation(
        evidence={
            "confidence": 0.9,
            "results": [
                {"status": "FAIL"},
                {"status": "FAIL"},
                {"status": "FAIL"},
                {"status": "PASS"},
            ],
        }
    )

    assert engine.evaluate(obs).severity is Severity.CRITICAL


def test_an_unknown_category_still_gets_graded() -> None:
    """A pack written next year must produce a finding on the day it ships."""
    engine = RuleEngine(load_ruleset(SHIPPED_RULES))

    outcome = engine.evaluate(observation(category="brand_new_pack"))

    assert outcome.status is PluginOutcome.FAIL
    assert outcome.severity is Severity.MEDIUM
    assert outcome.matched
