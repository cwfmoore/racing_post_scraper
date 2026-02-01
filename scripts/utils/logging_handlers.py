"""
Custom logging handler for centralized API logging.
"""

import logging
import socket
from datetime import datetime, timezone

import requests


class APILogHandler(logging.Handler):
    """
    Logging handler that posts errors to the central logging API.
    Fails silently to avoid breaking the app.
    """

    def __init__(
        self,
        api_url: str = "http://192.168.1.145:8000/api/logs/",
        app_name: str = "racing_post_scraper",
    ):
        super().__init__()
        self.api_url = api_url
        self.app_name = app_name
        self.hostname = socket.gethostname()
        self.setLevel(logging.WARNING)

    def emit(self, record):
        """Post log record to API with rich metadata."""
        try:
            # Build metadata with context useful for debugging
            metadata = {
                "level": record.levelname,
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "file": record.pathname,
                "line": record.lineno,
                "process_id": record.process,
                "thread_id": record.thread,
                "thread_name": record.threadName,
            }

            # Add exception info if present
            if record.exc_info:
                exc_type, exc_value, exc_tb = record.exc_info
                if exc_type:
                    metadata["exception_type"] = exc_type.__name__
                    metadata["exception_value"] = str(exc_value)
                    # Include traceback (limit to last 10 frames)
                    import traceback
                    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
                    metadata["traceback"] = "".join(tb_lines[-10:])

            # Add any extra attributes passed to the log call
            if hasattr(record, "extra_data") and record.extra_data:
                metadata["extra"] = record.extra_data

            payload = {
                "time_stamp": datetime.now(timezone.utc).isoformat(),
                "app_name": self.app_name,
                "log_type": "error",
                "message": f"[{record.levelname}] {record.name}: {record.getMessage()}",
                "hostname": self.hostname,
                "metadata": metadata,
            }
            requests.post(self.api_url, json=payload, timeout=5)
        except Exception:
            # Fail silently - logging shouldn't break the app
            pass
