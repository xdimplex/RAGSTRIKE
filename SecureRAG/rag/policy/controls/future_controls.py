"""Declared-but-unimplemented controls: rate limiting, authentication, authorization.

WHY THESE EXIST AS EXPLICIT PLACEHOLDERS RATHER THAN AS NOTHING
    The brief asks for rate-limiting, authentication, and authorization *placeholders*. A placeholder
    is only useful if it is honest, so each of these:

    - declares itself with ``implemented = False``,
    - is **excluded from the composed chain** by :func:`~rag.policy.controls.build_controls`,
    - and appears in ``GET /health`` under ``declared_controls`` rather than under
      ``security_policies``.

    That last distinction is the whole point. A control listed as active but doing nothing is worse
    than no control at all: it tells an operator they are covered when they are not, and it would
    make SecureRAG's own health endpoint lie about its posture. Anything in this module reports the
    truth -- "designed, not built" -- and cannot be composed by accident.

WHY THEY ARE NOT SIMPLY LEFT OUT
    Because the shape of the eventual control is a design decision worth recording now, while the
    reasoning is fresh. Each class below documents what it will enforce and what has to exist first.
"""

from __future__ import annotations

from rag.policy.protocol import SecurityPolicy


class DeclaredControl(SecurityPolicy):
    """Base for a control that is designed but not yet built.

    Every hook is inherited unchanged from :class:`SecurityPolicy`, which means every one is a
    pass-through. Composing one of these would therefore be silent no-op coverage -- which is why
    ``build_controls`` refuses to.
    """

    #: Read by ``build_controls`` and by ``GET /health``. Never true in this module.
    implemented: bool = False

    #: What has to exist before this control can be built.
    blocked_on: str = ""


class RateLimiter(DeclaredControl):
    """Per-client request throttling.

    **Will enforce:** a token bucket per client identity across ``/chat`` and ``/upload``, with a
    separate, tighter budget for uploads because ingestion is the expensive path.

    **Blocked on:** a client identity to key the bucket on. Rate limiting by source IP is
    approximately useless on loopback, where every request comes from ``127.0.0.1`` -- so this
    control cannot be meaningfully built before authentication exists.

    The API-layer placeholder in ``backend/middleware/security.py`` records request counts today, so
    the eventual limiter has data to be tuned against.
    """

    name = "rate-limiter"
    description = "Per-client throttling. Declared, not implemented -- needs client identity."
    blocked_on = "authentication (no client identity to key a bucket on)"


class Authenticator(DeclaredControl):
    """Caller authentication.

    **Will enforce:** an API key or bearer token on every endpoint except ``/health``, resolved to a
    principal that the rest of the chain can reason about.

    **Blocked on:** a decision about identity storage that is out of scope for a local lab. Adding a
    hardcoded shared secret would be worse than nothing -- it would look like authentication in a
    screenshot and would be a single grep away in the repository.
    """

    name = "authenticator"
    description = "Caller authentication. Declared, not implemented -- lab runs unauthenticated."
    blocked_on = "an identity store; a hardcoded key would be theatre"


class Authorizer(DeclaredControl):
    """Per-principal document authorization.

    **Will enforce:** document-level access control at ``on_context_assembly``, so retrieval can
    only return chunks the caller is entitled to see. This is the control that turns
    :class:`~rag.policy.controls.retrieval_filter.RetrievalFilter` from a relevance filter into a
    security boundary.

    **Blocked on:** authentication, and a per-document owner column that the schema does not have.
    Adding the filter without the ownership data would silently return everything while appearing to
    enforce a policy.
    """

    name = "authorizer"
    description = "Per-principal document scoping. Declared, not implemented -- needs identity."
    blocked_on = "authentication, and per-document ownership in the schema"


#: Everything designed but not built. Surfaced by ``GET /health`` so the gap is visible in the
#: application's own output rather than only in its documentation.
DECLARED_CONTROLS: tuple[type[DeclaredControl], ...] = (RateLimiter, Authenticator, Authorizer)


def describe_declared() -> list[dict[str, str]]:
    """What ``GET /health`` reports under ``declared_controls``."""
    return [
        {
            "name": control.name,
            "description": control.description,
            "implemented": "false",
            "blocked_on": control.blocked_on,
        }
        for control in DECLARED_CONTROLS
    ]
