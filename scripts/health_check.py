#!/usr/bin/env python3
"""
🏥 Racing Post API Health Check
================================
Quick verification that the scraping system is running correctly.

Usage:
    python scripts/health_check.py              # Check localhost (dev)
    python scripts/health_check.py --prod       # Check prod (PROD_API_URL env var)
    python scripts/health_check.py --url http://custom:8000  # Custom URL

Checks:
    ✅ API connectivity
    ✅ Data scraped today (racecards + results)
    ✅ Row counts for all tables
    ✅ Key fields populated
    ✅ Data freshness
"""

import argparse
import sys
import os
from datetime import datetime, date, timedelta
from dataclasses import dataclass

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_wrapper import RacingPostAPI, APIResponse


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

DEV_URL = "http://localhost:8000/api/racing-post"
PROD_URL = os.getenv("PROD_API_URL", "http://localhost:8000/api/racing-post")


# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def c(text, color):
    """Colorize text."""
    return f"{color}{text}{Colors.RESET}"


def header(title, emoji=""):
    """Print section header."""
    print(f"\n{c('═' * 60, Colors.CYAN)}")
    print(f"  {emoji} {c(title, Colors.BOLD)}")
    print(f"{c('═' * 60, Colors.CYAN)}")


def subheader(title):
    """Print subsection header."""
    print(f"\n  {c(f'▸ {title}', Colors.CYAN)}")


def ok(msg):
    print(f"    {c('✓', Colors.GREEN)} {msg}")


def fail(msg):
    print(f"    {c('✗', Colors.RED)} {msg}")


def warn(msg):
    print(f"    {c('⚠', Colors.YELLOW)} {msg}")


def info(msg):
    print(f"    {c('ℹ', Colors.BLUE)} {msg}")


def dim(msg):
    print(f"    {c(msg, Colors.DIM)}")


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK RESULTS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CheckResult:
    """Result of a single check."""
    name: str
    passed: bool
    message: str
    value: any = None


class HealthReport:
    """Collects all health check results."""

    def __init__(self):
        self.checks: list[CheckResult] = []
        self.environment = "unknown"
        self.api_url = ""
        self.timestamp = datetime.now()

    def add(self, name: str, passed: bool, message: str, value=None):
        self.checks.append(CheckResult(name, passed, message, value))

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_connectivity(api: RacingPostAPI, report: HealthReport):
    """Check API is reachable."""
    subheader("API Connectivity")

    response = api.get_courses(page_size=1)
    if response.success:
        ok(f"API responding at {api.base_url}")
        report.add("connectivity", True, "API reachable")
    else:
        fail(f"Cannot connect: {response.error}")
        report.add("connectivity", False, f"Connection failed: {response.error}")


def check_table_counts(api: RacingPostAPI, report: HealthReport):
    """Check row counts for all tables."""
    subheader("Table Row Counts")

    # Expected minimum counts for a healthy database
    # NOTE: For fresh deployments, these will fail - use --fresh flag to lower thresholds
    expected_minimums = {
        "courses": 1,         # At least 1 course
        "horses": 50,         # At least some horses
        "jockeys": 10,        # At least some jockeys
        "trainers": 10,       # At least some trainers
        "races": 1,           # At least 1 race
        "runs": 5,            # At least some runs
    }

    tables = [
        ("courses", api.get_courses),
        ("horses", api.get_horses),
        ("jockeys", api.get_jockeys),
        ("trainers", api.get_trainers),
        ("races", api.get_races),
        ("runs", api.get_runs),
        ("racecard_entries", api.get_racecard_entries),
        ("horse_race_stats", api.get_horse_race_stats),
        ("jockey_stats_daily", api.get_jockey_stats_daily),
        ("trainer_stats_daily", api.get_trainer_stats_daily),
        ("betfair_prices", api.get_betfair_prices),
        ("mappings", api.get_mappings),
    ]

    counts = {}
    for name, method in tables:
        response = method(page_size=1)
        if response.success:
            count = response.data.get("count", 0)
            counts[name] = count

            # Check against minimum
            min_expected = expected_minimums.get(name, 0)
            if count >= min_expected:
                ok(f"{name}: {count:,}")
            elif count > 0:
                warn(f"{name}: {count:,} (expected ≥{min_expected})")
            else:
                info(f"{name}: 0 (empty)")
        else:
            fail(f"{name}: ERROR - {response.error}")
            counts[name] = -1

    # Add to report
    for name, count in counts.items():
        min_expected = expected_minimums.get(name, 0)
        passed = count >= min_expected
        report.add(f"count_{name}", passed, f"{name}: {count}", count)


def check_data_freshness(api: RacingPostAPI, report: HealthReport):
    """Check if data was collected today/recently."""
    subheader("Data Freshness")

    today = date.today()
    yesterday = today - timedelta(days=1)
    today_str = today.strftime("%Y-%m-%d")
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    # Check for today's racecards
    response = api.get_racecard_entries(scrape_date=today_str, page_size=1)
    if response.success:
        count = response.data.get("count", 0)
        if count > 0:
            ok(f"Racecards scraped today: {count} entries")
            report.add("racecards_today", True, f"{count} entries", count)
        else:
            warn(f"No racecards scraped today yet")
            report.add("racecards_today", False, "No racecards today", 0)
    else:
        fail(f"Cannot check racecards: {response.error}")
        report.add("racecards_today", False, response.error)

    # Check for today's jockey/trainer stats (only available day-of)
    response = api.get_jockey_stats_daily(scrape_date=today_str, page_size=1)
    if response.success:
        count = response.data.get("count", 0)
        if count > 0:
            ok(f"Jockey stats scraped today: {count} records")
        else:
            info(f"No jockey stats today (scraped with racecards)")

    # Check for yesterday's results
    response = api.get_races(date=yesterday_str, page_size=1)
    if response.success:
        count = response.data.get("count", 0)
        if count > 0:
            ok(f"Yesterday's races in DB: {count} races")
            report.add("results_yesterday", True, f"{count} races", count)
        else:
            warn(f"No races for yesterday ({yesterday_str})")
            report.add("results_yesterday", False, "No races yesterday", 0)
    else:
        fail(f"Cannot check races: {response.error}")
        report.add("results_yesterday", False, response.error)

    # Check most recent race date
    response = api.get_races(page_size=1)
    if response.success and response.data.get("results"):
        latest_race = response.data["results"][0]
        latest_date = latest_race.get("date", "unknown")
        info(f"Most recent race in DB: {latest_date}")


def check_field_population(api: RacingPostAPI, report: HealthReport):
    """Check that key fields are being populated."""
    subheader("Field Population")

    # Check horses have pedigree data
    response = api.get_horses(page_size=20)
    if response.success and response.data.get("results"):
        horses = response.data["results"][:10]
        with_sire = 0
        with_dam = 0

        for horse in horses:
            horse_id = horse.get("horse_id")
            detail = api.get_horse(horse_id)
            if detail.success and detail.data:
                if detail.data.get("sire"):
                    with_sire += 1
                if detail.data.get("dam"):
                    with_dam += 1

        total = len(horses)
        if with_sire > 0:
            ok(f"Horses with sire: {with_sire}/{total}")
            report.add("pedigree_sire", True, f"{with_sire}/{total}", with_sire)
        else:
            fail(f"No horses have sire data! Pedigree not saving.")
            report.add("pedigree_sire", False, "No sire data", 0)

        if with_dam > 0:
            ok(f"Horses with dam: {with_dam}/{total}")
        else:
            warn(f"No horses have dam data")

    # Check runs have key fields
    response = api.get_runs(page_size=50)
    if response.success and response.data.get("results"):
        runs = response.data["results"]
        with_sp = sum(1 for r in runs if r.get("sp_decimal"))
        with_position = sum(1 for r in runs if r.get("position"))
        with_weight = sum(1 for r in runs if r.get("weight_lbs"))

        total = len(runs)
        ok(f"Runs with SP: {with_sp}/{total}")
        ok(f"Runs with position: {with_position}/{total}")
        info(f"Runs with weight: {with_weight}/{total}")

        sp_pct = (with_sp / total * 100) if total > 0 else 0
        report.add("runs_sp", sp_pct >= 80, f"{with_sp}/{total} ({sp_pct:.0f}%)", with_sp)

    # Check racecard entries have stats
    response = api.get_racecard_entries(page_size=30)
    if response.success and response.data.get("results"):
        entries = response.data["results"]
        with_form = sum(1 for e in entries if e.get("form"))
        with_rating = sum(1 for e in entries if e.get("official_rating"))

        total = len(entries)
        info(f"Entries with form: {with_form}/{total}")
        info(f"Entries with rating: {with_rating}/{total}")


def check_betfair_data(api: RacingPostAPI, report: HealthReport):
    """Check Betfair BSP data is being collected."""
    subheader("Betfair Data")

    response = api.get_betfair_prices(page_size=20)
    if response.success:
        count = response.data.get("count", 0)
        if count > 0:
            prices = response.data.get("results", [])
            with_bsp = sum(1 for p in prices if p.get("bsp"))

            ok(f"Betfair prices: {count:,} total")
            info(f"Sample with BSP: {with_bsp}/{len(prices)}")
            report.add("betfair_bsp", True, f"{count} prices", count)
        else:
            warn("No Betfair prices in database")
            report.add("betfair_bsp", False, "No BSP data", 0)
    else:
        fail(f"Cannot check Betfair: {response.error}")
        report.add("betfair_bsp", False, response.error)


def check_data_relationships(api: RacingPostAPI, report: HealthReport):
    """Check data integrity - relationships between tables."""
    subheader("Data Relationships")

    # Get race count and run count
    races_resp = api.get_races(page_size=1)
    runs_resp = api.get_runs(page_size=1)

    if races_resp.success and runs_resp.success:
        race_count = races_resp.data.get("count", 0)
        run_count = runs_resp.data.get("count", 0)

        if race_count > 0:
            avg_runners = run_count / race_count
            if avg_runners >= 5:
                ok(f"Avg runners per race: {avg_runners:.1f}")
                report.add("avg_runners", True, f"{avg_runners:.1f}", avg_runners)
            elif avg_runners >= 1:
                warn(f"Low avg runners per race: {avg_runners:.1f}")
                report.add("avg_runners", False, f"{avg_runners:.1f} (low)", avg_runners)
            else:
                fail(f"Very low runners: {avg_runners:.1f}")
                report.add("avg_runners", False, f"{avg_runners:.1f}", avg_runners)

    # Check a sample race has runs
    races_resp = api.get_races(page_size=1)
    if races_resp.success and races_resp.data.get("results"):
        race = races_resp.data["results"][0]
        race_id = race.get("race_id")

        race_detail = api.get_race_with_runs(race_id)
        if race_detail.success and race_detail.data:
            runs = race_detail.data.get("runs", [])
            if runs:
                ok(f"Sample race {race_id} has {len(runs)} runners")
            else:
                warn(f"Sample race {race_id} has no runners linked")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run_health_check(api_url: str, environment: str) -> HealthReport:
    """Run all health checks and return report."""
    report = HealthReport()
    report.environment = environment
    report.api_url = api_url

    api = RacingPostAPI(base_url=api_url)

    # Print header
    print(f"\n{c('🏥 RACING POST API HEALTH CHECK', Colors.BOLD)}")
    print(f"   {c(f'Environment: {environment.upper()}', Colors.CYAN)}")
    print(f"   {c(f'API: {api_url}', Colors.DIM)}")
    time_str = report.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    print(f"   {c(f'Time: {time_str}', Colors.DIM)}")

    # Run checks
    header("Connectivity", "🔌")
    check_connectivity(api, report)

    if report.all_passed:  # Only continue if API is reachable
        header("Database Status", "💾")
        check_table_counts(api, report)

        header("Data Freshness", "📅")
        check_data_freshness(api, report)

        header("Data Quality", "🔍")
        check_field_population(api, report)
        check_betfair_data(api, report)
        check_data_relationships(api, report)

    # Summary
    header("Summary", "📊")
    print()

    if report.all_passed:
        print(f"    {c('✅ ALL CHECKS PASSED', Colors.GREEN + Colors.BOLD)}")
    else:
        print(f"    {c(f'❌ {report.failed} CHECK(S) FAILED', Colors.RED + Colors.BOLD)}")

    print(f"\n    Passed: {c(str(report.passed), Colors.GREEN)}")
    print(f"    Failed: {c(str(report.failed), Colors.RED if report.failed else Colors.DIM)}")

    # List failures
    if report.failed > 0:
        print(f"\n    {c('Failed checks:', Colors.YELLOW)}")
        for check in report.checks:
            if not check.passed:
                print(f"      • {check.name}: {check.message}")

    print(f"\n{c('═' * 60, Colors.CYAN)}\n")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Racing Post API Health Check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/health_check.py           # Check dev (localhost)
  python scripts/health_check.py --prod    # Check prod (PROD_API_URL)
  python scripts/health_check.py --url http://custom:8000/api/racing-post
        """
    )
    parser.add_argument(
        "--prod", action="store_true",
        help="Check production server (set PROD_API_URL in .env)"
    )
    parser.add_argument(
        "--url", type=str,
        help="Custom API URL (overrides --prod)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Determine URL and environment
    if args.url:
        api_url = args.url
        environment = "custom"
    elif args.prod:
        api_url = PROD_URL
        environment = "prod"
    else:
        api_url = DEV_URL
        environment = "dev"

    # Run health check
    report = run_health_check(api_url, environment)

    # JSON output if requested
    if args.json:
        import json
        output = {
            "environment": report.environment,
            "api_url": report.api_url,
            "timestamp": report.timestamp.isoformat(),
            "passed": report.passed,
            "failed": report.failed,
            "all_passed": report.all_passed,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                    "value": c.value
                }
                for c in report.checks
            ]
        }
        print(json.dumps(output, indent=2))

    # Exit with appropriate code
    sys.exit(0 if report.all_passed else 1)


if __name__ == "__main__":
    main()
