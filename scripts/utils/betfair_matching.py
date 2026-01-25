"""
Betfair market matching for Racing Post races.

Fetches Betfair markets via API and matches them to Racing Post races
by venue and off time, then auto-matches runners by name.
"""

import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

# API configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
BETFAIR_API_URL = f"{API_BASE_URL}/api/betfair"
RACING_POST_API_URL = f"{API_BASE_URL}/api/racing-post"


def normalize_venue(venue: str) -> str:
    """Normalize venue name for matching."""
    if not venue:
        return ""

    result = venue.lower()
    # Remove accents
    result = unicodedata.normalize("NFD", result)
    result = "".join(c for c in result if unicodedata.category(c) != "Mn")
    # Remove non-alphanumeric
    result = re.sub(r"[^a-z0-9\s]", "", result)
    result = re.sub(r"\s+", " ", result)
    return result.strip()


def normalize_time(time_str: str) -> str:
    """Normalize time to HH:MM format."""
    if not time_str:
        return ""

    # Handle ISO format
    if "T" in time_str:
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            # Convert to UK time
            uk_tz = ZoneInfo("Europe/London")
            dt_uk = dt.astimezone(uk_tz)
            return dt_uk.strftime("%H:%M")
        except Exception:
            pass

    # Extract HH:MM pattern
    match = re.search(r"(\d{1,2}):(\d{2})", time_str)
    if match:
        hours = int(match.group(1))
        minutes = match.group(2)
        return f"{hours:02d}:{minutes}"

    return time_str


def fetch_betfair_markets(
    date: str,
    countries: list[str] = None,
    hours_ahead: int = 24,
) -> list[dict]:
    """
    Fetch Betfair markets from API.

    Args:
        date: Date string YYYY-MM-DD
        countries: Country codes (default: GB, IE)
        hours_ahead: Hours ahead to fetch

    Returns:
        List of market dicts with market_id, venue, start_time, runners
    """
    if countries is None:
        countries = ["GB", "IE"]

    url = f"{BETFAIR_API_URL}/racecards/"
    params = {
        "countries": ",".join(countries),
        "hours_ahead": hours_ahead,
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("races", [])
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Betfair markets: {e}")
        return []


def fetch_market_runners(market_id: str) -> list[dict]:
    """
    Fetch runners for a specific Betfair market.

    Args:
        market_id: Betfair market ID

    Returns:
        List of runner dicts with selection_id, name
    """
    url = f"{BETFAIR_API_URL}/markets/{market_id}/runners/"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 404:
            # Market not in local DB, need to fetch from Betfair API
            # Use the market info endpoint instead
            url = f"{API_BASE_URL}/api/streaming/markets/{market_id}/runners/"
            response = requests.get(url, timeout=30)

        if response.status_code != 200:
            logger.warning(f"Failed to fetch runners for {market_id}: {response.status_code}")
            return []

        runners = response.json()
        # Normalize runner format
        return [
            {
                "selection_id": r.get("selection_id"),
                "name": r.get("runner_name") or r.get("name", ""),
            }
            for r in runners
        ]
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch runners for {market_id}: {e}")
        return []


def auto_match_race(
    race_id: int,
    market_id: str,
    betfair_runners: list[dict],
) -> dict:
    """
    Call API to auto-match Racing Post runners to Betfair runners.

    Args:
        race_id: Racing Post race ID
        market_id: Betfair market ID
        betfair_runners: List of Betfair runners with selection_id and name

    Returns:
        API response with match results
    """
    url = f"{RACING_POST_API_URL}/mappings/auto-match/"
    payload = {
        "race_id": race_id,
        "market_id": market_id,
        "betfair_runners": betfair_runners,
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to auto-match race {race_id}: {e}")
        return {"error": str(e)}


def match_race_to_market(
    race_venue: str,
    race_time: str,
    betfair_markets: list[dict],
    time_tolerance_minutes: int = 5,
) -> Optional[dict]:
    """
    Find matching Betfair market for a Racing Post race.

    Args:
        race_venue: Racing Post venue name
        race_time: Race off time HH:MM
        betfair_markets: List of Betfair markets
        time_tolerance_minutes: Minutes tolerance for time matching

    Returns:
        Matched market dict or None
    """
    race_venue_norm = normalize_venue(race_venue)
    race_time_norm = normalize_time(race_time)

    if not race_venue_norm or not race_time_norm:
        return None

    # Parse race time
    try:
        race_hours, race_mins = map(int, race_time_norm.split(":"))
        race_total_mins = race_hours * 60 + race_mins
    except (ValueError, AttributeError):
        return None

    best_match = None
    best_time_diff = float("inf")

    for market in betfair_markets:
        market_venue = normalize_venue(market.get("venue", ""))
        market_time = normalize_time(market.get("start_time", ""))

        # Check venue match
        if not market_venue or race_venue_norm not in market_venue and market_venue not in race_venue_norm:
            continue

        # Check time match
        try:
            market_hours, market_mins = map(int, market_time.split(":"))
            market_total_mins = market_hours * 60 + market_mins
            time_diff = abs(race_total_mins - market_total_mins)

            if time_diff <= time_tolerance_minutes and time_diff < best_time_diff:
                best_time_diff = time_diff
                best_match = market
        except (ValueError, AttributeError):
            continue

    return best_match


def match_races_to_betfair(
    races: list[dict],
    date: str,
    countries: list[str] = None,
) -> dict:
    """
    Match Racing Post races to Betfair markets and auto-match runners.

    Args:
        races: List of Racing Post race dicts with race_id, course, off_time
        date: Date string YYYY-MM-DD
        countries: Country codes to fetch

    Returns:
        Dict with match statistics
    """
    if countries is None:
        countries = ["GB", "IE"]

    logger.info(f"Fetching Betfair markets for {date}...")
    betfair_markets = fetch_betfair_markets(date, countries)

    if not betfair_markets:
        logger.warning("No Betfair markets found")
        return {
            "total_races": len(races),
            "markets_found": 0,
            "races_matched": 0,
            "runners_matched": 0,
        }

    logger.info(f"Found {len(betfair_markets)} Betfair markets")

    races_matched = 0
    total_runners_matched = 0

    for race in races:
        race_id = race.get("race_id")
        venue = race.get("course") or race.get("venue")
        off_time = race.get("off_time")

        if not all([race_id, venue, off_time]):
            continue

        # Find matching Betfair market
        market = match_race_to_market(venue, off_time, betfair_markets)

        if not market:
            logger.debug(f"No Betfair match for {venue} {off_time}")
            continue

        market_id = market.get("market_id")
        logger.info(f"Matched {venue} {off_time} -> {market_id}")

        # Fetch runners for this market
        betfair_runners = fetch_market_runners(market_id)

        if not betfair_runners:
            logger.warning(f"No runners found for market {market_id}")
            continue

        # Auto-match runners
        result = auto_match_race(race_id, market_id, betfair_runners)

        if "error" not in result:
            races_matched += 1
            matched = result.get("matched", 0)
            total_runners_matched += matched
            logger.info(f"  Matched {matched} runners")
        else:
            logger.warning(f"  Auto-match failed: {result.get('error')}")

    return {
        "total_races": len(races),
        "markets_found": len(betfair_markets),
        "races_matched": races_matched,
        "runners_matched": total_runners_matched,
    }


def match_racecards_to_betfair(racecards_data: dict, date: str) -> dict:
    """
    Match racecard data structure to Betfair.

    Args:
        racecards_data: Nested dict structure from racecards.py
            {region: {course: {time: race_dict}}}
        date: Date string YYYY-MM-DD

    Returns:
        Match statistics
    """
    # Flatten racecards to list of races
    races = []

    for region, courses in racecards_data.items():
        for course, times in courses.items():
            for off_time, race in times.items():
                races.append({
                    "race_id": race.get("race_id"),
                    "course": course,
                    "off_time": off_time,
                    "region": region,
                })

    if not races:
        logger.warning("No races found in racecard data")
        return {"total_races": 0, "races_matched": 0}

    # Determine countries from regions
    countries = set()
    for race in races:
        region = race.get("region", "").upper()
        if region == "GB":
            countries.add("GB")
        elif region in ("IRE", "IE"):
            countries.add("IE")
        elif region == "FR":
            countries.add("FR")
        elif region == "USA":
            countries.add("US")

    return match_races_to_betfair(races, date, list(countries) or ["GB", "IE"])
