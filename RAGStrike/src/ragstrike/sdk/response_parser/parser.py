"""``ResponseParser`` -- structured access to a :class:`TargetResponse`.

``TargetResponse`` (Phase 3) is deliberately minimal: ``text``, ``latency_ms``,
``retrieved_chunks``, ``sources``, ``session_id``, ``raw``, ``error``. Everything an adapter could
not map onto one of those named fields lands in ``raw`` verbatim, by design ("a detector or a
human reviewing a finding may need the part the adapter chose not to map").

``ResponseParser`` is the SDK's answer to "now what do I do with ``raw``." It provides the
extraction methods the Phase 5 brief names, each with an honestly documented answer for what
happens when the underlying data was never captured in the first place -- this parser never
invents data that is not there.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ragstrike.core.contracts.target_adapter import TargetResponse

#: Matches the "HTTP 404: ..." style prefix `target_adapters/fastapi/adapter.py` writes into
#: `TargetResponse.error` on a non-2xx response. There is currently no dedicated status_code
#: field on TargetResponse, so this is the only place a status code can come from today.
_STATUS_CODE_IN_ERROR = re.compile(r"^HTTP (\d{3}):")


class ResponseParser:
    """Wraps one :class:`TargetResponse` with named extraction methods.

    Stateless beyond the response it wraps -- constructing one is free, and a plugin can build a
    fresh parser per response without worrying about shared state.
    """

    def __init__(self, response: TargetResponse) -> None:
        self.response = response

    # -- the fields TargetResponse already names directly --------------------------------

    def text(self) -> str:
        """The model's answer, exactly as the adapter returned it. Never ``None`` -- empty
        string if there was nothing to say."""
        return self.response.text

    def chunks(self) -> list[dict[str, Any]]:
        """Retrieved context chunks, when the adapter and target both expose them. Empty list
        otherwise -- callers should not need to distinguish "not supported" from "supported but
        empty" here; that distinction belongs to capability negotiation, not response parsing."""
        return list(self.response.retrieved_chunks)

    def sources(self) -> list[str]:
        """Distinct source names the target says it used. Empty list if none were reported."""
        return list(self.response.sources)

    def session_id(self) -> str:
        return self.response.session_id

    def latency_ms(self) -> int:
        """Round-trip time, as measured by the adapter."""
        return self.response.latency_ms

    def error(self) -> str:
        """The adapter's error message, or ``""`` on a clean response. Prefer :meth:`ok`, which
        reads more naturally at a call site, for the boolean question."""
        return self.response.error

    def ok(self) -> bool:
        return self.response.ok

    # -- derived / best-effort extraction -------------------------------------------------

    def json(self) -> Any | None:
        """Parse ``text()`` as JSON, for targets that answer in a structured format.

        Returns ``None`` on anything that is not valid JSON -- most chat responses are prose, and
        that is not a parsing failure worth raising an exception over.
        """
        try:
            return json.loads(self.response.text)
        except (json.JSONDecodeError, TypeError):
            return None

    def raw(self) -> dict[str, Any]:
        """The adapter's unmapped payload, verbatim. Whatever did not fit a named field lives
        here -- inspect it when you need something this parser does not already extract."""
        return dict(self.response.raw)

    def metadata(self) -> dict[str, Any]:
        """Everything in ``raw()`` except the fields already surfaced by name elsewhere on this
        parser (``text``, ``sources``, chunk-shaped keys). A best-effort "the rest of it" view --
        exactly what counts as "already surfaced" depends on the adapter, so this is a heuristic,
        not a guarantee."""
        excluded = {"answer", "text", "sources", "retrieved_chunks", "session_id"}
        return {key: value for key, value in self.raw().items() if key not in excluded}

    def status_code(self) -> int | None:
        """Best-effort HTTP status code.

        There is no dedicated status field on ``TargetResponse`` today. This checks, in order:
        an explicit ``"status_code"`` key in ``raw()`` (for adapters that choose to add one), then
        the ``"HTTP NNN: ..."`` prefix ``FastAPIAdapter`` writes into ``error()`` on a non-2xx
        response. Returns ``None`` when neither is present -- which is the normal case for a
        successful response, since nothing captures the 200 explicitly today.
        """
        raw_value = self.raw().get("status_code")
        if isinstance(raw_value, int):
            return raw_value

        match = _STATUS_CODE_IN_ERROR.match(self.response.error)
        return int(match.group(1)) if match else None

    def headers(self) -> dict[str, str]:
        """Response headers, if the adapter captured them.

        ``FastAPIAdapter`` does not populate a ``"headers"`` key in ``raw`` today, so this
        returns ``{}`` against every adapter currently shipped. Provided for forward
        compatibility with an adapter that does.
        """
        headers = self.raw().get("headers")
        return dict(headers) if isinstance(headers, dict) else {}

    def citations(self) -> list[str]:
        """Best-effort citation list.

        Checks ``raw()`` for an explicit ``"citations"`` key first (some targets distinguish
        citations -- claims attributed to a source -- from the broader retrieval set). Falls back
        to :meth:`sources` when no such key exists. This is a convenience heuristic, not a
        detector: it does not verify that a citation is *grounded* in a retrieved chunk, only
        that the target claimed one. Grounding verification is analyzer work, out of scope here.
        """
        explicit = self.raw().get("citations")
        if isinstance(explicit, list):
            return [str(item) for item in explicit]
        return self.sources()

    def excerpt(self, length: int = 200) -> str:
        """The first *length* characters of :meth:`text`, for compact evidence records."""
        text = self.text()
        return text if len(text) <= length else text[: length - 1] + "…"
