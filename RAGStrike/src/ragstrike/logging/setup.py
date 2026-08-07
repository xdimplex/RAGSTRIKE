"""Logging setup, on Loguru.

Two things worth knowing about how this is wired.

**Application modules use the standard library, not Loguru directly.** Every module does
``log = logging.getLogger(__name__)``, and an ``InterceptHandler`` routes those records into Loguru.
That keeps the logging *backend* replaceable and, more importantly, keeps ``ragstrike.logging`` out
of the import graph of every module in the engine -- it is Layer 3 infrastructure, and Layer 2 code
importing it would break the dependency rule. Only the composition root (the CLI) imports this
module, once, at startup.

**Reserved keys.** Anything passed via ``extra=`` becomes a structured field, except that Python's
logging refuses to overwrite a ``LogRecord`` attribute and raises at the call site if you try. The
two that bite in practice are ``name`` and ``filename``, because they are the obvious words for a
plugin name and a document name. Use ``slug`` and ``source_name``.
"""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
import sys
from typing import Any

from loguru import logger

#: Attributes present on every LogRecord; anything else came from ``extra=``.
_STANDARD = frozenset(
    [
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    ]
)

_CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> <level>{level: <8}</level> "
    "<cyan>{extra[origin]}</cyan>  <level>{message}</level>{extra[context]}"
)


class InterceptHandler(logging.Handler):
    """Routes standard-library records into Loguru, preserving ``extra=`` fields."""

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - plumbing
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Walk out of the logging machinery so Loguru reports the real call site.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD and not key.startswith("_")
        }
        context = "  " + " ".join(f"{k}={v}" for k, v in fields.items()) if fields else ""

        logger.bind(origin=record.name, context=context, **fields).opt(
            depth=depth, exception=record.exc_info
        ).log(level, record.getMessage())


def setup_logging(
    *,
    log_dir: Path,
    level: str = "INFO",
    json_lines: bool = True,
    console: bool = True,
) -> None:
    """Configure logging for the process. Safe to call more than once.

    Args:
        log_dir: Where the rotating log files go.
        level: Root level. ``DEBUG`` includes full request and response bodies, which contain
            whatever a target disclosed -- fine locally, not something to enable habitually.
        json_lines: Write files as JSON lines, so ``jq`` works instead of regex.
        console: Also write human-readable output to stderr.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()

    if console:
        logger.add(
            sys.stderr,
            level=level,
            format=_CONSOLE_FORMAT,
            colorize=True,
            backtrace=False,
            diagnose=False,
        )

    logger.add(
        log_dir / "ragstrike.log",
        level=level,
        serialize=json_lines,
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        enqueue=True,
    )

    # Errors also get their own file, so a bug report has one obvious thing to attach.
    logger.add(
        log_dir / "errors.log",
        level="WARNING",
        serialize=json_lines,
        rotation="5 MB",
        retention=10,
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
    )

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(InterceptHandler())
    root.setLevel(level)

    # Informative at DEBUG, pure noise at INFO.
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def bind(**context: Any) -> None:
    """Attach context to every subsequent record in this process (e.g. ``scan_id``)."""
    logger.configure(extra=context)
