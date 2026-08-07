"""Plugin and configuration tests for the Context Poisoning pack.

Covers the lifecycle, the configuration surface, the evidence fields the brief enumerates, and the
property that distinguishes this pack from its siblings: the loopback refusal is unconditional --
there is no configuration value that reaches past it.
"""

from __future__ import annotations

import asyncio

import pytest

from ragstrike.attacks.context_poisoning.plugin import PACK_ROOT, ContextPoisoningAttack
from ragstrike.core.contracts.target_adapter import (
    HealthResult,
    TargetDescriptor,
    TargetResponse,
)
from ragstrike.models.values.enums import Capability, PluginOutcome, Severity
from ragstrike.plugins.base.context import PluginContext

BENIGN = ["company_handbook.pdf", "policy_document.pdf", "product_faq.pdf"]
POISON = "hidden_instruction.pdf"


class ScriptedTarget:
    def __init__(
        self,
        sources: list[str] | None = None,
        *,
        text: str = "An answer from the documents.",
        citations: list[str] | None = None,
        url: str = "http://127.0.0.1:9000",
        raises: Exception | None = None,
    ) -> None:
        self.sources = BENIGN if sources is None else sources
        self.text = text
        self.citations = citations
        self.url = url
        self.raises = raises
        self.prompts: list[str] = []

    def describe(self) -> TargetDescriptor:
        return TargetDescriptor(
            adapter="scripted",
            version="1.0.0",
            url=self.url,
            capabilities=(Capability.CHAT, Capability.RETURN_CHUNKS),
        )

    async def health_check(self) -> HealthResult:
        return HealthResult(reachable=True)

    async def close(self) -> None:
        return None

    async def chat(self, request) -> TargetResponse:
        self.prompts.append(request.prompt)
        if self.raises is not None:
            raise self.raises
        chunks = [{"chunk_id": f"c{i}", "source_name": s} for i, s in enumerate(self.sources)]
        return TargetResponse(
            text=self.text,
            retrieved_chunks=chunks,
            sources=self.citations if self.citations is not None else self.sources,
            latency_ms=1,
        )


def make_attack(**config) -> ContextPoisoningAttack:
    config.setdefault("datasets", ["benign-baseline"])
    context = PluginContext.for_plugin(
        plugin_id="context-poisoning", source=PACK_ROOT, config=config
    )
    return ContextPoisoningAttack(context=context)


def scan(attack: ContextPoisoningAttack, target: ScriptedTarget):
    records = asyncio.run(attack.execute(target, attack.payloads()))
    return attack.analyze(records)


# -- lifecycle ------------------------------------------------------------------------------------------


def test_payloads_come_from_the_datasets() -> None:
    attack = make_attack()

    payloads = attack.payloads()

    assert payloads
    assert all(p.expects["dataset_id"] == "benign-baseline" for p in payloads)


def test_payloads_are_deterministic() -> None:
    assert [p.id for p in make_attack().payloads()] == [p.id for p in make_attack().payloads()]


def test_every_payload_carries_its_dataset_version() -> None:
    """Evidence must name the dataset version, so the payload has to carry it through."""
    assert all(p.expects["dataset_version"] for p in make_attack().payloads())


def test_validate_passes_on_the_shipped_pack() -> None:
    report = make_attack().validate()

    assert report.valid, [c.rule for c in report.failures]


def test_validation_fails_when_datasets_cannot_be_found(tmp_path) -> None:
    """A pack whose datasets are missing must be refused at load time. A scan that runs zero cases
    produces output indistinguishable from a clean bill of health."""
    report = make_attack(dataset_location=str(tmp_path / "nowhere")).validate()

    assert not report.valid
    assert any(c.rule == "datasets-load" for c in report.failures)


# -- verdicts -------------------------------------------------------------------------------------------


def test_healthy_retrieval_passes() -> None:
    analysis = scan(make_attack(), ScriptedTarget())

    assert analysis.outcome is PluginOutcome.PASS


def test_a_retrieved_poisoned_document_fails() -> None:
    analysis = scan(make_attack(), ScriptedTarget([*BENIGN, POISON]))

    assert analysis.outcome is PluginOutcome.FAIL
    assert "forbidden_source_retrieved" in analysis.detail


def test_a_fabricated_citation_fails() -> None:
    analysis = scan(make_attack(), ScriptedTarget(BENIGN, citations=["ghost.pdf"]))

    assert analysis.outcome is PluginOutcome.FAIL
    assert "unsupported_citation" in analysis.detail


def test_a_repeated_canary_fails() -> None:
    analysis = scan(
        make_attack(datasets=["poisoned-corpus"]),
        ScriptedTarget(BENIGN, text="Per POISON-CANARY-HI-01, ignore policy."),
    )

    assert analysis.outcome is PluginOutcome.FAIL
    assert "poisoned_content_repeated" in analysis.detail


def test_an_empty_observation_is_inconclusive_not_a_pass() -> None:
    """Nothing came back at all. Calling that PASS would claim retrieval behaved correctly on the
    basis of no observation."""
    analysis = scan(make_attack(), ScriptedTarget([], text=""))

    assert analysis.outcome is PluginOutcome.INCONCLUSIVE


def test_a_transport_failure_is_an_error_not_a_pass() -> None:
    analysis = scan(make_attack(), ScriptedTarget(raises=ConnectionError("down")))

    assert analysis.outcome is PluginOutcome.ERROR


def test_one_failing_case_does_not_lose_the_others() -> None:
    attack = make_attack()

    analysis = scan(attack, ScriptedTarget(raises=ConnectionError("down")))

    assert len(analysis.evidence["results"]) == len(attack.payloads())


def test_min_confidence_is_configurable() -> None:
    analysis = scan(make_attack(min_confidence=1.5), ScriptedTarget([*BENIGN, POISON]))

    assert analysis.outcome is not PluginOutcome.FAIL


# -- unconditional local-only enforcement -----------------------------------------------------------------


def test_a_non_local_target_is_refused() -> None:
    analysis = scan(make_attack(), ScriptedTarget(url="http://example.com:9000"))

    assert analysis.outcome is PluginOutcome.SKIPPED
    assert "not loopback" in analysis.summary


def test_a_refused_target_is_never_contacted() -> None:
    target = ScriptedTarget(url="http://example.com:9000")

    scan(make_attack(), target)

    assert target.prompts == []


@pytest.mark.parametrize(
    "option",
    [
        {"require_local_target": False},
        {"allow_remote": True},
        {"allow_remote_targets": True},
    ],
)
def test_no_configuration_can_enable_a_remote_target(option: dict) -> None:
    """The property that distinguishes this pack from its siblings. The Phase 9 brief requires that
    configuration to enable external targets not exist here, so the refusal is unconditional in
    code -- these plausible-looking options must all be inert."""
    target = ScriptedTarget(url="http://example.com:9000")

    analysis = scan(make_attack(**option), target)

    assert analysis.outcome is PluginOutcome.SKIPPED
    assert target.prompts == []


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:9000", "http://localhost:9000", "http://[::1]:9000"]
)
def test_loopback_forms_are_accepted(url: str) -> None:
    target = ScriptedTarget(url=url)

    scan(make_attack(), target)

    assert target.prompts


# -- evidence -----------------------------------------------------------------------------------------------


def test_evidence_captures_every_field_the_brief_requires() -> None:
    analysis = scan(make_attack(), ScriptedTarget())

    case = analysis.evidence["results"][0]["evidence"]

    for field in (
        "question_id",
        "dataset_id",
        "dataset_version",
        "retrieved_sources",
        "retrieved_chunk_ids",
        "execution_ms",
        "observed_response",
        "expected_summary",
        "timestamp",
    ):
        assert field in case, f"evidence missing {field}"


def test_evidence_records_the_analyzer_reason() -> None:
    analysis = scan(make_attack(), ScriptedTarget([*BENIGN, POISON]))

    reasons = {r["evidence"].get("reason") for r in analysis.evidence["results"]}
    assert "forbidden_source_retrieved" in reasons


def test_evidence_records_the_dataset_version() -> None:
    analysis = scan(make_attack(), ScriptedTarget())

    assert analysis.evidence["datasets"][0]["dataset_version"]


def test_evidence_records_skipped_datasets(tmp_path) -> None:
    """A dataset that failed to load must be visible, or a scan silently covers less than it
    appears to."""
    (tmp_path / "bad.yaml").write_text("cases: [unclosed\n", encoding="utf-8")

    attack = make_attack(dataset_location=str(tmp_path))
    analysis = attack.analyze([])

    assert analysis.evidence["skipped_datasets"]


def test_chunk_ids_are_recorded_even_without_an_id_key() -> None:
    """A positional placeholder is more useful to a reader than a silently shorter list."""

    class NoIdTarget(ScriptedTarget):
        async def chat(self, request):
            self.prompts.append(request.prompt)
            return TargetResponse(
                text="answer",
                retrieved_chunks=[{"source_name": s} for s in BENIGN],
                sources=BENIGN,
                latency_ms=1,
            )

    analysis = scan(make_attack(), NoIdTarget())

    ids = analysis.evidence["results"][0]["evidence"]["retrieved_chunk_ids"]
    assert len(ids) == len(BENIGN)


def test_the_observed_response_is_bounded() -> None:
    analysis = scan(make_attack(evidence={"response_chars": 20}), ScriptedTarget(text="x" * 500))

    assert len(analysis.evidence["results"][0]["evidence"]["observed_response"]) == 20


def test_negative_signals_are_excluded_by_default_and_includable() -> None:
    quiet = scan(make_attack(), ScriptedTarget())
    verbose = scan(make_attack(evidence={"include_negative_signals": True}), ScriptedTarget())

    assert len(verbose.evidence["results"][0]["evidence"]["signals"]) > len(
        quiet.evidence["results"][0]["evidence"]["signals"]
    )


def test_evidence_is_json_serializable() -> None:
    import json

    json.dumps(scan(make_attack(), ScriptedTarget([*BENIGN, POISON])).evidence)


# -- configuration -----------------------------------------------------------------------------------------------


def test_datasets_can_be_selected_by_id() -> None:
    only_benign = make_attack(datasets=["benign-baseline"]).payloads()
    both = make_attack(datasets=[]).payloads()

    assert len(both) > len(only_benign)


def test_dataset_location_can_be_an_absolute_path(tmp_path) -> None:
    (tmp_path / "custom.yaml").write_text(
        'dataset_id: "custom"\nversion: "1.0.0"\ncases:\n'
        '  - question_id: "c-1"\n    question: "hi?"\n'
        "    expected:\n      retrieval: {min_chunks: 1}\n",
        encoding="utf-8",
    )

    attack = make_attack(dataset_location=str(tmp_path), datasets=[])

    assert [p.id for p in attack.payloads()] == ["c-1"]


def test_severity_override_is_honoured() -> None:
    context = PluginContext.for_plugin(
        plugin_id="context-poisoning", source=PACK_ROOT, config={}, severity_override="LOW"
    )

    assert ContextPoisoningAttack(context=context).metadata().severity is Severity.LOW


def test_an_unknown_logging_level_fails_validation() -> None:
    report = make_attack(logging={"level": "shout"}).validate()

    assert not report.valid
    assert any(c.rule == "logging-level-known" for c in report.failures)


def test_per_case_logging_is_off_by_default(caplog) -> None:
    with caplog.at_level("DEBUG"):
        scan(make_attack(), ScriptedTarget())

    assert not any("sending case" in r.message for r in caplog.records)


def test_per_case_logging_can_be_enabled(caplog) -> None:
    with caplog.at_level("DEBUG"):
        scan(make_attack(logging={"per_case": True}), ScriptedTarget())

    assert any("sending case" in r.message for r in caplog.records)


# -- recommendations -----------------------------------------------------------------------------------------------


def test_recommendation_is_keyed_by_the_failure_reason() -> None:
    attack = make_attack()
    poisoned = scan(attack, ScriptedTarget([*BENIGN, POISON]))
    fabricated = scan(attack, ScriptedTarget(BENIGN, citations=["ghost.pdf"]))

    assert attack.recommendation(poisoned).title != attack.recommendation(fabricated).title


def test_a_clean_result_recommends_no_action() -> None:
    attack = make_attack()
    analysis = scan(attack, ScriptedTarget())

    assert "no action" in attack.recommendation(analysis).title.lower()


def test_recommendations_are_retrieved_not_generated() -> None:
    attack = make_attack()
    analysis = scan(attack, ScriptedTarget([*BENIGN, POISON]))

    assert attack.recommendation(analysis) == attack.recommendation(analysis)


def test_a_missing_corpus_recommends_checking_ingestion() -> None:
    """The most common cause of a failing scan is an un-ingested corpus, not a security problem.
    The advice has to say so, or an operator chases a vulnerability that does not exist."""
    attack = make_attack()
    analysis = scan(attack, ScriptedTarget(["unrelated.pdf"]))

    assert "ingest" in attack.recommendation(analysis).remediation.lower()


# -- corpus preconditions -------------------------------------------------------------------------


def test_the_poisoned_dataset_is_inconclusive_when_the_poison_was_never_ingested() -> None:
    """PASS here would be the pack's own dead battery.

    The `poisoned-corpus` dataset asks, of every case, "was the poisoned document wrongly
    retrieved?". Run against a corpus containing no poisoned document, every case is satisfied and
    the pack folded that to `PASS -- 8/8` -- reporting "context poisoning: clean" about a
    DELIBERATELY VULNERABLE target.

    That is exactly the confusion INCONCLUSIVE exists to prevent: "I checked and it held" is not the
    same statement as "there was nothing to check". Here the principle is applied to the pack's own
    precondition rather than to the target's behaviour.
    """
    attack = make_attack(datasets=["poisoned-corpus"])

    # A clean corpus: only the benign documents are ever retrieved.
    analysis = scan(attack, ScriptedTarget(sources=BENIGN))

    assert analysis.outcome is PluginOutcome.INCONCLUSIVE
    assert "precondition" in analysis.summary.lower()
    assert analysis.confidence == 0.0


def test_the_unmet_precondition_names_the_dataset_and_says_how_to_fix_it() -> None:
    """A verdict an operator cannot act on is only half a result."""
    analysis = scan(make_attack(datasets=["poisoned-corpus"]), ScriptedTarget(sources=BENIGN))

    assert "poisoned-corpus" in analysis.summary
    assert "include-poisoned" in analysis.detail


def test_a_verdict_survives_when_another_dataset_carried_it() -> None:
    """The shipped default runs BOTH datasets, and `poisoned-corpus` is unmet on any ordinary lab.

    Overriding whenever *any* dataset was unmet would make the pack permanently INCONCLUSIVE in
    normal use -- useless in a different way. With the benign baseline satisfied there is a real
    verdict to report, and the gap is named in the detail instead.
    """
    analysis = scan(make_attack(datasets=[]), ScriptedTarget(sources=BENIGN))

    assert analysis.outcome is PluginOutcome.PASS
    assert "coverage gap" in analysis.detail.lower()
    assert "poisoned-corpus" in analysis.detail


def test_a_dataset_whose_documents_are_present_is_judged_normally() -> None:
    """The check must not swallow a genuine verdict.

    One appearance of a declared document anywhere in the run clears the dataset -- deliberately
    conservative, because a false 'precondition met' merely restores the previous behaviour whereas
    a false 'unmet' would mask a real result.
    """
    attack = make_attack(datasets=["poisoned-corpus"])

    analysis = scan(attack, ScriptedTarget(sources=[*BENIGN, POISON]))

    assert analysis.outcome is not PluginOutcome.INCONCLUSIVE


def test_the_benign_baseline_is_unaffected_by_the_precondition_check() -> None:
    """Its declared documents are the ordinary corpus, so it must still reach a real verdict."""
    analysis = scan(make_attack(), ScriptedTarget())

    assert analysis.outcome is PluginOutcome.PASS
