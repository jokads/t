"""
Structured Logging - JSON format with Sentry integration

Provides:
- JSON structured logging
- Sentry error tracking (optional)
- Request tracing with trace IDs
- Performance metrics logging
"""

from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional

from bot_mt5.utils.config import LoggingConfig, get_config

# Context variable for trace ID (thread-safe)
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter.

    Outputs logs in structured JSON format for easy parsing by
    log aggregation tools (ELK, Loki, etc).
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        # Base log data
        log_data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add trace ID if available
        trace_id = trace_id_var.get()
        if trace_id:
            log_data["trace_id"] = trace_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": (
                    self.formatException(record.exc_info) if record.exc_info else None
                ),
            }

        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        # Add process/thread info
        log_data["process"] = {
            "pid": record.process,
            "name": record.processName,
        }

        log_data["thread"] = {
            "id": record.thread,
            "name": record.threadName,
        }

        # Add source location
        log_data["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }

        return json.dumps(log_data, default=str)


class TextFormatter(logging.Formatter):
    """
    Human-readable text formatter.

    For development/debugging.
    """

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def setup_logging(config: Optional[LoggingConfig] = None):
    """
    Setup logging configuration.

    Args:
        config: Logging configuration (uses default if None)
    """
    config = config or get_config().logging

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Set formatter
    if config.format == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Setup Sentry if DSN provided
    if config.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=config.sentry_dsn,
                traces_sample_rate=0.1,  # 10% of transactions
                profiles_sample_rate=0.1,  # 10% of profiles
            )
            root_logger.info("Sentry error tracking enabled")
        except ImportError:
            root_logger.warning("sentry-sdk not installed, error tracking disabled")
        except Exception as e:
            root_logger.exception(f"Failed to initialize Sentry: {e}")

    root_logger.info(
        f"Logging configured: level={config.level}, format={config.format}"
    )


def set_trace_id(trace_id: str):
    """
    Set trace ID for current context.

    All logs in this context will include the trace ID.

    Args:
        trace_id: Trace ID string
    """
    trace_id_var.set(trace_id)


def get_trace_id() -> Optional[str]:
    """
    Get trace ID for current context.

    Returns:
        Trace ID string or None
    """
    return trace_id_var.get()


def clear_trace_id():
    """Clear trace ID for current context"""
    trace_id_var.set(None)


class LogTimer:
    """
    Context manager for timing code blocks with logging.

    Example:
        with LogTimer("process_signal"):
            result = await process_signal(data)
    """

    def __init__(
        self,
        operation: str,
        logger: Optional[logging.Logger] = None,
        level: int = logging.INFO,
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.operation = operation
        self.logger = logger or logging.getLogger(__name__)
        self.level = level
        self.extra = extra or {}
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.time() - self.start_time) * 1000

        log_data = {
            "operation": self.operation,
            "duration_ms": round(elapsed_ms, 2),
            **self.extra,
        }

        if exc_type:
            log_data["success"] = False
            log_data["error"] = str(exc_val)
            self.logger.log(
                logging.ERROR,
                f"{self.operation} failed after {elapsed_ms:.1f}ms",
                extra=log_data,
            )
        else:
            log_data["success"] = True
            self.logger.log(
                self.level,
                f"{self.operation} completed in {elapsed_ms:.1f}ms",
                extra=log_data,
            )


def log_performance(
    operation: str,
    duration_ms: float,
    success: bool = True,
    extra: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
):
    """
    Log performance metrics.

    Args:
        operation: Operation name
        duration_ms: Duration in milliseconds
        success: Whether operation succeeded
        extra: Extra fields to log
        logger: Logger to use (default: root logger)
    """
    logger = logger or logging.getLogger(__name__)

    log_data = {
        "metric": "performance",
        "operation": operation,
        "duration_ms": round(duration_ms, 2),
        "success": success,
        **(extra or {}),
    }

    level = logging.INFO if success else logging.WARNING
    logger.log(level, f"{operation}: {duration_ms:.1f}ms", extra=log_data)


def log_metric(
    metric_name: str,
    value: float,
    unit: str = "",
    extra: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
):
    """
    Log a metric value.

    Args:
        metric_name: Metric name
        value: Metric value
        unit: Unit of measurement
        extra: Extra fields to log
        logger: Logger to use (default: root logger)
    """
    logger = logger or logging.getLogger(__name__)

    log_data = {
        "metric": metric_name,
        "value": value,
        "unit": unit,
        **(extra or {}),
    }

    logger.info(f"{metric_name}={value}{unit}", extra=log_data)
