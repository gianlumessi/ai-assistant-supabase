"""Centralized logging configuration with structured logging support."""

import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict
from contextvars import ContextVar

# Context variable for tracking request ID across async calls
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
website_id_var: ContextVar[str] = ContextVar('website_id', default='')


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add request context if available
        request_id = request_id_var.get()
        if request_id:
            log_data['request_id'] = request_id

        website_id = website_id_var.get()
        if website_id:
            log_data['website_id'] = website_id

        # Add extra fields from record
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        level = record.levelname
        name = record.name
        message = record.getMessage()

        # Add request context if available
        context_parts = []
        request_id = request_id_var.get()
        if request_id:
            context_parts.append(f'req={request_id[:8]}')

        website_id = website_id_var.get()
        if website_id:
            context_parts.append(f'site={website_id[:8]}')

        context = f' [{" ".join(context_parts)}]' if context_parts else ''

        log_line = f'{timestamp} {level:8} {name:30}{context} {message}'

        if record.exc_info:
            log_line += '\n' + self.formatException(record.exc_info)

        return log_line


def setup_logging(use_json: bool = False, level: str = 'INFO') -> None:
    """
    Configure application logging.

    Args:
        use_json: If True, use structured JSON logging. Otherwise, use human-readable format.
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    # Set formatter based on configuration
    if use_json:
        formatter = StructuredFormatter()
    else:
        formatter = HumanReadableFormatter()

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Set log level for third-party libraries to reduce noise
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def log_with_context(logger: logging.Logger, level: str, message: str, **kwargs) -> None:
    """
    Log a message with additional context fields.

    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **kwargs: Additional context fields to include in the log
    """
    log_method = getattr(logger, level.lower())

    # Create a LogRecord with extra fields
    extra = {'extra_fields': kwargs}
    log_method(message, extra=extra)


def set_request_context(request_id: str = '', website_id: str = '') -> None:
    """Set request context for logging."""
    if request_id:
        request_id_var.set(request_id)
    if website_id:
        website_id_var.set(website_id)


def clear_request_context() -> None:
    """Clear request context."""
    request_id_var.set('')
    website_id_var.set('')
