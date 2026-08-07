"""ExampleAttack tests.

Exercises the example plugin end to end against ``FakeTarget`` to prove the SDK modules actually
compose into a working plugin, and pins down the Phase 5 acceptance criterion itself: the file
must stay under 100 lines.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.conftest import FakeTarget

from ragstrike.models.values.enums import PluginOutcome
from ragstrike.plugins.base.attack import Analysis
from ragstrike.plugins.base.context import PluginContext

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_DIR = REPO_ROOT / "examples" / "custom_pack"


def _import_example_attack():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "example_custom_pack_plugin", PLUGIN_DIR / "plugin.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ExampleAttack


def make_attack():
    attack_cls = _import_example_attack()
    context = PluginContext.for_plugin(plugin_id="example-attack", source=PLUGIN_DIR)
    return attack_cls(context=context)


def test_plugin_file_is_under_the_100_line_acceptance_criterion() -> None:
    lines = (PLUGIN_DIR / "plugin.py").read_text(encoding="utf-8").splitlines()

    assert len(lines) < 100


def test_payloads_loads_from_the_shipped_payload_directory() -> None:
    attack = make_attack()

    payloads = attack.payloads()

    assert len(payloads) >= 1
    assert all(payload.content for payload in payloads)


async def test_execute_sends_every_payload_to_the_target() -> None:
    attack = make_attack()
    target = FakeTarget(reply="a scripted answer")
    payloads = attack.payloads()

    records = await attack.execute(target, payloads)

    assert len(records) == len(payloads)
    assert target.prompts == [p.content for p in payloads]


async def test_full_lifecycle_produces_a_pass_analysis_against_a_healthy_target() -> None:
    attack = make_attack()
    target = FakeTarget(reply="a scripted answer")
    payloads = attack.payloads()

    records = await attack.execute(target, payloads)
    analysis = attack.analyze(records)

    assert analysis.outcome is PluginOutcome.PASS


async def test_execute_propagates_a_transport_failure_rather_than_swallowing_it() -> None:
    """ExampleAttack does no retrying or error-wrapping of its own -- a target that raises
    during ``chat()`` must surface to the caller (the scheduler's own isolation catches it there),
    not be silently absorbed into a fabricated ExecutionRecord."""
    attack = make_attack()
    target = FakeTarget(raises=ConnectionError("target down"))
    payloads = attack.payloads()

    with pytest.raises(ConnectionError):
        await attack.execute(target, payloads)


def test_recommendation_does_not_require_a_prior_analyze_call() -> None:
    attack = make_attack()

    recommendation = attack.recommendation(Analysis(outcome=PluginOutcome.PASS, summary="x"))

    assert recommendation.title
    assert recommendation.remediation
