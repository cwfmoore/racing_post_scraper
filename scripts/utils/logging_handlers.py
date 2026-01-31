"""
Custom logging handlers for error log management.

Provides daily rotating error logs with automatic cleanup of files older than retention period.
"""

import logging
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


class DailyErrorFileHandler(logging.Handler):
    """
    A logging handler that writes to daily error log files.

    Features:
    - Creates files named YYYY-MM-DD_error_log.txt
    - Automatically creates the log directory if it doesn't exist
    - Cleans up files older than retention_days on startup
    - Only logs WARNING level and above by default
    """

    def __init__(self, log_dir: str, retention_days: int = 90):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.retention_days = retention_days
        self._current_date = None
        self._file_handle = None

        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Clean up old logs on startup
        self._cleanup_old_logs()

    def _get_log_filename(self) -> Path:
        """Get the log filename for today."""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.log_dir / f"{today}_error_log.txt"

    def _ensure_file_handle(self):
        """Ensure we have a valid file handle for today's date."""
        today = datetime.now().date()

        if self._current_date != today:
            # Close old file handle if exists
            if self._file_handle:
                self._file_handle.close()

            # Open new file for today
            self._current_date = today
            log_file = self._get_log_filename()
            self._file_handle = open(log_file, 'a', encoding='utf-8')

    def _cleanup_old_logs(self):
        """Remove log files older than retention_days."""
        if not self.log_dir.exists():
            return

        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        for log_file in self.log_dir.glob('*_error_log.txt'):
            try:
                # Extract date from filename (YYYY-MM-DD_error_log.txt)
                date_str = log_file.name[:10]
                file_date = datetime.strptime(date_str, '%Y-%m-%d')

                if file_date < cutoff_date:
                    log_file.unlink()
            except (ValueError, OSError):
                # Skip files that don't match expected format or can't be deleted
                pass

    def emit(self, record):
        """Write a log record to the daily file."""
        try:
            self._ensure_file_handle()
            msg = self.format(record)
            self._file_handle.write(msg + '\n')
            self._file_handle.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        """Clean up the file handle."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
        super().close()


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
        """Post log record to API."""
        try:
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "app_name": self.app_name,
                "log_type": "error",
                "message": self.format(record),
                "hostname": self.hostname,
                "metadata": {
                    "level": record.levelname,
                    "logger": record.name,
                    "module": record.module,
                    "line": record.lineno,
                },
            }
            requests.post(self.api_url, json=payload, timeout=5)
        except Exception:
            # Fail silently - logging shouldn't break the app
            pass
