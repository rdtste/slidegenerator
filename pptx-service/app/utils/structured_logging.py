"""Structured logging with context metadata (P2 enhancement).

PPTX Skill requirement (Production Observability):
- Context-rich logs with request/job metadata
- Structured JSON output for log aggregation
- Distributed tracing support (trace IDs)
- Performance timing and profiling
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any, Optional

# Context variables for distributed tracing
request_id: ContextVar[str] = ContextVar("request_id", default="")
job_id: ContextVar[str] = ContextVar("job_id", default="")
user_id: ContextVar[str] = ContextVar("user_id", default="")


class StructuredLogRecord(logging.LogRecord):
    """Extended log record with structured metadata."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_id = request_id.get()
        self.job_id = job_id.get()
        self.user_id = user_id.get()
        self.timestamp = time.time()


class StructuredFormatter(logging.Formatter):
    """Formats logs as structured JSON."""
    
    def format(self, record: StructuredLogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": record.created,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add context variables if present
        if record.request_id:
            log_data["request_id"] = record.request_id
        if record.job_id:
            log_data["job_id"] = record.job_id
        if record.user_id:
            log_data["user_id"] = record.user_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add custom message data if attached
        if hasattr(record, "extra_data") and record.extra_data:
            log_data.update(record.extra_data)
        
        return json.dumps(log_data, ensure_ascii=False)


class StructuredLogger:
    """Wrapper for consistent structured logging."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Only configure if no handlers exist
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = StructuredFormatter()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def set_context(
        self,
        request_id: Optional[str] = None,
        job_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Set context variables for this request."""
        if request_id:
            request_id.set(request_id)
        if job_id:
            job_id.set(job_id)
        if user_id:
            user_id.set(user_id)
    
    def debug(self, message: str, **extra):
        """Log debug message with extra metadata."""
        record = self.logger.makeRecord(
            self.logger.name, logging.DEBUG, "(unknown file)", 0,
            message, (), None
        )
        record.extra_data = extra
        self.logger.handle(record)
    
    def info(self, message: str, **extra):
        """Log info message with extra metadata."""
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, "(unknown file)", 0,
            message, (), None
        )
        record.extra_data = extra
        self.logger.handle(record)
    
    def warning(self, message: str, **extra):
        """Log warning message with extra metadata."""
        record = self.logger.makeRecord(
            self.logger.name, logging.WARNING, "(unknown file)", 0,
            message, (), None
        )
        record.extra_data = extra
        self.logger.handle(record)
    
    def error(self, message: str, **extra):
        """Log error message with extra metadata."""
        record = self.logger.makeRecord(
            self.logger.name, logging.ERROR, "(unknown file)", 0,
            message, (), None
        )
        record.extra_data = extra
        self.logger.handle(record)
    
    def exception(self, message: str, exc_info=True, **extra):
        """Log exception with traceback."""
        self.logger.exception(message, exc_info=exc_info, extra=extra)
    
    def timing(self, operation: str, elapsed_seconds: float, **extra):
        """Log operation timing."""
        self.info(
            f"[TIMING] {operation} completed",
            duration_seconds=round(elapsed_seconds, 3),
            **extra
        )


class TimingContext:
    """Context manager for operation timing."""
    
    def __init__(self, logger: StructuredLogger, operation: str, **extra):
        self.logger = logger
        self.operation = operation
        self.extra = extra
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        
        if exc_type:
            self.logger.error(
                f"[TIMING] {self.operation} failed after {elapsed:.3f}s",
                duration_seconds=round(elapsed, 3),
                error=str(exc_val),
                **self.extra
            )
        else:
            self.logger.timing(self.operation, elapsed, **self.extra)


def setup_structured_logging():
    """Configure structured logging for entire application."""
    
    # Override logging module's LogRecord with structured version
    logging.setLogRecordFactory(StructuredLogRecord)
    
    logger.info("Structured logging initialized")


# Get structured logger for module
logger = StructuredLogger("pptx_service")
