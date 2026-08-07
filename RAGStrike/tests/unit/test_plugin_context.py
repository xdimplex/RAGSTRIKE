"""PluginContext + BaseAttack declarative API tests."""

from __future__ import annotations

from pathlib import Path

from ragstrike.models.values.enums import Capability, PluginOutcome, Severity
from ragstrike.plugins.base.attack import (
    Analysis,
    BaseAttack,
    Payload,
    Recommendation,
)
from ragstrike.plugins.base.context import PluginContext


class Minimal(BaseAttack):
    plugin_id = "minimal-attack"
    plugin_name = "Minimal"
    plugin_version = "1.2.3"
    author = "Tests"
    category = "diagnostic"
    severity = Severity.LOW
    tags = ("t",)

    def payloads(self):
        return [Payload(id="p", content="c")]

    async def execute(self, target, payloads):
        return []

    def analyze(self, records):
        return Analysis(outcome=PluginOutcome.PASS, summary="ok")

    def recommendation(self, analysis):
        return Recommendation(title="", remediation="")


def test_metadata_is_derived_from_class_attributes() -> None:
    """Declarative style: no ``metadata()`` override needed."""
    meta = Minimal().metadata()

    assert meta.slug == "minimal-attack"
    assert meta.version == "1.2.3"
    assert meta.author == "Tests"
    assert meta.severity is Severity.LOW
    assert meta.tags == ("t",)


def test_severity_override_from_context_takes_effect(tmp_path: Path) -> None:
    """plugins.yaml can raise or lower a plugin's severity without touching its code."""
    context = PluginContext.for_plugin(
        plugin_id="minimal-attack",
        source=tmp_path,
        severity_override="CRITICAL",
    )

    assert Minimal(context=context).metadata().severity is Severity.CRITICAL


def test_bad_severity_override_is_ignored(tmp_path: Path) -> None:
    """A typo in ``plugins.yaml`` should not stop a scan."""
    context = PluginContext.for_plugin(
        plugin_id="minimal-attack",
        source=tmp_path,
        severity_override="OOPS",
    )

    assert Minimal(context=context).metadata().severity is Severity.LOW


def test_options_backward_compat() -> None:
    """Phase 3 plugins used ``self.options``. Kept so existing plugins keep working."""
    plugin = Minimal(options={"foo": "bar"})

    assert plugin.options == {"foo": "bar"}
    assert plugin.context.config == {"foo": "bar"}


def test_default_validate_passes() -> None:
    report = Minimal().validate()
    assert report.valid


def test_default_healthcheck_passes() -> None:
    report = Minimal().healthcheck()
    assert report.healthy


def test_default_setup_and_cleanup_are_noops() -> None:
    """Nothing crashes -- and nothing side-effectful happens either."""
    plugin = Minimal()
    plugin.setup()
    plugin.cleanup()


def test_applies_to_capability_filter() -> None:
    class NeedsIngest(Minimal):
        requires_capabilities = (Capability.CHAT, Capability.INGEST_DOCUMENT)

    plugin = NeedsIngest()

    assert plugin.applies_to((Capability.CHAT, Capability.INGEST_DOCUMENT))
    assert not plugin.applies_to((Capability.CHAT,))
    # Unverified target -- attempt rather than skip.
    assert plugin.applies_to(())


def test_context_is_always_populated(tmp_path: Path) -> None:
    """Ad-hoc constructions (tests, one-shots) get a synthesised context so self.context is
    always valid."""
    plugin = Minimal()

    assert plugin.context is not None
    assert plugin.context.plugin_id == "minimal-attack"
