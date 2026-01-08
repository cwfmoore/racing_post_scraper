"""
Racing Post API Wrapper.

A Python client for interacting with the Racing Post API endpoints.

Usage:
    from api_wrapper import RacingPostAPI

    api = RacingPostAPI()  # Uses default localhost:8000

    # Scrape results from Racing Post
    result = api.scrape(date="2026/01/06", region="gb", betfair=True)

    # Get races by date
    races = api.get_races(date="2026-01-06")

    # Get all winners
    winners = api.get_runs(won=True)

    # Get horse history
    history = api.get_horse_history(horse_id=1234567)
"""

from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import urlencode

import requests


@dataclass
class APIResponse:
    """Response wrapper for API calls."""

    success: bool
    data: Any
    error: str | None = None
    status_code: int = 200


class RacingPostAPI:
    """Client for Racing Post API."""

    def __init__(self, base_url: str = "http://localhost:8000/api/racing-post"):
        """
        Initialize the API client.

        Args:
            base_url: Base URL for the API (default: localhost:8000)
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    # =========================================================================
    # Scraping Endpoints (POST)
    # =========================================================================

    def scrape(
        self,
        date: str,
        region: str = "gb",
        race_type: str = "all",
        betfair: bool = False,
    ) -> APIResponse:
        """
        Scrape race results from Racing Post and save to database.

        Args:
            date: Date or date range (YYYY/MM/DD or YYYY/MM/DD-YYYY/MM/DD)
            region: Region code (gb, ire, fr, etc.)
            race_type: Filter by type ("flat", "jumps", "all")
            betfair: Include Betfair BSP data

        Returns:
            APIResponse with import results
        """
        payload = {
            "date": date,
            "region": region,
            "race_type": race_type,
            "betfair": betfair,
        }
        return self._post("/scrape/", payload)

    def sync(self, races: list[dict]) -> APIResponse:
        """
        Sync race data to the database.

        Args:
            races: List of race data dicts with race_info and runner_info

        Returns:
            APIResponse with import results
        """
        payload = {"races": races}
        return self._post("/sync/", payload)

    # =========================================================================
    # Course Endpoints
    # =========================================================================

    def get_courses(
        self,
        region: str | None = None,
        name: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> APIResponse:
        """Get list of courses."""
        params = self._build_params(
            region=region, name=name, page=page, page_size=page_size
        )
        return self._get("/courses/", params)

    def get_course(self, course_id: int) -> APIResponse:
        """Get a single course by ID."""
        return self._get(f"/courses/{course_id}/")

    # =========================================================================
    # Horse Endpoints
    # =========================================================================

    def get_horses(
        self,
        name: str | None = None,
        region: str | None = None,
        sex: str | None = None,
        sire_id: int | None = None,
        dam_id: int | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> APIResponse:
        """Get list of horses."""
        params = self._build_params(
            name=name,
            region=region,
            sex=sex,
            sire_id=sire_id,
            dam_id=dam_id,
            page=page,
            page_size=page_size,
        )
        return self._get("/horses/", params)

    def get_horse(self, horse_id: int) -> APIResponse:
        """Get a single horse by ID."""
        return self._get(f"/horses/{horse_id}/")

    def get_horse_history(self, horse_id: int) -> APIResponse:
        """Get horse with full race history."""
        return self._get(f"/horses/{horse_id}/history/")

    # =========================================================================
    # Jockey Endpoints
    # =========================================================================

    def get_jockeys(
        self,
        name: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> APIResponse:
        """Get list of jockeys."""
        params = self._build_params(name=name, page=page, page_size=page_size)
        return self._get("/jockeys/", params)

    def get_jockey(self, jockey_id: int) -> APIResponse:
        """Get a single jockey by ID."""
        return self._get(f"/jockeys/{jockey_id}/")

    def get_jockey_runs(self, jockey_id: int) -> APIResponse:
        """Get all runs for a jockey."""
        return self._get(f"/jockeys/{jockey_id}/runs/")

    def get_jockey_stats(self, jockey_id: int) -> APIResponse:
        """Get stats for a jockey."""
        return self._get(f"/jockeys/{jockey_id}/stats/")

    # =========================================================================
    # Trainer Endpoints
    # =========================================================================

    def get_trainers(
        self,
        name: str | None = None,
        location: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> APIResponse:
        """Get list of trainers."""
        params = self._build_params(
            name=name, location=location, page=page, page_size=page_size
        )
        return self._get("/trainers/", params)

    def get_trainer(self, trainer_id: int) -> APIResponse:
        """Get a single trainer by ID."""
        return self._get(f"/trainers/{trainer_id}/")

    def get_trainer_runs(self, trainer_id: int) -> APIResponse:
        """Get all runs for a trainer."""
        return self._get(f"/trainers/{trainer_id}/runs/")

    def get_trainer_stats(self, trainer_id: int) -> APIResponse:
        """Get stats for a trainer."""
        return self._get(f"/trainers/{trainer_id}/stats/")

    # =========================================================================
    # Owner Endpoints
    # =========================================================================

    def get_owners(self, page: int = 1, page_size: int = 100) -> APIResponse:
        """Get list of owners."""
        params = self._build_params(page=page, page_size=page_size)
        return self._get("/owners/", params)

    def get_owner(self, owner_id: int) -> APIResponse:
        """Get a single owner by ID."""
        return self._get(f"/owners/{owner_id}/")

    # =========================================================================
    # Breeder Endpoints
    # =========================================================================

    def get_breeders(self, page: int = 1, page_size: int = 100) -> APIResponse:
        """Get list of breeders."""
        params = self._build_params(page=page, page_size=page_size)
        return self._get("/breeders/", params)

    def get_breeder(self, breeder_id: int) -> APIResponse:
        """Get a single breeder by ID."""
        return self._get(f"/breeders/{breeder_id}/")

    # =========================================================================
    # Race Endpoints
    # =========================================================================

    def get_races(
        self,
        date: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        course_id: int | None = None,
        region: str | None = None,
        race_type: str | None = None,
        race_class: str | None = None,
        pattern: str | None = None,
        surface: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> APIResponse:
        """Get list of races."""
        params = self._build_params(
            date=date,
            date_from=date_from,
            date_to=date_to,
            course_id=course_id,
            region=region,
            race_type=race_type,
            race_class=race_class,
            pattern=pattern,
            surface=surface,
            page=page,
            page_size=page_size,
        )
        return self._get("/races/", params)

    def get_race(self, race_id: int) -> APIResponse:
        """Get a single race by ID."""
        return self._get(f"/races/{race_id}/")

    def get_race_with_runs(self, race_id: int) -> APIResponse:
        """Get race with all runners included."""
        return self._get(f"/races/{race_id}/with-runs/")

    def get_racecard(self, race_id: int) -> APIResponse:
        """
        Get race with all runners and Betfair ID mappings.

        Returns a complete racecard with:
        - Racing Post: race_id, horse_id
        - Betfair: market_id, selection_id
        - Runner details: name, jockey, trainer, weight, OR
        - Mapping metadata: confidence, method, needs_review
        """
        return self._get(f"/races/{race_id}/racecard/")

    # =========================================================================
    # Run Endpoints
    # =========================================================================

    def get_runs(
        self,
        race_id: int | None = None,
        horse_id: int | None = None,
        jockey_id: int | None = None,
        trainer_id: int | None = None,
        owner_id: int | None = None,
        date: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        region: str | None = None,
        position: str | None = None,
        won: bool | None = None,
        placed: bool | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> APIResponse:
        """Get list of runs (results)."""
        params = self._build_params(
            race_id=race_id,
            horse_id=horse_id,
            jockey_id=jockey_id,
            trainer_id=trainer_id,
            owner_id=owner_id,
            date=date,
            date_from=date_from,
            date_to=date_to,
            region=region,
            position=position,
            won=won,
            placed=placed,
            page=page,
            page_size=page_size,
        )
        return self._get("/runs/", params)

    def get_run(self, run_id: int) -> APIResponse:
        """Get a single run by ID."""
        return self._get(f"/runs/{run_id}/")

    # =========================================================================
    # Betfair Price Endpoints
    # =========================================================================

    def get_betfair_prices(
        self, page: int = 1, page_size: int = 100
    ) -> APIResponse:
        """Get list of Betfair prices."""
        params = self._build_params(page=page, page_size=page_size)
        return self._get("/betfair-prices/", params)

    def get_betfair_price(self, run_id: int) -> APIResponse:
        """Get Betfair price for a run."""
        return self._get(f"/betfair-prices/{run_id}/")

    # =========================================================================
    # Betfair Mapping Endpoints
    # =========================================================================

    def get_mappings(
        self,
        race_id: int | None = None,
        horse_id: int | None = None,
        market_id: str | None = None,
        selection_id: int | None = None,
        needs_review: bool | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> APIResponse:
        """Get list of Betfair ID mappings."""
        params = self._build_params(
            race_id=race_id,
            horse_id=horse_id,
            market_id=market_id,
            selection_id=selection_id,
            needs_review=needs_review,
            page=page,
            page_size=page_size,
        )
        return self._get("/mappings/", params)

    def get_mapping(self, mapping_id: int) -> APIResponse:
        """Get a single mapping by ID."""
        return self._get(f"/mappings/{mapping_id}/")

    def get_mappings_by_race(self, race_id: int) -> APIResponse:
        """Get all mappings for a Racing Post race."""
        return self._get(f"/mappings/by-race/{race_id}/")

    def get_mappings_by_market(self, market_id: str) -> APIResponse:
        """Get all mappings for a Betfair market."""
        return self._get(f"/mappings/by-market/{market_id}/")

    def create_mappings(self, mappings: list[dict]) -> APIResponse:
        """
        Create or update Betfair ID mappings.

        Args:
            mappings: List of mapping dicts with:
                - race_id: Racing Post race ID
                - horse_id: Racing Post horse ID
                - market_id: Betfair market ID
                - selection_id: Betfair selection ID
                - rp_horse_name: (optional) Racing Post horse name
                - bf_runner_name: (optional) Betfair runner name
                - match_confidence: (optional) 0.0-1.0
                - match_method: (optional) "exact", "fuzzy", or "manual"

        Returns:
            APIResponse with created/updated counts
        """
        return self._post("/mappings/create/", {"mappings": mappings})

    def auto_match(
        self,
        race_id: int,
        market_id: str,
        betfair_runners: list[dict],
    ) -> APIResponse:
        """
        Auto-match Racing Post runners to Betfair runners by name.

        Args:
            race_id: Racing Post race ID
            market_id: Betfair market ID
            betfair_runners: List of Betfair runners with:
                - selection_id: Betfair selection ID
                - name: Runner name

        Returns:
            APIResponse with match results
        """
        return self._post("/mappings/auto-match/", {
            "race_id": race_id,
            "market_id": market_id,
            "betfair_runners": betfair_runners,
        })

    # =========================================================================
    # Pagination Helpers
    # =========================================================================

    def iter_all(
        self,
        endpoint_method,
        page_size: int = 100,
        **filters,
    ) -> Iterator[dict]:
        """
        Iterate through all pages of a paginated endpoint.

        Args:
            endpoint_method: The get_* method to call (e.g., self.get_races)
            page_size: Number of items per page
            **filters: Additional filter parameters

        Yields:
            Individual items from each page
        """
        page = 1
        while True:
            response = endpoint_method(page=page, page_size=page_size, **filters)
            if not response.success:
                break

            results = response.data.get("results", [])
            if not results:
                break

            yield from results

            if not response.data.get("next"):
                break

            page += 1

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _get(self, endpoint: str, params: dict | None = None) -> APIResponse:
        """Make a GET request."""
        url = f"{self.base_url}{endpoint}"
        if params:
            url = f"{url}?{urlencode(params)}"

        try:
            response = self.session.get(url)
            return self._handle_response(response)
        except requests.RequestException as e:
            return APIResponse(success=False, data=None, error=str(e))

    def _post(self, endpoint: str, data: dict) -> APIResponse:
        """Make a POST request."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.post(url, json=data)
            return self._handle_response(response)
        except requests.RequestException as e:
            return APIResponse(success=False, data=None, error=str(e))

    def _handle_response(self, response: requests.Response) -> APIResponse:
        """Handle API response."""
        try:
            data = response.json()
        except ValueError:
            data = None

        if response.status_code >= 400:
            error = data.get("error") if isinstance(data, dict) else str(data)
            return APIResponse(
                success=False,
                data=data,
                error=error,
                status_code=response.status_code,
            )

        return APIResponse(
            success=True,
            data=data,
            status_code=response.status_code,
        )

    def _build_params(self, **kwargs) -> dict:
        """Build query parameters, excluding None values."""
        params = {}
        for key, value in kwargs.items():
            if value is not None:
                # Convert booleans to lowercase strings for Django
                if isinstance(value, bool):
                    params[key] = str(value).lower()
                else:
                    params[key] = value
        return params


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    api = RacingPostAPI()

    # Test connection
    print("Testing API connection...")
    response = api.get_courses(page_size=3)
    if response.success:
        print(f"Connected! Found {response.data.get('count', 0)} courses")
    else:
        print(f"Connection failed: {response.error}")
        exit(1)

    # Example: Get races for a specific date
    print("\nRaces on 2026-01-06:")
    response = api.get_races(date="2026-01-06", page_size=5)
    if response.success:
        for race in response.data.get("results", []):
            print(f"  {race['race_id']}: {race['race_name'][:50]}")

    # Example: Get winners
    print("\nRecent winners:")
    response = api.get_runs(won=True, page_size=5)
    if response.success:
        for run in response.data.get("results", []):
            print(f"  {run['horse_name']} (SP: {run['sp_decimal']})")

    # Example: Jockey stats
    print("\nJockey stats:")
    response = api.get_jockeys(name="cosgrave", page_size=1)
    if response.success and response.data.get("results"):
        jockey = response.data["results"][0]
        stats = api.get_jockey_stats(jockey["jockey_id"])
        if stats.success:
            print(f"  {stats.data['name']}: {stats.data['wins']} wins, {stats.data['win_rate']}% win rate")

    # Example: Scrape new data
    # print("\nScraping 2026/01/07...")
    # response = api.scrape(date="2026/01/07", region="gb")
    # if response.success:
    #     print(f"  Created: {response.data['races_created']} races, {response.data['runs_created']} runs")
