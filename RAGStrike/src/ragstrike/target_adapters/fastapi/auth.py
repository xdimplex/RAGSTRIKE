"""Target authentication.

WHY CREDENTIALS COME FROM THE ENVIRONMENT AND NOWHERE ELSE
    ``targets.yaml`` is committed. Every configuration file in this repository carries a comment
    saying not to put a secret in it, and a comment is not a control.

    So the schema has no field a secret fits in. A target declares *which environment variable*
    holds its credential; the value is read at request time and never written to a log, a report, a
    scan snapshot, or an error message. Someone who wants to commit a token to this repository has
    to work at it.

WHY A MISSING VARIABLE IS A STARTUP ERROR
    A target configured for bearer auth whose token is absent would otherwise send unauthenticated
    requests, collect a wall of 401s, and report them as findings -- "the target refused every
    payload" is what a hardened system looks like. Failing at construction makes the real problem
    visible in one line instead of buried in a scan report.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import os
from typing import Any

from ragstrike.core.errors import ConfigurationError

#: Schemes a target may declare.
BEARER = "bearer"
API_KEY = "api_key"
BASIC = "basic"
NONE = "none"

_SCHEMES = (BEARER, API_KEY, BASIC, NONE)

#: Where an api_key lands when the target does not say.
_DEFAULT_API_KEY_HEADER = "X-API-Key"


@dataclass(frozen=True, slots=True)
class TargetAuth:
    """A resolved credential, ready to become a header."""

    scheme: str = NONE
    header: str = ""
    value: str = ""

    @property
    def active(self) -> bool:
        return self.scheme != NONE and bool(self.value)

    def headers(self) -> dict[str, str]:
        """The header(s) this credential contributes. Empty when no auth is configured."""
        return {self.header: self.value} if self.active else {}

    def __repr__(self) -> str:
        """Never render the credential.

        ``repr`` reaches logs, tracebacks, and debugger output. A dataclass would print the token by
        default, which is exactly the leak this module exists to prevent.
        """
        return f"TargetAuth(scheme={self.scheme!r}, header={self.header!r}, value=***)"


def build_auth(options: dict[str, Any], *, target_name: str) -> TargetAuth:
    """Resolve the ``auth`` block of a target's options.

    Expected shape::

        options:
          auth:
            type: bearer            # bearer | api_key | basic | none
            env: MY_TARGET_TOKEN    # the variable holding the credential
            header: X-API-Key       # api_key only; defaults to X-API-Key
            username_env: MY_USER   # basic only

    Raises:
        ConfigurationError: Unknown scheme, missing ``env``, or an unset variable.
    """
    block = options.get("auth")
    if not block:
        return TargetAuth()
    if not isinstance(block, dict):
        raise ConfigurationError(
            f"Target {target_name!r}: 'auth' must be a mapping.",
            hint="See the auth block in configs/targets/vulnerable-rag.example.yaml.",
        )

    scheme = str(block.get("type", NONE)).lower()
    if scheme not in _SCHEMES:
        raise ConfigurationError(
            f"Target {target_name!r}: unknown auth type {scheme!r}.",
            hint=f"Valid types: {', '.join(_SCHEMES)}.",
        )
    if scheme == NONE:
        return TargetAuth()

    secret = _from_env(block.get("env"), target_name=target_name, field="env")

    if scheme == BEARER:
        return TargetAuth(scheme=BEARER, header="Authorization", value=f"Bearer {secret}")

    if scheme == API_KEY:
        header = str(block.get("header") or _DEFAULT_API_KEY_HEADER)
        return TargetAuth(scheme=API_KEY, header=header, value=secret)

    username = _from_env(block.get("username_env"), target_name=target_name, field="username_env")
    encoded = base64.b64encode(f"{username}:{secret}".encode()).decode("ascii")
    return TargetAuth(scheme=BASIC, header="Authorization", value=f"Basic {encoded}")


def _from_env(name: Any, *, target_name: str, field: str) -> str:
    if not name:
        raise ConfigurationError(
            f"Target {target_name!r}: auth requires '{field}' naming an environment variable.",
            hint="Credentials are read from the environment; targets.yaml is committed.",
        )
    value = os.environ.get(str(name), "")
    if not value:
        raise ConfigurationError(
            f"Target {target_name!r}: environment variable {name!r} is not set.",
            hint=(
                f"Export {name} before scanning. Without it every request would be "
                "unauthenticated, and a wall of 401s reads exactly like a hardened target."
            ),
        )
    return value


__all__ = ["API_KEY", "BASIC", "BEARER", "NONE", "TargetAuth", "build_auth"]
