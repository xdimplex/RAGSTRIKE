"""The process boundary.

THE CONSTRAINT THIS FILE EXISTS TO HONOUR
    ADR-010 and import-linter contract 3 forbid the dashboard from importing *any* engine package --
    and not only directly: the contract catches indirect chains too, so importing the reporting
    engine to reach a ``Finding`` breaks it just as surely as importing ``ragstrike.models``. The
    dashboard therefore reaches the engine across a process boundary or not at all.

    That is deliberate. Streamlit re-runs its whole script on every widget interaction; engine state
    held in that process is lost or duplicated. Forcing the UI through a network hop is also what
    keeps the API provably complete, because the reference UI cannot cheat.

THE CONTRACT THE CLIENT CODES AGAINST
    ``/api/v1`` exactly as SDD 22.2 specifies it -- same paths, same verbs, same error envelope.
    Writing against the published contract rather than against whatever a server happens to return
    is what makes the UI and the API independently replaceable.

TRANSPORTS
    ``http``  the real one, and the default.
    ``demo``  a deterministic in-memory fixture, opt-in only. It exists so the interface can be
              demonstrated, reviewed, and tested without a backend. It announces itself with a
              banner on every page: unlabelled sample data in a security tool is a hazard, because a
              screenshot of it is indistinguishable from a real assessment.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from ragstrike.dashboard.config import DashboardConfig
from ragstrike.dashboard.services.errors import (
    BackendUnavailableError,
    NotImplementedByBackendError,
    from_envelope,
)

#: The HTTP statuses this client treats specially. Named because ``status == 404`` in five months'
#: time reads as a magic number, and the *reason* each one is special is the interesting part.
HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
#: 501/502/503 all mean "the thing behind this address is not ready", which is the operator's
#: problem to fix rather than a request they got wrong.
HTTP_BACKEND_NOT_READY = (501, 502, 503)


@runtime_checkable
class BackendTransport(Protocol):
    """One method, because everything above it is REST.

    Services call :meth:`request` and get parsed JSON or an exception from
    :mod:`ragstrike.dashboard.services.errors`. No service knows whether it is talking to HTTP.
    """

    name: str

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> Any:
        """Perform one call. ``path`` is relative to the API base, e.g. ``/targets``."""
        ...

    def describe(self) -> str:
        """A one-line human description for the status bar."""
        ...

    def close(self) -> None:
        """Release any connection resources."""
        ...


class HttpTransport:
    """The real client: httpx against ``/api/v1``.

    The client is created lazily and kept for the life of the transport so connections are reused
    across the many small requests a dashboard makes on every re-run.
    """

    name = "http"

    def __init__(self, base_url: str, *, timeout_s: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import httpx

            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_s,
                follow_redirects=True,
                headers={"Accept": "application/json"},
            )
        return self._client

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> Any:
        import httpx

        client = self._ensure_client()
        try:
            response = client.request(
                method.upper(),
                path if path.startswith("/") else f"/{path}",
                params=dict(params) if params else None,
                json=dict(json) if json is not None else None,
            )
        except httpx.TimeoutException as exc:
            raise BackendUnavailableError(
                f"The backend did not answer within {self.timeout_s:g}s.",
                detail=str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            raise BackendUnavailableError(
                f"Could not reach the backend at {self.base_url}.",
                detail=str(exc),
            ) from exc

        return self._interpret(response)

    @staticmethod
    def _interpret(response: Any) -> Any:
        status = int(response.status_code)
        if status == HTTP_NO_CONTENT:
            return None

        try:
            body = response.json()
        except ValueError:
            body = None

        if status < HTTP_BAD_REQUEST:
            return body

        # A 404 carrying the documented error envelope is "this resource does not exist"; a bare 404
        # with no envelope is almost always "this route is not mounted", which is a different message
        # and a different operator response. Guessing wrong here is cheap and guessing at all is
        # unavoidable until the backend distinguishes them itself.
        if status == HTTP_NOT_FOUND and not isinstance(body, dict):
            raise NotImplementedByBackendError(
                f"{response.request.method} {response.request.url.path}"
            )
        if status in HTTP_BACKEND_NOT_READY:
            raise BackendUnavailableError(
                f"The backend reported it is not ready (HTTP {status}).",
                detail=str(body) if body else "",
            )
        raise from_envelope(status, body)

    def describe(self) -> str:
        return self.base_url

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def build_transport(config: DashboardConfig) -> BackendTransport:
    """Pick a transport from configuration.

    ``http`` is the default and the fallback for an unrecognised name. Demo mode is never inferred
    -- an operator gets sample data only by asking for it by name.
    """
    if config.transport == "demo":
        from ragstrike.dashboard.services.demo import DemoTransport

        return DemoTransport()
    return HttpTransport(config.api_base_url, timeout_s=config.request_timeout_s)
