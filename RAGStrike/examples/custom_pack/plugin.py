"""ExampleAttack -- demonstrates the Attack SDK. NOT a security attack.

Loads a payload, sends it through the SDK's request builder, parses the response, and returns a
standardized result -- the three things the Phase 5 brief asks a plugin to write. Everything else
(request assembly, response extraction, result bookkeeping, folding into ``Analysis``) comes from
:mod:`ragstrike.sdk`. See ``docs/sdk-guide.md`` for the full walkthrough.

This file is under 100 lines. That is the acceptance criterion the SDK exists to satisfy.

Not discovered by the plugin registry: this directory lives under ``examples/``, not
``plugins/`` or ``packs/``, so it never appears in ``ragstrike plugins list``.
"""

from __future__ import annotations

from ragstrike.core.contracts.target_adapter import TargetAdapter, TargetDescriptor
from ragstrike.models.values.enums import Capability, Severity
from ragstrike.plugins.base.attack import (
    Analysis,
    BaseAttack,
    ExecutionRecord,
    Payload,
    Recommendation,
)
from ragstrike.sdk import (
    ResponseParser,
    ResultBuilder,
    SdkPayloadLoader,
    TargetRequestBuilder,
    fold_results,
)


class ExampleAttack(BaseAttack):
    """Sends one benign question and reports what came back. Teaches the SDK, attacks nothing."""

    plugin_id = "example-attack"
    plugin_name = "Example Attack (SDK demo)"
    plugin_version = "1.0.0"
    author = "RAGStrike"
    description = "Demonstrates the Attack SDK end to end. Not a security attack."
    category = "example"
    severity = Severity.INFO
    requires_capabilities = (Capability.CHAT,)
    tags = ("example", "sdk-demo")

    def payloads(self) -> list[Payload]:
        """Load payloads/example.yaml. Malformed entries would be skipped, not fatal --
        SdkPayloadLoader's whole point, though this pack ships none."""
        return SdkPayloadLoader(self.context.payload_dir).all()

    async def execute(
        self, target: TargetAdapter, payloads: list[Payload]
    ) -> list[ExecutionRecord]:
        # Stashed for analyze(), which does not receive `target` directly -- see ScanContext's
        # docstring for why that is intentional rather than an oversight.
        self._target_descriptor: TargetDescriptor = target.describe()

        records = []
        for payload in payloads:
            request = TargetRequestBuilder().with_prompt(payload.content).build()
            response = await target.chat(request)
            records.append(
                ExecutionRecord(
                    payload_id=payload.id,
                    prompt=payload.content,
                    response=response,
                    elapsed_ms=response.latency_ms,
                    error=response.error,
                )
            )
        return records

    def analyze(self, records: list[ExecutionRecord]) -> Analysis:
        target_url = getattr(self, "_target_descriptor", None)
        target_label = target_url.url if target_url else "unknown"

        results = []
        for record in records:
            excerpt = ResponseParser(record.response).excerpt(80)
            builder = (
                ResultBuilder(plugin_name=self.plugin_name, target=target_label)
                .from_execution_record(record)
                .with_notes(f"Answer excerpt: {excerpt!r}")
            )
            outcome = builder.passed() if record.ok else builder.errored()
            results.append(outcome.build())

        return fold_results(results, summary="SDK demonstration -- every response is reported")

    def recommendation(self, analysis: Analysis) -> Recommendation:  # noqa: ARG002
        # `analysis` is unused: the contract requires the parameter, but a demo plugin's advice
        # does not vary by outcome. A real plugin would branch on analysis.outcome here.
        return Recommendation(
            title="No action required",
            remediation="This is a demonstration plugin. It performs no security testing.",
            references=("docs/sdk-guide.md", "docs/plugin-development.md"),
            effort="LOW",
        )
