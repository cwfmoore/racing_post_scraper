"""
Logging configuration for the Racing Post scraper.

Provides:
- Console logging (INFO+) for docker compose logs
- API logging (WARNING+) to central logging server
"""

import logging

from utils.logging_handlers import APILogHandler


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

    # API handler for central logging
    api_handler = APILogHandler(app_name='racing_post_scraper')
    api_handler.setFormatter(formatter)
    api_handler.setLevel(logging.WARNING)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(api_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)
