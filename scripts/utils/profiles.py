import logging

from typing import Any
from orjson import loads, JSONDecodeError
from lxml import html

from utils.exceptions import ProfileFetchError, ProfileParseError, NetworkError
from utils.network import NetworkClient

logger = logging.getLogger(__name__)


def get_profiles(client: NetworkClient, urls: list[str]) -> dict[str, dict[str, Any]]:
    """
    Fetch profiles for multiple horses.

    Individual profile failures are logged and skipped - the function continues
    processing remaining URLs. This allows partial data collection rather than
    failing the entire operation.

    The network layer handles retries with exponential backoff for up to 23 hours
    on retryable errors (429, 500, 502, 503, 504, 406).

    Args:
        client: NetworkClient instance for making requests
        urls: List of profile URLs to fetch

    Returns:
        Dictionary mapping horse UID to profile data
    """
    profiles: dict[str, dict[str, Any]] = {}

    for url in urls:
        try:
            profile = _extract_profile_from_url(client, url)
            split = url.split('/')

            profile['profile']['profile'] = f'{split[5]}/{split[6]}'
            profile['profile']['quotes'] = profile['quotes']
            profile['profile']['stable_quotes'] = profile['stableTourQuotes']
            profiles[profile['profile']['horseUid']] = profile['profile']

        except (ProfileFetchError, ProfileParseError, NetworkError) as e:
            logger.warning(f'Skipping profile: {e}')
            continue

    return profiles


def _extract_profile_from_url(client: NetworkClient, url: str) -> dict[str, Any]:
    """
    Extract profile data from a URL.

    The network layer handles retries with exponential backoff for up to 23 hours
    on retryable errors.

    Args:
        client: NetworkClient instance
        url: Profile URL to fetch

    Returns:
        Profile data dictionary

    Raises:
        ProfileFetchError: If HTTP request fails (non-200 status after retries)
        ProfileParseError: If response cannot be parsed
        NetworkError: If network error persists after retry period
    """
    status, response = client.get(url)

    if status != 200:
        raise ProfileFetchError(f'Failed to get profile. Status: {status}, URL: {url}')

    return _parse_profile_response(response.content, url)


def _parse_profile_response(content: bytes, url: str) -> dict[str, Any]:
    """
    Parse profile data from HTML response.

    Args:
        content: Response content bytes
        url: URL for error messages

    Returns:
        Parsed profile data

    Raises:
        ProfileParseError: If parsing fails
    """
    try:
        doc = html.fromstring(content)
        script_elements = doc.xpath('//body/script')

        if not script_elements:
            raise ProfileParseError(f'No script element found at URL: {url}')

        json_str = _extract_json_string(script_elements[0].text)
        return loads(json_str)

    except (IndexError, AttributeError) as e:
        raise ProfileParseError(f'Failed to extract script from {url}: {e}')
    except (ValueError, JSONDecodeError) as e:
        raise ProfileParseError(f'Invalid JSON at {url}: {e}')
    except KeyError as e:
        raise ProfileParseError(f'Missing key in profile data from {url}: {e}')


def _extract_json_string(script_text: str) -> str:
    """Extract JSON string from script element text."""
    return script_text.split('window.PRELOADED_STATE =')[1].split('\n')[0].strip().strip(';')
