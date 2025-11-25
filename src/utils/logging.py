"""
Structured JSON logging configuration.

This module provides structured logging with JSON output for better
observability and integration with log aggregation systems.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from src.config import get_settings


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON.

    This formatter converts log records to structured JSON format,
    including timestamp, level, message, and contextual information.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON string representation of the log record
        """
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_obj["extra"] = record.extra_fields

        return json.dumps(log_obj)


class ContextLogger:
    """
    Logger wrapper that supports adding contextual information.

    This class wraps the standard logger and allows adding extra
    context fields to log messages.
    """

    def __init__(self, name: str) -> None:
        """
        Initialize the context logger.

        Args:
            name: Logger name (typically __name__)
        """
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}

    def add_context(self, **kwargs: Any) -> None:
        """
        Add context fields to all subsequent log messages.

        Args:
            **kwargs: Key-value pairs to add to context
        """
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """Clear all context fields."""
        self.context.clear()

    def _log_with_context(
        self,
        level: int,
        message: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Log a message with context.

        Args:
            level: Log level (logging.INFO, etc.)
            message: Log message
            *args: Positional arguments for message formatting
            **kwargs: Additional context for this specific log
        """
        extra_fields = {**self.context, **kwargs}
        extra = {"extra_fields": extra_fields} if extra_fields else {}
        self.logger.log(level, message, *args, extra=extra)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        self._log_with_context(logging.DEBUG, message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log an info message."""
        self._log_with_context(logging.INFO, message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        self._log_with_context(logging.WARNING, message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message."""
        self._log_with_context(logging.ERROR, message, *args, **kwargs)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a critical message."""
        self._log_with_context(logging.CRITICAL, message, *args, **kwargs)

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log an exception with traceback."""
        self.logger.exception(message, *args, extra={"extra_fields": self.context})


def setup_logging() -> None:
    """
    Configure logging for the application.

    This function sets up structured JSON logging with the appropriate
    log level from configuration.
    """
    settings = get_settings()

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler with JSON formatter
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Set lower level for psycopg2 to reduce noise
    logging.getLogger("psycopg2").setLevel(logging.WARNING)

    # Log startup message
    logger = get_logger(__name__)
    logger.info(
        "Logging configured",
        log_level=settings.log_level,
        server_name=settings.server_name,
        server_version=settings.server_version,
    )


def get_logger(name: str) -> ContextLogger:
    """
    Get a context-aware logger for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        ContextLogger instance
    """
    return ContextLogger(name)
