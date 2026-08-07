"""Logging configuration.

Writes to ``logs/`` and to the console. Four concerns land in the log and are required by Phase 2:
document uploads, questions, retrieved chunks, and errors -- plus API requests and response times
from the access middleware.

Records are JSON lines. Any keyword passed via ``extra=`` becomes a top-level field, so
``log.info("question answered", extra={"elapsed_ms": 412})`` is queryable with ``jq`` rather than
regex.

There is no redaction here, deliberately. Question text and answer text reach the log verbatim. In a
production application that would be a serious mistake; noticing that it is missing is part of what
this lab teaches. The corpus is synthetic precisely so it is safe.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import UTC, datetime
from pathlib import Path

#: Attributes present on every LogRecord. Anything else came from ``extra=`` and is worth emitting.
#:
#: These names are also **reserved**: passing any of them in ``extra=`` makes Python's logging raise
#: ``KeyError: Attempt to overwrite ... in LogRecord`` at the call site. ``filename`` and ``name``
#: are the two that bite in practice, because they are the obvious words for a document name and a
#: migration name. Use ``source_name`` and ``migration`` instead.
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


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """Short, readable lines for a terminal."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)s  %(message)s", "%H:%M:%S")


def setup_logging(log_dir: Path, *, level: str = "INFO", console: bool = True) -> None:
    """Configure root logging. Safe to call more than once.

    Args:
        log_dir: Directory for the rotating log files.
        level: Root level. ``DEBUG`` also writes full prompts, which contain whatever the corpus
            contains -- fine in a lab, not something to enable habitually.
        console: Also log to stderr.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(level.upper())

    for handler in list(root.handlers):
        root.removeHandler(handler)

    app_file = logging.handlers.RotatingFileHandler(
        log_dir / "vulnerable-rag.log", maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    app_file.setFormatter(JsonFormatter())
    app_file.setLevel(level.upper())
    root.addHandler(app_file)

    # Errors also go to their own file, so a bug report has one obvious thing to attach.
    error_file = logging.handlers.RotatingFileHandler(
        log_dir / "errors.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    error_file.setFormatter(JsonFormatter())
    error_file.setLevel(logging.WARNING)
    root.addHandler(error_file)

    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(ConsoleFormatter())
        stream.setLevel(level.upper())
        root.addHandler(stream)

    # These are informative at DEBUG and pure noise at INFO.
    for noisy in ("httpx", "httpcore", "chromadb", "urllib3", "watchfiles"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
