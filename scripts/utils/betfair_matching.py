"""
Betfair market matching for Racing Post races.

Uses centralized matching API to match Racing Post races to Betfair markets
by venue and time, then matches runners by name.
"""

import logging
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

# API configuration - set API_BASE_URL in .env
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MATCHING_API_URL = f"{API_BASE_URL}/api/matching"
RACING_POST_API_URL = f"{API_BASE_URL}/api/racing-post"

# Matching thresholds
MATCH_THRESHOLD = 90  # 0-100 scale


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


def fetch_racing_post_runners(race_id: int) -> list[dict]:
    """
    Fetch runners for a Racing Post race from the API.

    Args:
        race_id: Racing Post race ID

    Returns:
        List of runner dicts with name
    """
    url = f"{RACING_POST_API_URL}/races/{race_id}/runners/"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch RP runners for race {race_id}: {response.status_code}")
            return []

        data = response.json()
        runners = data.get("results", data) if isinstance(data, dict) else data
        return [
            {"name": r.get("horse_name") or r.get("name", ""), "source_id": str(r.get("horse_id") or r.get("id", i))}
            for i, r in enumerate(runners)
        ]
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch RP runners for race {race_id}: {e}")
        return []


def match_runners_via_api(market_id: str, source_runners: list[dict]) -> dict:
    """
    Match source runners to Betfair selection IDs via centralized API.

    Args:
        market_id: Betfair market ID
        source_runners: List of dicts with 'name' and 'source_id'

    Returns:
        API response with match results
    """
    url = f"{MATCHING_API_URL}/runners/"
    payload = {
        "market_id": market_id,
        "source_runners": source_runners,
        "config": {
            "runner_threshold": MATCH_THRESHOLD
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to match runners for {market_id}: {e}")
        return {"error": str(e), "results": []}


def match_races_via_api(races: list[dict], date: str) -> dict:
    """
    Match races to Betfair markets via centralized API.

    Args:
        races: List of race dicts with venue, time, runners
        date: Date string YYYY-MM-DD

    Returns:
        API response with match results
    """
    url = f"{MATCHING_API_URL}/races/"
    payload = {
        "date": date,
        "races": races,
        "config": {
            "venue_threshold": MATCH_THRESHOLD,
            "runner_threshold": MATCH_THRESHOLD,
            "time_tolerance_mins": 5
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to match races for {date}: {e}")
        return {"error": str(e), "results": []}


def save_runner_mappings(race_id: int, market_id: str, runner_matches: list[dict]) -> bool:
    """
    Save runner mappings to Racing Post API.

    Updates rp_race.market_id and rp_run.selection_id.

    Args:
        race_id: Racing Post race ID
        market_id: Betfair market ID
        runner_matches: List of match results from matching API

    Returns:
        True if saved successfully
    """
    url = f"{RACING_POST_API_URL}/save-mappings/"

    # Build runners list from match results
    runners = []
    for match in runner_matches:
        if match.get("matched") and match.get("selection_id"):
            # source_id format is the horse_id from RP
            source_id = match.get("source_id", "")
            try:
                horse_id = int(source_id) if source_id else None
            except (ValueError, TypeError):
                horse_id = None

            if horse_id:
                runners.append({
                    "horse_id": horse_id,
                    "selection_id": match.get("selection_id"),
                })

    if not runners:
        logger.warning(f"No matched runners to save for race {race_id}")
        return False

    payload = {
        "race_id": race_id,
        "market_id": market_id,
        "runners": runners,
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        logger.info(f"Saved mappings for race {race_id}: {result.get('runners_updated', 0)} runners")
        return True
    except requests.RequestException as e:
        logger.warning(f"Failed to save mappings for race {race_id}: {e}")
        return False


def match_races_to_betfair(
    races: list[dict],
    date: str,
    countries: list[str] = None,
) -> dict:
    """
    Match Racing Post races to Betfair markets and runners via API.

    Args:
        races: List of Racing Post race dicts with race_id, course, off_time
        date: Date string YYYY-MM-DD
        countries: Country codes (unused, API handles this)

    Returns:
        Dict with match statistics
    """
    if not races:
        return {
            "total_races": 0,
            "races_matched": 0,
            "runners_matched": 0,
        }

    logger.info(f"Matching {len(races)} races for {date} via API...")

    # Build race list with runners for matching API
    api_races = []
    race_lookup = {}  # Map source_id -> race_id for saving mappings

    for race in races:
        race_id = race.get("race_id")
        venue = race.get("course") or race.get("venue")
        off_time = race.get("off_time")

        if not all([race_id, venue, off_time]):
            continue

        # Fetch runners for this race
        runners = fetch_racing_post_runners(race_id)

        source_id = f"rp_{race_id}"
        api_races.append({
            "venue": venue,
            "time": normalize_time(off_time),
            "source_id": source_id,
            "runners": runners,
        })
        race_lookup[source_id] = race_id

    if not api_races:
        logger.warning("No valid races to match")
        return {"total_races": len(races), "races_matched": 0, "runners_matched": 0}

    # Call matching API
    result = match_races_via_api(api_races, date)

    if "error" in result:
        logger.error(f"Matching API error: {result.get('error')}")
        return {"total_races": len(races), "races_matched": 0, "runners_matched": 0}

    # Process results and save mappings
    races_matched = 0
    total_runners_matched = 0

    for race_result in result.get("results", []):
        source_id = race_result.get("source_id")
        race_id = race_lookup.get(source_id)

        if not race_result.get("matched") or not race_id:
            continue

        market_id = race_result.get("market_id")
        runners_matched = race_result.get("runners_matched", 0)
        runner_results = race_result.get("runners", [])

        # Save mappings to Racing Post API
        if save_runner_mappings(race_id, market_id, runner_results):
            races_matched += 1
            total_runners_matched += runners_matched
            logger.info(f"Matched race {race_id} -> {market_id} ({runners_matched} runners)")
        else:
            logger.warning(f"Failed to save mappings for race {race_id}")

    logger.info(f"Matching complete: {races_matched}/{len(races)} races, {total_runners_matched} runners")

    return {
        "total_races": len(races),
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
