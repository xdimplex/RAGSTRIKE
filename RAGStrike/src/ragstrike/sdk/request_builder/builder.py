"""``TargetRequestBuilder`` -- fluent construction of :class:`TargetRequest`.

**There is exactly one operation in the current target contract: ``chat()``.** Phase 3's
:class:`~ragstrike.core.contracts.target_adapter.TargetAdapter` protocol does not expose "GET" or
"POST" -- a RAG target is not a REST API from a plugin's point of view, it is a chat endpoint the
adapter mediates. Plugins never make their own HTTP calls: only the adapter, injected by the
engine, is allowed to reach the network (Phase 4's dependency-injection rule). So "construct HTTP
requests, support GET/POST" from the Phase 5 brief is satisfied here as *building the one request
type the engine's contract actually defines*, well, rather than as raw HTTP verbs a plugin would
need its own client for.

What this builder does today, backed by real adapter behaviour:

* ``.with_prompt()``, ``.with_session()``, ``.with_correlation_id()`` -- set the corresponding
  :class:`TargetRequest` field directly.
* ``.with_timeout()`` -- sets ``timeout_s``, which :class:`~ragstrike.target_adapters.fastapi.adapter.FastAPIAdapter`
  actually reads (confirmed: it is passed straight into the ``httpx`` call).

What this builder accepts but the shipped adapter does not yet act on -- **documented, not
pretended**:

* ``.with_header()``, ``.with_auth()``, ``.with_cookie()`` -- stored under
  ``TargetRequest.metadata``, which the port's own docstring calls "opaque passthrough... the
  engine never inspects." ``FastAPIAdapter.chat()`` does not read ``request.metadata`` today. A
  future adapter that wants per-request headers, auth, or cookies has a place to read them from
  without another change to the ``TargetRequest`` dataclass itself.

Retries, streaming, and multipart are not builder methods at all -- see
:class:`RawRequestSpec` below for why, and where that functionality is actually planned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self

from ragstrike.core.contracts.target_adapter import TargetRequest


class TargetRequestBuilder:
    """Fluent builder for :class:`~ragstrike.core.contracts.target_adapter.TargetRequest`.

    Every method returns ``self``, so a plugin can chain::

        request = (
            TargetRequestBuilder()
            .with_prompt(payload.content)
            .with_session(session_id)
            .with_timeout(30)
            .build()
        )
        response = await target.chat(request)

    Building performs no I/O -- it only assembles the value object the adapter's ``chat()``
    accepts. Sending is always the plugin's own explicit ``await target.chat(...)`` call,
    consistent with ``execute()`` being the one place the ``BaseAttack`` contract permits I/O.
    """

    def __init__(self) -> None:
        self._prompt: str = ""
        self._session_id: str | None = None
        self._timeout_s: int | None = None
        self._correlation_id: str = ""
        self._metadata: dict[str, Any] = {}

    def with_prompt(self, prompt: str) -> Self:
        self._prompt = prompt
        return self

    def with_session(self, session_id: str | None) -> Self:
        self._session_id = session_id
        return self

    def with_timeout(self, seconds: int) -> Self:
        self._timeout_s = seconds
        return self

    def with_correlation_id(self, correlation_id: str) -> Self:
        self._correlation_id = correlation_id
        return self

    def with_metadata(self, key: str, value: Any) -> Self:
        """Attach one opaque key/value pair. See the module docstring for what reads this today."""
        self._metadata[key] = value
        return self

    def with_header(self, name: str, value: str) -> Self:
        """Stage a header under ``metadata["headers"]``. Not yet consumed by the shipped adapter
        -- see the module docstring."""
        headers = self._metadata.setdefault("headers", {})
        headers[name] = value
        return self

    def with_cookie(self, name: str, value: str) -> Self:
        """Stage a cookie under ``metadata["cookies"]``. Not yet consumed by the shipped adapter."""
        cookies = self._metadata.setdefault("cookies", {})
        cookies[name] = value
        return self

    def with_auth(self, scheme: str, credential: str) -> Self:
        """Stage an ``Authorization``-style credential under ``metadata["auth"]``.

        Stored as ``{"scheme": scheme, "credential": credential}``, e.g.
        ``with_auth("Bearer", token)``. Not yet consumed by the shipped adapter.
        """
        self._metadata["auth"] = {"scheme": scheme, "credential": credential}
        return self

    def build(self) -> TargetRequest:
        """Assemble the request.

        ``timeout_s`` is left as ``None`` when the caller did not set one, which is what makes the
        per-target ``timeout:`` in ``configs/targets.yaml`` mean anything.

        This used to substitute ``DEFAULT_TIMEOUT_S`` (60) here. The adapter resolves the timeout as
        ``request.timeout_s or self.target.timeout_s``, so a request that always carried a number
        meant the target's configured value could NEVER apply -- every SDK-built attack payload was
        silently capped at 60s no matter what the operator wrote in targets.yaml. Against a
        CPU-hosted model, where one generation takes 65-120s, that capped it below a single answer
        and the whole pack died with "did not respond within 60s".

        ``None`` is the documented "unset" of :class:`TargetRequest`, and deferring to the target is
        what the adapter was already written to do.
        """
        return TargetRequest(
            prompt=self._prompt,
            session_id=self._session_id,
            metadata=dict(self._metadata),
            timeout_s=self._timeout_s,
            correlation_id=self._correlation_id,
        )


# --------------------------------------------------------------------------------------------
# Architecture only, below this line. Nothing here is wired to anything.
# --------------------------------------------------------------------------------------------


class HttpMethod(StrEnum):
    """The HTTP verbs a future raw-request capability would need to distinguish.

    Not used by :class:`TargetRequestBuilder` or by any adapter today -- the target contract has
    exactly one operation (``chat``), issued as a POST by
    :class:`~ragstrike.target_adapters.fastapi.adapter.FastAPIAdapter`, and no plugin has a
    sanctioned way to issue an HTTP request of its own (Phase 4's dependency-injection rule keeps
    all network access behind the adapter).
    """

    GET = "GET"
    POST = "POST"


@dataclass(frozen=True, slots=True)
class RawRequestSpec:
    """Architecture placeholder for a future "raw HTTP" attack capability.

    Some attack techniques legitimately need to reach an endpoint the ``chat()`` contract cannot
    express -- probing an auxiliary API the target exposes, for instance. That capability does not
    exist yet: it would need a new :class:`~ragstrike.models.values.enums.Capability` value, an
    adapter method beyond ``chat()``, and a scheduler-level decision about how such a case gets
    scored. All of that is out of scope for Phase 5, which is not permitted to touch the target
    contract or the scheduler.

    This dataclass exists so that when that capability *is* built, its request shape does not need
    to be designed from scratch -- the fields below are the ones every raw-HTTP client needs
    regardless of when authentication, streaming, and multipart support (also listed as future
    work in the Phase 5 brief) actually land:

    Attributes:
        method: GET or POST today; the enum leaves room for more without a breaking change.
        path: Relative to the target's base URL.
        headers: Request headers.
        params: Query string parameters (GET).
        body: JSON-serializable request body (POST).
        files: Reserved for multipart support. Empty today.
        stream: Reserved for streaming support. Ignored today.
        retries: Reserved for a future per-request retry override. Ignored today -- retry policy
            currently lives entirely in ``core/executor`` design notes, not in any built
            component.
    """

    method: HttpMethod = HttpMethod.POST
    path: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] | None = None
    files: dict[str, bytes] = field(default_factory=dict)
    stream: bool = False
    retries: int | None = None


__all__ = ["HttpMethod", "RawRequestSpec", "TargetRequestBuilder"]
