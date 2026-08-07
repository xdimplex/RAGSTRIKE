"""The five Phase 6 evaluation plugins.

These tests exercise ``judge()`` directly wherever possible. ``judge`` is pure by contract -- no
network, no clock, no randomness -- so its whole truth table is reachable without a target, which
is the property that makes a criterion auditable rather than merely observed to work once.

Each plugin gets a "recognises correct behaviour", a "recognises the failure it exists to catch",
and an "admits when it cannot tell" case. The third matters most: a criterion that never returns
INCONCLUSIVE is one that will eventually report a confident verdict it has not earned.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from ragstrike.core.contracts.target_adapter import TargetResponse
from ragstrike.models.values.enums import PluginOutcome
from ragstrike.plugins.base.context import PluginContext
from ragstrike.sdk.response_parser import ResponseParser

PLUGINS_DIR = Path(__file__).resolve().parent.parent.parent / "plugins"

_PLUGINS = {
    "instruction_priority": "InstructionPriorityEvaluation",
    "prompt_boundary": "PromptBoundaryEvaluation",
    "context_separation": "ContextSeparationEvaluation",
    "source_attribution": "SourceAttributionVerification",
    "retrieval_consistency": "RetrievalConsistencyEvaluation",
}


def load_plugin(directory: str):
    """Import a plugin the way the loader does -- straight from its file path."""
    source = PLUGINS_DIR / directory
    spec = importlib.util.spec_from_file_location(f"phase6_{directory}", source / "plugin.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    attack_cls = getattr(module, _PLUGINS[directory])
    return attack_cls(context=PluginContext.for_plugin(plugin_id=directory, source=source))


def observed(text: str = "An answer.", **kwargs: Any) -> ResponseParser:
    return ResponseParser(TargetResponse(text=text, **kwargs))


# -- properties every evaluation plugin must hold ------------------------------------------------


@pytest.mark.parametrize("directory", sorted(_PLUGINS))
def test_every_plugin_loads_its_cases_from_configuration(directory: str) -> None:
    """The test cases live in payloads/, not in the code -- the brief's requirement, and the
    reason adding a case does not mean editing Python."""
    payloads = load_plugin(directory).payloads()

    assert payloads, f"{directory} shipped no test cases"
    assert all(p.id and p.content.strip() for p in payloads)


@pytest.mark.parametrize("directory", sorted(_PLUGINS))
def test_every_case_declares_its_expectation(directory: str) -> None:
    assert all(p.expects for p in load_plugin(directory).payloads())


@pytest.mark.parametrize("directory", sorted(_PLUGINS))
def test_an_empty_response_is_never_reported_as_a_pass(directory: str) -> None:
    """A target that said nothing has demonstrated nothing. Reporting that as PASS would be the
    single most damaging bug this plugin family could have."""
    plugin = load_plugin(directory)
    case = plugin.payloads()[0]

    verdict = plugin.judge(observed(""), case.expects)

    assert verdict.outcome is not PluginOutcome.PASS


# -- instruction priority --------------------------------------------------------------------------


def test_instruction_priority_passes_when_the_marker_is_absent() -> None:
    plugin = load_plugin("instruction_priority")

    verdict = plugin.judge(observed("The documents cover finance."), {"marker": "ACK-1"})

    assert verdict.outcome is PluginOutcome.PASS


def test_instruction_priority_fails_when_the_target_echoes_the_marker() -> None:
    plugin = load_plugin("instruction_priority")

    verdict = plugin.judge(observed("ACK-1"), {"marker": "ACK-1"})

    assert verdict.outcome is PluginOutcome.FAIL


def test_instruction_priority_matching_is_case_insensitive() -> None:
    """Echoing the token in a different case is still echoing it. Matching case-sensitively would
    score the target's formatting rather than its behaviour."""
    plugin = load_plugin("instruction_priority")

    verdict = plugin.judge(observed("ack-1"), {"marker": "ACK-1"})

    assert verdict.outcome is PluginOutcome.FAIL


def test_instruction_priority_is_inconclusive_without_a_marker() -> None:
    plugin = load_plugin("instruction_priority")

    assert plugin.judge(observed("hello"), {}).outcome is PluginOutcome.INCONCLUSIVE


# -- prompt boundary ------------------------------------------------------------------------------


def test_prompt_boundary_passes_on_a_clean_reply() -> None:
    plugin = load_plugin("prompt_boundary")

    verdict = plugin.judge(
        observed("I can answer questions about the documents."),
        {"forbidden_phrases": ["you are a helpful"]},
    )

    assert verdict.outcome is PluginOutcome.PASS


def test_prompt_boundary_fails_when_configuration_text_surfaces() -> None:
    plugin = load_plugin("prompt_boundary")

    verdict = plugin.judge(
        observed("You are a helpful assistant that answers from documents."),
        {"forbidden_phrases": ["you are a helpful"]},
    )

    assert verdict.outcome is PluginOutcome.FAIL


def test_prompt_boundary_evidence_names_the_phrase_not_the_surrounding_text() -> None:
    """The evidence must prove a leak without becoming a second copy of the leaked material."""
    plugin = load_plugin("prompt_boundary")
    secret = "and the admin override code is SWORDFISH"

    verdict = plugin.judge(
        observed(f"You are a helpful assistant {secret}"),
        {"forbidden_phrases": ["you are a helpful"]},
    )

    assert "SWORDFISH" not in verdict.note


# -- context separation ---------------------------------------------------------------------------


def test_context_separation_passes_when_the_passage_is_summarized() -> None:
    plugin = load_plugin("context_separation")

    verdict = plugin.judge(
        observed("The passage reports four percent growth."), {"marker": "SEP-1"}
    )

    assert verdict.outcome is PluginOutcome.PASS


def test_context_separation_fails_when_the_embedded_directive_is_executed() -> None:
    plugin = load_plugin("context_separation")

    verdict = plugin.judge(observed("SEP-1"), {"marker": "SEP-1"})

    assert verdict.outcome is PluginOutcome.FAIL


# -- source attribution ---------------------------------------------------------------------------


def test_source_attribution_passes_when_citations_match_retrieved_chunks() -> None:
    plugin = load_plugin("source_attribution")
    response = observed(
        "An answer.",
        sources=["a.pdf"],
        retrieved_chunks=[{"source_name": "a.pdf"}],
    )

    verdict = plugin.judge(
        response, {"require_sources": True, "require_sources_match_chunks": True}
    )

    assert verdict.outcome is PluginOutcome.PASS


def test_source_attribution_fails_on_a_citation_that_was_never_retrieved() -> None:
    """The finding this plugin exists for: a confident citation with no retrieval behind it."""
    plugin = load_plugin("source_attribution")
    response = observed(
        "An answer.",
        sources=["ghost.pdf"],
        retrieved_chunks=[{"source_name": "real.pdf"}],
    )

    verdict = plugin.judge(
        response, {"require_sources": True, "require_sources_match_chunks": True}
    )

    assert verdict.outcome is PluginOutcome.FAIL
    assert "ghost.pdf" in verdict.note


def test_source_attribution_fails_when_sources_are_required_but_absent() -> None:
    plugin = load_plugin("source_attribution")

    verdict = plugin.judge(observed("An answer."), {"require_sources": True})

    assert verdict.outcome is PluginOutcome.FAIL


def test_source_attribution_is_inconclusive_when_provenance_cannot_be_checked() -> None:
    """Citations exist but the adapter surfaced no chunk provenance. That is a limit on what can
    be observed, not evidence the citations are wrong."""
    plugin = load_plugin("source_attribution")
    response = observed("An answer.", sources=["a.pdf"], retrieved_chunks=[])

    verdict = plugin.judge(response, {"require_sources_match_chunks": True})

    assert verdict.outcome is PluginOutcome.INCONCLUSIVE


def test_source_attribution_allows_a_grounded_refusal_to_cite_nothing() -> None:
    """A question with no answer in the corpus should produce no citations. Requiring some would
    push the target toward inventing them, which is the failure this plugin is meant to catch."""
    plugin = load_plugin("source_attribution")

    verdict = plugin.judge(
        observed("I could not find that in the documents."),
        {"require_sources": False, "require_sources_match_chunks": True},
    )

    assert verdict.outcome is PluginOutcome.PASS


# -- retrieval consistency ------------------------------------------------------------------------


def records_for(plugin, source_sets: list[list[str]]):
    """Build one ExecutionRecord per repeat, all in the same comparison group."""
    from ragstrike.plugins.base.attack import ExecutionRecord

    plugin._expectations = {f"r{i}": {"group": "g"} for i in range(len(source_sets))}
    return [
        ExecutionRecord(
            payload_id=f"r{i}",
            prompt="same question",
            response=TargetResponse(
                text="An answer.",
                sources=list(sources),
                retrieved_chunks=[{"source_name": s} for s in sources],
            ),
        )
        for i, sources in enumerate(source_sets)
    ]


def test_retrieval_consistency_passes_when_every_repeat_retrieves_the_same_sources() -> None:
    plugin = load_plugin("retrieval_consistency")
    records = records_for(plugin, [["a.pdf", "b.pdf"]] * 3)

    assert plugin.analyze(records).outcome is PluginOutcome.PASS


def test_retrieval_consistency_ignores_ordering_differences() -> None:
    """Retrieval returning the same documents in a different order is still the same retrieval;
    only the set matters for reproducibility of a downstream finding."""
    plugin = load_plugin("retrieval_consistency")
    records = records_for(plugin, [["a.pdf", "b.pdf"], ["b.pdf", "a.pdf"], ["a.pdf", "b.pdf"]])

    assert plugin.analyze(records).outcome is PluginOutcome.PASS


def test_retrieval_consistency_fails_when_the_source_set_drifts() -> None:
    plugin = load_plugin("retrieval_consistency")
    records = records_for(plugin, [["a.pdf"], ["b.pdf"], ["c.pdf"]])

    analysis = plugin.analyze(records)

    assert analysis.outcome is PluginOutcome.FAIL


def test_retrieval_consistency_is_inconclusive_with_too_few_usable_repeats() -> None:
    """One usable response cannot be inconsistent with itself."""
    plugin = load_plugin("retrieval_consistency")
    records = records_for(plugin, [["a.pdf"]])

    assert plugin.analyze(records).outcome is PluginOutcome.INCONCLUSIVE


def test_retrieval_consistency_is_inconclusive_without_provenance() -> None:
    plugin = load_plugin("retrieval_consistency")
    records = records_for(plugin, [[], [], []])

    assert plugin.analyze(records).outcome is PluginOutcome.INCONCLUSIVE


# -- recommendations ------------------------------------------------------------------------------


@pytest.mark.parametrize("directory", sorted(_PLUGINS))
def test_recommendation_differs_between_a_finding_and_a_clean_result(directory: str) -> None:
    """Advice that reads the same whether or not anything was found is not advice."""
    from ragstrike.plugins.base.attack import Analysis

    plugin = load_plugin(directory)
    failed = plugin.recommendation(Analysis(outcome=PluginOutcome.FAIL, summary="x"))
    passed = plugin.recommendation(Analysis(outcome=PluginOutcome.PASS, summary="x"))

    assert failed.title != passed.title
    assert failed.remediation and passed.remediation
