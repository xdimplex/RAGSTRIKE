"""The HTTP surface: ``/api/v1``.

Empty until Phase 16 -- routing, schemas, streaming, and middleware were four empty packages, and
the dashboard reported ``BACKEND OFFLINE`` because there was nothing behind the address it called.

The dashboard was already written against this contract through a transport Protocol (ADR-021), so
implementing it required no dashboard change at all. That was the point of building the client
against the published contract rather than against whatever a server happened to return.
"""

from ragstrike.api.app import API_PREFIX, create_app, run

__all__ = ["API_PREFIX", "create_app", "run"]
