"""
Racing Post Database Integrity Tests
=====================================
Tests API connectivity, data structure, and integrity.

Run: python tests/test_database_integrity.py
"""

import sys
import os

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

import requests
from datetime import datetime, timedelta
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

API_BASE = "http://localhost:8000/api/racing-post"

ENDPOINTS = {
    # Core Reference
    "courses": f"{API_BASE}/courses/",
    "horses": f"{API_BASE}/horses/",
    "jockeys": f"{API_BASE}/jockeys/",
    "trainers": f"{API_BASE}/trainers/",
    "owners": f"{API_BASE}/owners/",
    "breeders": f"{API_BASE}/breeders/",
    # Race Data
    "races": f"{API_BASE}/races/",
    "runs": f"{API_BASE}/runs/",
    "betfair_prices": f"{API_BASE}/betfair-prices/",
    "mappings": f"{API_BASE}/mappings/",
    # Racecard & Stats
    "racecard_entries": f"{API_BASE}/racecard-entries/",
    "horse_race_stats": f"{API_BASE}/horse-race-stats/",
    "jockey_stats": f"{API_BASE}/jockey-stats/",
    "trainer_stats": f"{API_BASE}/trainer-stats/",
    "trainer_history": f"{API_BASE}/trainer-history/",
    "owner_history": f"{API_BASE}/owner-history/",
    "medical": f"{API_BASE}/medical/",
}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def c(text, color):
    return f"{color}{text}{Colors.RESET}"


def ok(msg):
    print(f"  {c('✓', Colors.GREEN)} {msg}")


def fail(msg):
    print(f"  {c('✗', Colors.RED)} {msg}")


def warn(msg):
    print(f"  {c('⚠', Colors.YELLOW)} {msg}")


def info(msg):
    print(f"  {c('ℹ', Colors.BLUE)} {msg}")


def header(title):
    print(f"\n{c('═' * 60, Colors.CYAN)}")
    print(f"{c(f'  {title}', Colors.BOLD)}")
    print(f"{c('═' * 60, Colors.CYAN)}")


def subheader(title):
    print(f"\n{c(f'▸ {title}', Colors.CYAN)}")


def get_json(url, params=None):
    """Fetch JSON from API with error handling."""
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def get_count(url, params=None):
    """Get count from paginated endpoint."""
    data = get_json(url, params)
    if "error" in data:
        return -1
    return data.get("count", len(data.get("results", [])))


def get_all_pages(url, params=None, max_pages=10):
    """Fetch all pages from paginated endpoint."""
    params = params or {}
    params["page_size"] = 1000
    all_results = []

    for page in range(1, max_pages + 1):
        params["page"] = page
        data = get_json(url, params)
        if "error" in data or not data.get("results"):
            break
        all_results.extend(data["results"])
        if not data.get("next"):
            break

    return all_results


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors = []

    def add_pass(self, msg):
        self.passed += 1
        ok(msg)

    def add_fail(self, msg):
        self.failed += 1
        self.errors.append(msg)
        fail(msg)

    def add_warn(self, msg):
        self.warnings += 1
        warn(msg)

    def summary(self):
        header("TEST SUMMARY")
        total = self.passed + self.failed
        print(f"\n  {c('Passed:', Colors.GREEN)} {self.passed}/{total}")
        print(f"  {c('Failed:', Colors.RED)} {self.failed}/{total}")
        print(f"  {c('Warnings:', Colors.YELLOW)} {self.warnings}")

        if self.errors:
            print(f"\n  {c('Errors:', Colors.RED)}")
            for err in self.errors:
                print(f"    • {err}")

        return self.failed == 0


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_api_connectivity(results: TestResults):
    """Test basic API connectivity."""
    header("1️⃣  API CONNECTIVITY")

    try:
        resp = requests.get(f"{API_BASE}/courses/", timeout=10)
        if resp.status_code == 200:
            results.add_pass(f"API reachable at {API_BASE}")
        else:
            results.add_fail(f"API returned status {resp.status_code}")
    except requests.exceptions.RequestException as e:
        results.add_fail(f"Cannot connect to API: {e}")
        return False

    return True


def test_endpoint_availability(results: TestResults):
    """Test all endpoints are available."""
    header("2️⃣  ENDPOINT AVAILABILITY")

    for name, url in ENDPOINTS.items():
        data = get_json(url)
        if "error" in data:
            results.add_fail(f"{name}: {data['error']}")
        else:
            count = data.get("count", len(data.get("results", [])))
            results.add_pass(f"{name}: {count:,} records")


def test_data_counts(results: TestResults):
    """Test data counts and relationships."""
    header("3️⃣  DATA COUNTS & RELATIONSHIPS")

    counts = {}
    for name, url in ENDPOINTS.items():
        counts[name] = get_count(url)

    # Core tables should have data
    subheader("Core Tables")
    core_tables = ["courses", "horses", "jockeys", "trainers", "races", "runs"]
    for table in core_tables:
        if counts.get(table, 0) > 0:
            results.add_pass(f"{table}: {counts[table]:,} records")
        else:
            results.add_fail(f"{table}: EMPTY (expected data)")

    # Relationship checks
    subheader("Relationship Checks")

    # More runs than races (multiple runners per race)
    if counts.get("races", 0) > 0 and counts.get("runs", 0) > 0:
        avg_runners = counts["runs"] / counts["races"]
        if avg_runners >= 1:
            results.add_pass(f"Avg runners/race: {avg_runners:.1f}")
        else:
            results.add_warn(f"Low avg runners/race: {avg_runners:.1f}")

    # Horses should be >= runs (but not way more)
    if counts.get("horses", 0) > 0 and counts.get("runs", 0) > 0:
        runs_per_horse = counts["runs"] / counts["horses"]
        info(f"Avg runs/horse: {runs_per_horse:.1f}")


def test_race_data_integrity(results: TestResults):
    """Test race data integrity."""
    header("4️⃣  RACE DATA INTEGRITY")

    # Sample recent races
    subheader("Recent Race Structure")
    races = get_json(ENDPOINTS["races"], {"page_size": 10})

    if "error" in races:
        results.add_fail(f"Cannot fetch races: {races['error']}")
        return

    race_list = races.get("results", [])
    if not race_list:
        results.add_warn("No races found")
        return

    # Check required fields (API returns course_id and course_name, not course)
    required_fields = ["race_id", "course_id", "date", "off_time"]
    for race in race_list[:3]:
        race_id = race.get("race_id", "Unknown")
        missing = [f for f in required_fields if not race.get(f)]
        if missing:
            results.add_fail(f"Race {race_id}: Missing {missing}")
        else:
            results.add_pass(f"Race {race_id}: All required fields present")

    # Check a race has runners
    subheader("Race → Runs Relationship")
    if race_list:
        test_race = race_list[0]
        race_id = test_race["race_id"]
        runs = get_json(ENDPOINTS["runs"], {"race_id": race_id})

        if "error" not in runs:
            run_count = runs.get("count", 0)
            if run_count > 0:
                results.add_pass(f"Race {race_id} has {run_count} runners")
            else:
                results.add_warn(f"Race {race_id} has no runners")


def test_run_data_integrity(results: TestResults):
    """Test run/result data integrity."""
    header("5️⃣  RUN DATA INTEGRITY")

    runs = get_json(ENDPOINTS["runs"], {"page_size": 50})

    if "error" in runs:
        results.add_fail(f"Cannot fetch runs: {runs['error']}")
        return

    run_list = runs.get("results", [])
    if not run_list:
        results.add_warn("No runs found")
        return

    # Check required fields (API returns race_id and horse_id)
    subheader("Required Fields")
    required = ["race_id", "horse_id"]
    missing_count = 0

    for run in run_list:
        for field in required:
            if not run.get(field):
                missing_count += 1

    if missing_count == 0:
        results.add_pass(f"All {len(run_list)} runs have required FK references")
    else:
        results.add_fail(f"{missing_count} runs missing FK references")

    # Check position data
    subheader("Position Data")
    positions = [r.get("position_numeric") for r in run_list if r.get("position_numeric")]
    non_runners = [r for r in run_list if r.get("non_runner")]

    info(f"Runs with position: {len(positions)}/{len(run_list)}")
    info(f"Non-runners: {len(non_runners)}")

    # SP data
    subheader("SP (Starting Price) Data")
    sp_count = sum(1 for r in run_list if r.get("sp_decimal"))
    sp_pct = (sp_count / len(run_list) * 100) if run_list else 0

    if sp_pct >= 80:
        results.add_pass(f"SP coverage: {sp_pct:.0f}% ({sp_count}/{len(run_list)})")
    elif sp_pct >= 50:
        results.add_warn(f"SP coverage: {sp_pct:.0f}% ({sp_count}/{len(run_list)})")
    else:
        results.add_fail(f"Low SP coverage: {sp_pct:.0f}% ({sp_count}/{len(run_list)})")


def test_betfair_data(results: TestResults):
    """Test Betfair price data."""
    header("6️⃣  BETFAIR DATA")

    bf_count = get_count(ENDPOINTS["betfair_prices"])
    run_count = get_count(ENDPOINTS["runs"])

    if bf_count > 0:
        coverage = (bf_count / run_count * 100) if run_count > 0 else 0
        results.add_pass(f"Betfair prices: {bf_count:,} ({coverage:.1f}% of runs)")

        # Check BSP values
        prices = get_json(ENDPOINTS["betfair_prices"], {"page_size": 50})
        if "error" not in prices:
            price_list = prices.get("results", [])
            bsp_count = sum(1 for p in price_list if p.get("bsp"))
            if bsp_count > 0:
                results.add_pass(f"BSP data present: {bsp_count}/{len(price_list)} sampled")
            else:
                results.add_warn("No BSP values in sample")
    else:
        results.add_warn("No Betfair price data collected")

    # Mappings
    subheader("Betfair Mappings")
    mapping_count = get_count(ENDPOINTS["mappings"])
    if mapping_count > 0:
        results.add_pass(f"Betfair mappings: {mapping_count:,}")

        # Check for low confidence matches
        review_count = get_count(ENDPOINTS["mappings"], {"needs_review": "true"})
        if review_count > 0:
            results.add_warn(f"Mappings needing review: {review_count}")
        else:
            results.add_pass("No mappings flagged for review")
    else:
        info("No Betfair mappings yet")


def test_racecard_data(results: TestResults):
    """Test racecard and stats data."""
    header("7️⃣  RACECARD & STATS DATA")

    # Racecard entries
    subheader("Racecard Entries")
    rc_count = get_count(ENDPOINTS["racecard_entries"])
    if rc_count > 0:
        results.add_pass(f"Racecard entries: {rc_count:,}")
    else:
        results.add_warn("No racecard entries (run racecards.py to collect)")

    # Horse race stats (C/D/G)
    subheader("Horse Race Stats (C/D/G)")
    stats_count = get_count(ENDPOINTS["horse_race_stats"])
    if stats_count > 0:
        results.add_pass(f"Horse race stats: {stats_count:,}")
    else:
        results.add_warn("No C/D/G stats (requires fetch_stats=true)")

    # Jockey/Trainer daily stats
    subheader("Jockey/Trainer Daily Stats")
    jock_stats = get_count(ENDPOINTS["jockey_stats"])
    train_stats = get_count(ENDPOINTS["trainer_stats"])

    if jock_stats > 0:
        results.add_pass(f"Jockey daily stats: {jock_stats:,}")
    else:
        info("No jockey daily stats yet")

    if train_stats > 0:
        results.add_pass(f"Trainer daily stats: {train_stats:,}")
    else:
        info("No trainer daily stats yet")

    # History tracking
    subheader("History Tracking")
    trainer_hist = get_count(ENDPOINTS["trainer_history"])
    owner_hist = get_count(ENDPOINTS["owner_history"])
    medical = get_count(ENDPOINTS["medical"])

    info(f"Trainer changes: {trainer_hist:,}")
    info(f"Owner changes: {owner_hist:,}")
    info(f"Medical records: {medical:,}")


def test_data_quality(results: TestResults):
    """Test overall data quality."""
    header("8️⃣  DATA QUALITY CHECKS")

    # Check for duplicate runs (use race_id and horse_id)
    subheader("Duplicate Detection")
    runs = get_all_pages(ENDPOINTS["runs"], max_pages=5)

    if runs:
        seen = set()
        duplicates = []
        for run in runs:
            key = (run.get("race_id"), run.get("horse_id"))
            if key in seen:
                duplicates.append(key)
            seen.add(key)

        if duplicates:
            results.add_fail(f"Found {len(duplicates)} duplicate run entries")
        else:
            results.add_pass(f"No duplicate runs in sample of {len(runs)}")

    # Check date ranges
    subheader("Date Range Coverage")
    races = get_json(ENDPOINTS["races"], {"page_size": 1, "ordering": "date"})
    races_desc = get_json(ENDPOINTS["races"], {"page_size": 1, "ordering": "-date"})

    if "error" not in races and "error" not in races_desc:
        oldest = races.get("results", [{}])[0].get("date", "Unknown")
        newest = races_desc.get("results", [{}])[0].get("date", "Unknown")

        results.add_pass(f"Date range: {oldest} → {newest}")

    # Check for orphaned data (use race_id and horse_id)
    subheader("Referential Integrity")

    # Sample runs and check FKs exist
    sample_runs = get_json(ENDPOINTS["runs"], {"page_size": 20})
    if "error" not in sample_runs:
        run_list = sample_runs.get("results", [])
        orphaned = 0

        for run in run_list:
            if run.get("race_id") is None or run.get("horse_id") is None:
                orphaned += 1

        if orphaned == 0:
            results.add_pass("All sampled runs have valid FK references")
        else:
            results.add_fail(f"{orphaned} runs with missing FK references")


def test_regional_coverage(results: TestResults):
    """Test coverage by region."""
    header("9️⃣  REGIONAL COVERAGE")

    courses = get_all_pages(ENDPOINTS["courses"], max_pages=5)

    if not courses:
        results.add_warn("No course data available")
        return

    # Group by region
    by_region = defaultdict(list)
    for course in courses:
        region = course.get("region", "Unknown")
        by_region[region].append(course.get("name", "Unknown"))

    subheader("Courses by Region")
    for region, course_list in sorted(by_region.items()):
        info(f"{region}: {len(course_list)} courses")

    # Check key regions
    key_regions = ["GB", "IRE"]
    for region in key_regions:
        if region in by_region:
            results.add_pass(f"{region} courses present: {len(by_region[region])}")
        else:
            results.add_warn(f"No {region} courses found")


def test_horse_pedigree(results: TestResults):
    """Test horse pedigree data."""
    header("🔟  HORSE PEDIGREE DATA")

    # List endpoint doesn't include pedigree - check detail for a sample
    horses = get_json(ENDPOINTS["horses"], {"page_size": 10})

    if "error" in horses:
        results.add_fail(f"Cannot fetch horses: {horses['error']}")
        return

    horse_list = horses.get("results", [])
    if not horse_list:
        results.add_warn("No horses found")
        return

    # Check pedigree by fetching detail for sample horses
    subheader("Pedigree Coverage (sample of 5)")
    sample_ids = [h["horse_id"] for h in horse_list[:5]]

    with_sire = 0
    with_dam = 0
    with_damsire = 0

    for horse_id in sample_ids:
        detail = get_json(f"{ENDPOINTS['horses']}{horse_id}/")
        if "error" not in detail:
            if detail.get("sire"):
                with_sire += 1
            if detail.get("dam"):
                with_dam += 1
            if detail.get("damsire"):
                with_damsire += 1

    total = len(sample_ids)
    info(f"With sire: {with_sire}/{total}")
    info(f"With dam: {with_dam}/{total}")
    info(f"With damsire: {with_damsire}/{total}")

    if with_sire >= total * 0.5:
        results.add_pass("Good sire coverage")
    else:
        results.add_warn("Low sire coverage - check if scraper collects pedigree")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{c('🏇 RACING POST DATABASE INTEGRITY TESTS', Colors.BOLD)}")
    print(f"{c(f'   Target: {API_BASE}', Colors.CYAN)}")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{c(f'   Time: {timestamp}', Colors.CYAN)}")

    results = TestResults()

    # Run tests
    if not test_api_connectivity(results):
        print(f"\n{c('❌ Cannot connect to API. Aborting tests.', Colors.RED)}")
        sys.exit(1)

    test_endpoint_availability(results)
    test_data_counts(results)
    test_race_data_integrity(results)
    test_run_data_integrity(results)
    test_betfair_data(results)
    test_racecard_data(results)
    test_data_quality(results)
    test_regional_coverage(results)
    test_horse_pedigree(results)

    # Summary
    success = results.summary()

    print(f"\n{c('=' * 60, Colors.CYAN)}\n")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
