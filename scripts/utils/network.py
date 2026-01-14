import logging

from collections.abc import Sequence
from curl_cffi import Session, Response, BrowserTypeLiteral
from datetime import datetime

# Handle different curl_cffi versions - exception class name varies
try:
    from curl_cffi.requests.exceptions import RequestsError
except ImportError:
    try:
        from curl_cffi import CurlError as RequestsError
    except ImportError:
        # Fallback to base Exception if neither exists
        RequestsError = Exception
from random import choice
from time import sleep
from urllib.parse import quote

from utils.exceptions import (
    NetworkError,
    RETRYABLE_STATUS_CODES,
    RETRY_BASE_DELAY,
    RETRY_MAX_DELAY,
    RETRY_MAX_HOURS,
    calculate_backoff,
    get_retry_deadline,
    should_continue_retry,
    time_remaining,
)

logger = logging.getLogger(__name__)


class Persistent406Error(Exception):
    """Kept for backwards compatibility."""

    pass


BROWSERS: Sequence[BrowserTypeLiteral] = (
    'edge',
    'chrome',
    'firefox',
    'safari',
)


COGNITO_POOL = '3fii107m4bmtggnm21pud2es21'


def construct_cookies(
    email: str | None, auth_state: str | None, access_token: str | None
) -> dict[str, str]:
    if email is None or auth_state is None or access_token is None:
        return {}

    key = f'CognitoIdentityServiceProvider.{COGNITO_POOL}.{quote(email, safe="")}.accessToken'

    return {
        'auth_state': auth_state,
        key: access_token,
    }


class NetworkClient:
    def __init__(
        self,
        *,
        email: str | None = None,
        auth_state: str | None = None,
        access_token: str | None = None,
        timeout: int = 14,
    ) -> None:
        cookies = construct_cookies(email, auth_state, access_token)

        self.session: Session = Session(impersonate=choice(BROWSERS), cookies=cookies)
        self.timeout: int = timeout

    def get(
        self,
        url: str,
        allow_redirects: bool = True,
        max_hours: float = RETRY_MAX_HOURS,
        base_delay: float = RETRY_BASE_DELAY,
        max_delay: float = RETRY_MAX_DELAY,
    ) -> tuple[int, Response]:
        """
        Make a GET request with time-based exponential backoff retry.

        Retries for up to max_hours (default 23 hours) with exponential backoff
        starting at base_delay (default 2s) up to max_delay (default 30 minutes).

        Args:
            url: The URL to fetch
            allow_redirects: Whether to follow redirects
            max_hours: Maximum hours to keep retrying (default 23)
            base_delay: Base delay for exponential backoff (default 2s)
            max_delay: Maximum delay between retries (default 30 minutes)

        Returns:
            Tuple of (status_code, response)

        Raises:
            NetworkError: On connection/timeout errors after retry period
            Persistent406Error: On persistent 406 errors (backwards compatibility)
        """
        deadline = get_retry_deadline(max_hours)
        last_error: Exception | None = None
        last_status: int | None = None
        attempt = 0

        while should_continue_retry(deadline):
            try:
                response = self.session.get(
                    url,
                    allow_redirects=allow_redirects,
                    timeout=self.timeout,
                )

                # Success - return immediately
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    return response.status_code, response

                last_status = response.status_code

                # Retryable status - log and retry with backoff
                remaining = time_remaining(deadline)
                if remaining.total_seconds() > 0:
                    delay = calculate_backoff(attempt, base_delay, max_delay)
                    # Don't wait longer than remaining time
                    delay = min(delay, remaining.total_seconds())

                    logger.warning(
                        f'{response.status_code} error (attempt {attempt + 1}, '
                        f'{remaining.total_seconds() / 3600:.1f}h remaining): '
                        f'{url}, retrying in {delay:.0f}s'
                    )
                    sleep(delay)
                    attempt += 1

            except RequestsError as e:
                # Connection error, timeout, etc.
                last_error = e
                remaining = time_remaining(deadline)
                if remaining.total_seconds() > 0:
                    delay = calculate_backoff(attempt, base_delay, max_delay)
                    delay = min(delay, remaining.total_seconds())

                    logger.warning(
                        f'Network error (attempt {attempt + 1}, '
                        f'{remaining.total_seconds() / 3600:.1f}h remaining): {e}, '
                        f'retrying in {delay:.0f}s'
                    )
                    sleep(delay)
                    attempt += 1

        # Retry period exhausted
        elapsed_hours = max_hours - (time_remaining(deadline).total_seconds() / 3600)

        if last_error:
            logger.error(
                f'Network error after {elapsed_hours:.1f}h ({attempt} attempts): {url} - {last_error}'
            )
            raise NetworkError(
                f'Network error after {elapsed_hours:.1f}h on {url}: {last_error}'
            )

        if last_status == 406:
            # Backwards compatibility
            logger.error(f'Persistent 406 after {elapsed_hours:.1f}h ({attempt} attempts): {url}')
            raise Persistent406Error(
                f'received 406 for {elapsed_hours:.1f}h on {url}'
            )

        # Return last response even if it was a retryable status
        logger.error(
            f'Persistent {last_status} after {elapsed_hours:.1f}h ({attempt} attempts): {url}'
        )
        return last_status, response
