"""
Enhanced logging configuration with JSON structured logging and request ID tracing.
"""

import json
import logging
import sys
import time
import traceback
import uuid
from contextvars import ContextVar
from typing import Optional

from app.core.config import settings

# Context variables for request tracking
request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
request_start_time: ContextVar[Optional[float]] = ContextVar(
    "request_start_time", default=None
)


class RequestIDFilter(logging.Filter):
    """Add request ID and duration to log records."""

    def filter(self, record):
        record.request_id = request_id.get() or "no-request-id"
        record.duration_ms = 0
        if request_start_time.get():
            record.duration_ms = int((time.time() - request_start_time.get()) * 1000)
        return True


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "no-request-id"),
            "duration_ms": getattr(record, "duration_ms", 0),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            log_entry["stack_trace"] = traceback.format_exc()

        # No indentation in production for smaller logs
        return json.dumps(log_entry, indent=2 if settings.DEBUG else None)


class StructuredFormatter(logging.Formatter):
    """Human-readable structured formatter."""

    def format(self, record):
        base_message = super().format(record)
        request_id_str = getattr(record, "request_id", "no-request-id")
        duration_ms = getattr(record, "duration_ms", 0)

        structured_message = f"[{request_id_str}] {base_message}"
        if duration_ms > 0:
            structured_message += f" [duration: {duration_ms}ms]"

        return structured_message


def setup_logging(log_level: Optional[str] = None) -> logging.Logger:
    """
    Setup application logging.

    Args:
        log_level: Optional log level override

    Returns:
        Configured logger instance
    """
    if log_level is None:
        log_level = settings.LOG_LEVEL

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    logger = logging.getLogger(settings.APP_NAME)
    logger.setLevel(numeric_level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.addFilter(RequestIDFilter())

    # Choose formatter
    if settings.LOG_FORMAT == "json":
        formatter = JSONFormatter()
    else:
        formatter = StructuredFormatter(
            "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def set_request_context(request_id_str: Optional[str] = None) -> str:
    """
    Set request context for logging.

    Args:
        request_id_str: Optional request ID

    Returns:
        The request ID used
    """
    if not request_id_str:
        request_id_str = str(uuid.uuid4())

    request_id.set(request_id_str)
    request_start_time.set(time.time())
    return request_id_str


def clear_request_context():
    """Clear request context."""
    request_id.set(None)
    request_start_time.set(None)


def get_request_id() -> Optional[str]:
    """Get current request ID."""
    return request_id.get()


class RequestContextManager:
    """Context manager for request ID tracking."""

    def __init__(self, request_id_str: Optional[str] = None):
        self.request_id_str = request_id_str
        self.original_request_id = None
        self.original_start_time = None

    async def __aenter__(self):
        """Enter context and set request ID."""
        self.original_request_id = request_id.get()
        self.original_start_time = request_start_time.get()
        set_request_context(self.request_id_str)
        return get_request_id()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context and restore previous state."""
        request_id.set(self.original_request_id)
        request_start_time.set(self.original_start_time)
        # Return False to propagate exceptions
        return False


# Global logger instance
logger = setup_logging()
