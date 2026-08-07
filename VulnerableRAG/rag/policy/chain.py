"""Ordered composition of security policies.

The chain runs each policy in order at each hook point, threading the output of one into the input
of the next. A chain with no policies is a set of pass-through functions -- which is exactly what
VulnerableRAG runs.

The pipeline calls the chain unconditionally at all five hook points. There is no
``if self.policies:`` shortcut and no ``if profile == "secure"`` branch anywhere: the *only* thing
that distinguishes the two applications is what was put in this list at construction time.
"""

from __future__ import annotations

import logging

from rag.models import Chunk, RetrievedChunk
from rag.policy.hooks import (
    ChunkContext,
    ContextAssemblyContext,
    HookPoint,
    IngestContext,
    PromptContext,
    ResponseContext,
)
from rag.policy.protocol import SecurityPolicy

log = logging.getLogger(__name__)


class SecurityPolicyChain:
    """A list of policies applied in order at every hook point."""

    def __init__(self, policies: list[SecurityPolicy] | None = None) -> None:
        self.policies: list[SecurityPolicy] = list(policies or [])

    def __len__(self) -> int:
        return len(self.policies)

    def __bool__(self) -> bool:
        return bool(self.policies)

    def describe(self) -> list[dict[str, str]]:
        """Used by ``GET /health`` and the System Status page.

        An empty list here is the honest, visible signal that no defences are active.
        """
        return [{"name": p.name, "description": p.description} for p in self.policies]

    # -- hook dispatch ----------------------------------------------------------------------

    def on_ingest(self, ctx: IngestContext) -> str:
        for policy in self.policies:
            ctx.text = policy.on_ingest(ctx)
            self._trace(policy, HookPoint.ON_INGEST)
        return ctx.text

    def on_chunk(self, ctx: ChunkContext) -> list[Chunk]:
        for policy in self.policies:
            ctx.chunks = policy.on_chunk(ctx)
            self._trace(policy, HookPoint.ON_CHUNK)
        return ctx.chunks

    def on_context_assembly(self, ctx: ContextAssemblyContext) -> list[RetrievedChunk]:
        for policy in self.policies:
            ctx.retrieved = policy.on_context_assembly(ctx)
            self._trace(policy, HookPoint.ON_CONTEXT_ASSEMBLY)
        return ctx.retrieved

    def on_prompt_build(self, ctx: PromptContext) -> str:
        for policy in self.policies:
            ctx.prompt = policy.on_prompt_build(ctx)
            self._trace(policy, HookPoint.ON_PROMPT_BUILD)
        return ctx.prompt

    def on_response(self, ctx: ResponseContext) -> str:
        for policy in self.policies:
            ctx.answer = policy.on_response(ctx)
            self._trace(policy, HookPoint.ON_RESPONSE)
        return ctx.answer

    @staticmethod
    def _trace(policy: SecurityPolicy, hook: HookPoint) -> None:
        log.debug("policy applied", extra={"policy": policy.name, "hook": hook.value})
