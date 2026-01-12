"""
Custom exceptions and retry configuration for the racing post scraper.

These exceptions allow for recoverable error handling instead of hard exits,
enabling retry logic and graceful degradation.
"""

import random
from datetime import datetime, timedelta


# =============================================================================
# Retry Configuration
# =============================================================================

# Maximum time to keep retrying (23 hours)
RETRY_MAX_HOURS = 23

# Base delay for exponential backoff (2 seconds)
RETRY_BASE_DELAY = 2.0

# Maximum delay between retries (30 minutes = 1800 seconds)
RETRY_MAX_DELAY = 1800.0

# Status codes that should trigger a retry
RETRYABLE_STATUS_CODES = {406, 429, 500, 502, 503, 504}


def calculate_backoff(
    attempt: int,
    base_delay: float = RETRY_BASE_DELAY,
    max_delay: float = RETRY_MAX_DELAY,
) -> float:
    """
    Calculate exponential backoff delay with jitter.

    Args:
        attempt: The current attempt number (0-indexed)
        base_delay: Base delay in seconds (default 2s)
        max_delay: Maximum delay in seconds (default 30 minutes)

    Returns:
        Delay in seconds with jitter (0-25% added)
    """
    delay = min(base_delay * (2**attempt), max_delay)
    jitter = delay * random.uniform(0, 0.25)
    return delay + jitter


def get_retry_deadline(max_hours: float = RETRY_MAX_HOURS) -> datetime:
    """
    Get the deadline for retry operations.

    Args:
        max_hours: Maximum hours to retry (default 23)

    Returns:
        Datetime when retries should stop
    """
    return datetime.now() + timedelta(hours=max_hours)


def should_continue_retry(deadline: datetime) -> bool:
    """
    Check if retries should continue based on deadline.

    Args:
        deadline: The retry deadline datetime

    Returns:
        True if current time is before deadline
    """
    return datetime.now() < deadline


def time_remaining(deadline: datetime) -> timedelta:
    """
    Get time remaining until deadline.

    Args:
        deadline: The retry deadline datetime

    Returns:
        Timedelta of remaining time (minimum 0)
    """
    remaining = deadline - datetime.now()
    return max(remaining, timedelta(0))


# =============================================================================
# Exceptions
# =============================================================================


class ScraperError(Exception):
    """Base exception for scraper errors."""

    pass


class ProfileFetchError(ScraperError):
    """Failed to fetch horse profile after retries."""

    pass


class ProfileParseError(ScraperError):
    """Failed to parse horse profile data."""

    pass


class RaceFetchError(ScraperError):
    """Failed to fetch race data after retries."""

    pass


class NetworkError(ScraperError):
    """Network-level error (connection, timeout, etc.)."""

    pass
