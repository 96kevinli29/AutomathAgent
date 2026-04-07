"""Structured logging setup."""

from __future__ import annotations

import structlog
from pathlib import Path


def setup_logging(log_dir: str | Path | None = None, json_output: bool = True) -> None:
    """Configure structlog for the application."""
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
