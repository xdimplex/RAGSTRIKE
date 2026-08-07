"""``FastAPIAdapter`` -- REST/JSON over HTTP.

The reference adapter, and the one that speaks to VulnerableRAG's ``POST /chat``.

It is **configuration-driven** rather than hardcoded to one API. Method, path, request shape,
response extraction, headers, authentication, and retry are all declared in the target's ``options``
block, so supporting a different bespoke API is a change to ``targets.yaml`` rather than a change to
this file -- the Open/Closed Principle applied to integration.

WHAT PHASE 16 ADDED, AND WHY
    The Phase 3 version handled VulnerableRAG and nothing else. It hardcoded ``POST``, flattened the
    prompt into a single top-level string field, resolved responses with a dotted-path helper that
    could not index a list, had no authentication of any kind, and did not retry.

    That was enough for a lab whose two halves it was written against, and not enough for the claim
    on the box: *any third-party RAG, without touching plugin code*. Four APIs -- ``POST /chat``,
    ``POST /generate``, ``POST /query``, ``POST /ask`` -- now differ only by configuration, and so do
    the ones that nest their prompt or answer inside a list.

WHAT IS AND IS NOT RETRIED
    Transport failures, 429, and 5xx. **Never a refusal, and never any other 4xx.**

    A target declining to answer is the most interesting result an attack pack can get. Retrying it
    would resend the payload, multiply the ``attempts`` a payload was actually sent, corrupt the
    ``successes / attempts`` exploitability ratio the scoring model depends on -- and increase the
    load on a system someone owns, for no information.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from ragstrike.core.config.models import RetrySettings
from ragstrike.core.contracts.target_adapter import (
    HealthResult,
    TargetRequest,
    TargetResponse,
)
from ragstrike.core.errors import (
    ConfigurationError,
    TargetProtocolError,
    TargetTimeoutError,
    TargetUnreachableError,
)
from ragstrike.models.entities.target import Target
from ragstrike.models.values.enums import Capability
from ragstrike.sdk.helpers.retry import retry_async
from ragstrike.target_adapters.base.base_target import BaseTarget
from ragstrike.target_adapters.fastapi.auth import build_auth
from ragstrike.target_adapters.fastapi.mapping import as_list, assign, extract

log = logging.getLogger(__name__)

#: Below this an HTTP response is a result; at or above it, an error.
_HTTP_ERROR = 400

#: Too Many Requests -- the one 4xx worth retrying, because it explicitly says "later".
_HTTP_TOO_MANY_REQUESTS = 429

#: At or above this the server is telling us it failed, not that we did.
_HTTP_SERVER_ERROR = 500

#: Methods a target may declare. GET is here for read-style query APIs; anything that could not
#: carry a prompt is not.
_METHODS = ("POST", "PUT", "PATCH", "GET")

_DEFAULTS: dict[str, Any] = {
    "method": "POST",
    "chat_path": "/chat",
    "health_path": "/health",
    "prompt_field": "message",
    "session_field": "session_id",
    "answer_path": "answer",
    "chunks_path": "retrieved_chunks",
    "sources_path": "sources",
    "session_path": "session_id",
}


class _RetryableStatusError(Exception):
    """Internal signal that a response should be retried rather than returned.

    Not a ``RAGStrikeError``: it never escapes this module. It exists so the retry helper -- which
    retries exceptions, never response content -- can be reused without teaching it about HTTP.
    """

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"HTTP {response.status_code}")
        self.response = response


class FastAPIAdapter(BaseTarget):
    """Talks to any JSON HTTP API; defaults tuned for VulnerableRAG."""

    adapter_name = "fastapi"
    adapter_version = "1.0.0"
    default_capabilities = (Capability.CHAT, Capability.RETURN_CHUNKS, Capability.LIST_SOURCES)

    def __init__(self, target: Target, *, retry: RetrySettings | None = None) -> None:
        super().__init__(target)
        self.options = {**_DEFAULTS, **target.options}
        self.retry = retry or RetrySettings()
        self.auth = build_auth(target.options, target_name=target.name)
        self._method = self._validated_method()
        self._client: httpx.AsyncClient | None = None

    def _validated_method(self) -> str:
        method = str(self.options["method"]).upper()
        if method not in _METHODS:
            raise ConfigurationError(
                f"Target {self.target.name!r}: unsupported HTTP method {method!r}.",
                hint=f"Supported methods: {', '.join(_METHODS)}.",
            )
        return method

    # -- lifecycle --------------------------------------------------------------------------

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"User-Agent": f"RAGStrike/{self.adapter_version}"}
            headers.update(self.options.get("headers") or {})
            # Auth last: a target must not be able to unset its own credential with a stray
            # `headers: {Authorization: ""}` entry.
            headers.update(self.auth.headers())
            self._client = httpx.AsyncClient(
                base_url=self.target.url,
                timeout=self.target.timeout_s,
                headers=headers,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # -- contract ---------------------------------------------------------------------------

    async def health_check(self) -> HealthResult:
        """Probe the target. Never raises -- a health check reports, it does not propagate."""
        started = time.perf_counter()
        try:
            response = await self.client.get(str(self.options["health_path"]), timeout=10)
        except httpx.ConnectError as exc:
            return HealthResult(
                reachable=False, detail=f"Cannot connect to {self.target.url}: {exc}"
            )
        except httpx.TimeoutException:
            return HealthResult(reachable=False, detail="Health check timed out.")
        except httpx.HTTPError as exc:  # pragma: no cover - defensive
            return HealthResult(reachable=False, detail=f"{type(exc).__name__}: {exc}")

        latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code >= _HTTP_ERROR:
            return HealthResult(
                reachable=False,
                latency_ms=latency_ms,
                detail=f"Health endpoint returned {response.status_code}.",
            )

        detail = ""
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = str(body.get("status", "") or body.get("profile", ""))
        except ValueError:
            detail = "reachable (non-JSON health response)"
        return HealthResult(reachable=True, latency_ms=latency_ms, detail=detail)

    async def chat(self, request: TargetRequest) -> TargetResponse:
        """Send one prompt.

        Raises:
            TargetUnreachableError: Connection refused, or refused on every retry.
            TargetTimeoutError: No response in time.
            TargetProtocolError: Responded, but not in a shape this adapter understands.
        """
        payload = self._build_payload(request)
        timeout = request.timeout_s or self.target.timeout_s
        started = time.perf_counter()

        try:
            response = await retry_async(
                lambda: self._send(payload, timeout=timeout),
                attempts=self.retry.max_attempts,
                backoff_s=self.retry.backoff_base_s,
                max_backoff_s=self.retry.backoff_max_s,
                retry_on=(httpx.ConnectError, httpx.TimeoutException, _RetryableStatusError),
            )
        except httpx.ConnectError as exc:
            raise TargetUnreachableError(
                f"Cannot connect to {self.target.url}.",
                hint="Is the target running? Check the url in configs/targets.yaml.",
            ) from exc
        except httpx.TimeoutException as exc:
            raise TargetTimeoutError(
                f"{self.target.name!r} did not respond within {timeout}s.",
                hint="Raise the target's timeout, or use a smaller model.",
            ) from exc
        except _RetryableStatusError as exc:
            # Retries exhausted on a 429/5xx. The status is data, not a transport failure: an
            # attack that reliably provokes a 500 has learned something worth reporting.
            response = exc.response

        latency_ms = int((time.perf_counter() - started) * 1000)

        if response.status_code >= _HTTP_ERROR:
            return TargetResponse(
                text="",
                latency_ms=latency_ms,
                raw=_safe_json(response),
                error=f"HTTP {response.status_code}: {response.text[:300]}",
            )

        return self._parse(response, latency_ms=latency_ms)

    # -- internals --------------------------------------------------------------------------

    def _build_payload(self, request: TargetRequest) -> dict[str, Any]:
        """Shape the request body from the target's field mapping.

        Dotted field names nest, so ``prompt_field: "input.query"`` produces
        ``{"input": {"query": ...}}`` -- which is what makes an API that wraps its prompt a
        configuration change rather than a code change.
        """
        payload: dict[str, Any] = {}
        assign(payload, str(self.options["prompt_field"]), request.prompt)
        if request.session_id:
            assign(payload, str(self.options["session_field"]), request.session_id)
        extra = self.options.get("extra_body") or {}
        if extra:
            payload.update(extra)
        return payload

    async def _send(
        self,
        payload: dict[str, Any],
        *,
        timeout: int,  # noqa: ASYNC109
    ) -> httpx.Response:
        """One attempt. Raises :class:`_RetryableStatusError` for statuses worth another try.

        ASYNC109 suggests ``asyncio.timeout`` instead of a ``timeout`` parameter. Not here: this
        value is handed to ``httpx``, which enforces it per-phase (connect, read, write, pool) and
        closes the connection cleanly on expiry. An ``asyncio.timeout`` wrapper would cancel the
        task mid-request and leak the socket back to the pool in an undefined state.
        """
        path = str(self.options["chat_path"])
        if self._method == "GET":
            # A GET target takes its prompt in the query string; a nested mapping cannot be
            # expressed there, so the flat form is the only one that makes sense.
            response = await self.client.get(path, params=_flatten(payload), timeout=timeout)
        else:
            response = await self.client.request(self._method, path, json=payload, timeout=timeout)

        if (
            response.status_code >= _HTTP_SERVER_ERROR
            or response.status_code == _HTTP_TOO_MANY_REQUESTS
        ):
            raise _RetryableStatusError(response)
        return response

    def _parse(self, response: httpx.Response, *, latency_ms: int) -> TargetResponse:
        try:
            body = response.json()
        except ValueError as exc:
            raise TargetProtocolError(
                f"{self.target.name!r} returned non-JSON on {self.options['chat_path']}.",
                hint="This adapter expects a JSON API. Check the target's chat_path.",
            ) from exc

        text = extract(body, str(self.options["answer_path"]))
        if text is None:
            keys = ", ".join(sorted(body)) if isinstance(body, dict) else type(body).__name__
            raise TargetProtocolError(
                f"No {self.options['answer_path']!r} field in the response from "
                f"{self.target.name!r}.",
                hint=(
                    "Set options.answer_path in configs/targets.yaml to the field holding the "
                    f"answer -- a dotted path, or JSONPath if it starts with '$'. "
                    f"Response keys were: {keys}."
                ),
            )

        return TargetResponse(
            text=str(text),
            latency_ms=latency_ms,
            retrieved_chunks=as_list(extract(body, str(self.options["chunks_path"]))),
            sources=[str(s) for s in as_list(extract(body, str(self.options["sources_path"])))],
            session_id=str(extract(body, str(self.options["session_path"])) or ""),
            raw=body if isinstance(body, dict) else {"body": body},
        )


def _flatten(payload: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Collapse a nested body into query parameters, joining keys with a dot."""
    flat: dict[str, str] = {}
    for key, value in payload.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, prefix=f"{name}."))
        else:
            flat[name] = str(value)
    return flat


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {"body": response.text[:1000]}
    return body if isinstance(body, dict) else {"body": body}
