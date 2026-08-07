"""``Timer`` -- measuring elapsed time without every plugin reaching for ``time.perf_counter``
by hand.

The engine already times things itself (``scheduler/scan_scheduler.py`` times each plugin's whole
run). ``Timer`` is for timing *within* a plugin's own ``execute()`` -- one payload, one retry
attempt, one parsing step -- independent of and in addition to the engine's own bookkeeping.
"""

from __future__ import annotations

import time
from types import TracebackType


class Timer:
    """A stopwatch, usable as a context manager or by hand.

    Context manager::

        with Timer() as timer:
            await do_something()
        print(timer.elapsed_ms)

    By hand::

        timer = Timer()
        timer.start()
        ...
        timer.stop()
        print(timer.elapsed_ms)

    ``elapsed_ms`` is readable while the timer is still running -- it returns time-so-far rather
    than raising, which is convenient for logging progress mid-operation.
    """

    def __init__(self) -> None:
        self._start: float | None = None
        self._end: float | None = None

    def start(self) -> Timer:
        self._start = time.perf_counter()
        self._end = None
        return self

    def stop(self) -> Timer:
        if self._start is None:
            raise RuntimeError("Timer.stop() called before start().")
        self._end = time.perf_counter()
        return self

    @property
    def running(self) -> bool:
        return self._start is not None and self._end is None

    @property
    def elapsed_ms(self) -> int:
        if self._start is None:
            return 0
        end = self._end if self._end is not None else time.perf_counter()
        return int((end - self._start) * 1000)

    def __enter__(self) -> Timer:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()


__all__ = ["Timer"]
