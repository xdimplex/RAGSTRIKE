"""``retry_async`` -- exponential backoff for a plugin's own I/O.

``execute()`` is the only ``BaseAttack`` method permitted to do I/O (ADR-004). When it does, and
the target is momentarily flaky, this is the retry loop a plugin reaches for instead of writing
its own ``for attempt in range(...)`` with ad-hoc sleeping.

**This retries on exceptions, never on response content.** A target that responded -- even with a
refusal, even with an answer that looks wrong -- is not a transport failure, and retrying it would
silently multiply the ``attempts`` a payload was actually sent, corrupting the
``successes / attempts`` exploitability measurement the scoring model depends on. Retry only what
raised; decide what a *response* means in ``analyze()``, never by resending it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
import random
from typing import TypeVar

from ragstrike.sdk.constants import (
    DEFAULT_RETRY_BACKOFF_S,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_MAX_BACKOFF_S,
)

log = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = DEFAULT_RETRY_COUNT,
    backoff_s: float = DEFAULT_RETRY_BACKOFF_S,
    max_backoff_s: float = DEFAULT_RETRY_MAX_BACKOFF_S,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Call *func* up to *attempts* times, backing off exponentially between failures.

    Args:
        func: A zero-argument async callable. Wrap what you are calling in a lambda or a small
            closure: ``retry_async(lambda: target.chat(request))``.
        attempts: Total attempts, including the first. ``1`` disables retrying.
        backoff_s: Delay before the second attempt. Doubles each subsequent attempt.
        max_backoff_s: Ceiling on the delay, so a flaky target cannot stall a scan indefinitely.
        retry_on: Exception types worth retrying. Defaults to everything; narrow this to
            connection/timeout errors specifically when you want a genuine parsing bug in your
            own code to fail immediately instead of being retried three times first.

    Returns:
        Whatever *func* returned on its first successful call.

    Raises:
        The last exception *func* raised, if every attempt failed.
    """
    if attempts < 1:
        raise ValueError(f"attempts must be at least 1, got {attempts}")

    delay = backoff_s
    last_error: BaseException | None = None

    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except retry_on as exc:
            last_error = exc
            if attempt == attempts:
                break
            # Jitter spreads retries so concurrent failures do not resynchronise. Not a
            # security use, so the standard PRNG is correct here.
            jittered = delay * (0.5 + random.random())  # noqa: S311  # nosec B311
            log.warning(
                "retrying after failure",
                extra={
                    "attempt": attempt,
                    "attempts": attempts,
                    "delay_s": round(jittered, 2),
                    "error": str(exc),
                },
            )
            await asyncio.sleep(jittered)
            delay = min(delay * 2, max_backoff_s)

    # A loop invariant, not input validation: the loop above cannot exit without recording an
    # error. Stripped under -O, which is fine -- the next line would raise anyway.
    assert last_error is not None  # nosec B101
    raise last_error


__all__ = ["retry_async"]
