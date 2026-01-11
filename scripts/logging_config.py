"""
Logging configuration for the Racing Post scraper.

Provides:
- Console logging (INFO+) for docker compose logs
- Daily error log files (WARNING+) with 90-day retention
"""

import logging
from pathlib import Path

from utils.logging_handlers import DailyErrorFileHandler

BASE_DIR = Path(__file__).resolve().parent.parent
ERROR_LOG_DIR = BASE_DIR / 'error_logs'


def setup_logging():
    """Configure application logging. Call this at application startup."""

    formatter = logging.Formatter(
        fmt='%(levelname)-8s [%(asctime)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (all levels INFO+)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Error file handler (WARNING and above only)
    error_file_handler = DailyErrorFileHandler(
        log_dir=str(ERROR_LOG_DIR),
        retention_days=90
    )
    error_file_handler.setFormatter(formatter)
    error_file_handler.setLevel(logging.WARNING)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(error_file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)
