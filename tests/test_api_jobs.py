"""
🧪 Racing Post API Jobs Test
==============================
Tests AM (racecards) and PM (results) jobs, then verifies database accuracy.

Run: python tests/test_api_jobs.py
"""

import sys
import os
import json
from datetime import datetime, timedelta

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

import requests

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

API_BASE = os.getenv("API_URL", "http://localhost:8000/api/racing-post")
REGION = "gb"
TIMEOUT = 300  # 5 minutes for scraping


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
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


def c(text, color):
    return f"{color}{text}{Colors.RESET}"


def header(title):
    print(f"\n{c('═' * 60, Colors.CYAN)}")
    print(f"{c(f'  {title}', Colors.BOLD)}")
    print(f"{c('═' * 60, Colors.CYAN)}")


def subheader(title):
    print(f"\n{c(f'▸ {title}', Colors.CYAN)}")


def ok(msg):
    print(f"  {c('✓', Colors.GREEN)} {msg}")


def fail(msg):
    print(f"  {c('✗', Colors.RED)} {msg}")


def warn(msg):
    print(f"  {c('⚠', Colors.YELLOW)} {msg}")


def info(msg):
    print(f"  {c('ℹ', Colors.BLUE)} {msg}")


def step(msg):
    print(f"\n{c('→', Colors.MAGENTA)} {c(msg, Colors.BOLD)}")


# ═══════════════════════════════════════════════════════════════════════════════
# API CALLS
# ═══════════════════════════════════════════════════════════════════════════════

def api_post(endpoint, data, timeout=TIMEOUT):
    """POST to API endpoint."""
    try:
        resp = requests.post(
            f"{API_BASE}/{endpoint}/",
            json=data,
            timeout=timeout
        )
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def api_get(endpoint, params=None):
    """GET from API endpoint."""
    try:
        resp = requests.get(
            f"{API_BASE}/{endpoint}/",
            params=params,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


# ═══════════════════════════════════════════════════════════════════════════════
# AM JOB: RACECARDS
# ═══════════════════════════════════════════════════════════════════════════════

def run_am_job():
    """Run AM job: scrape and sync racecards."""
    header("🌅 AM JOB: Racecards")

    results = {
        "success": False,
        "races": 0,
        "entries_created": 0,
        "date": "",
        "errors": []
    }

    # Step 1: Scrape racecards
    step("Scraping racecards from Racing Post...")
    info(f"Region: {REGION}, Day: 1 (today)")

    scrape_data, err = api_post("scrape-racecards", {
        "day": 1,
        "region": REGION,
        "fetch_stats": True,
        "fetch_profiles": True
    })

    if err:
        fail(f"Scrape failed: {err}")
        results["errors"].append(f"Scrape: {err}")
        return results

    results["races"] = scrape_data.get("races", 0)
    results["date"] = scrape_data.get("date", "")

    ok(f"Scraped {results['races']} races for {results['date']}")

    if results["races"] == 0:
        warn("No races found - maybe no racing today?")
        results["success"] = True
        return results

    # Step 2: Sync to database
    step("Syncing to database...")

    sync_data, err = api_post("sync-racecards", {
        "data": scrape_data.get("data", {}),
        "scrape_date": results["date"]
    })

    if err:
        fail(f"Sync failed: {err}")
        results["errors"].append(f"Sync: {err}")
        return results

    results["entries_created"] = sync_data.get("entries_created", 0)
    results["entries_updated"] = sync_data.get("entries_updated", 0)
    results["stats_created"] = sync_data.get("stats_created", 0)
    results["jockey_stats"] = sync_data.get("jockey_stats_created", 0)
    results["trainer_stats"] = sync_data.get("trainer_stats_created", 0)

    ok(f"Entries: {results['entries_created']} created, {results.get('entries_updated', 0)} updated")
    ok(f"Horse stats (C/D/G): {results['stats_created']}")
    ok(f"Jockey daily stats: {results['jockey_stats']}")
    ok(f"Trainer daily stats: {results['trainer_stats']}")

    if sync_data.get("errors"):
        for e in sync_data["errors"][:5]:
            warn(f"Sync warning: {e}")

    results["success"] = True
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# PM JOB: RESULTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_pm_job(date=None):
    """Run PM job: scrape results."""
    header("🌙 PM JOB: Results")

    if date is None:
        # Default to yesterday
        yesterday = datetime.now() - timedelta(days=1)
        date = yesterday.strftime("%Y/%m/%d")

    results = {
        "success": False,
        "races_created": 0,
        "races_updated": 0,
        "runs_created": 0,
        "runs_updated": 0,
        "date": date,
        "errors": []
    }

    step(f"Scraping results for {date}...")
    info(f"Region: {REGION}, Betfair: enabled")

    scrape_data, err = api_post("scrape", {
        "date": date,
        "region": REGION,
        "race_type": "all",
        "betfair": True
    }, timeout=600)  # Results can take longer

    if err:
        fail(f"Scrape failed: {err}")
        results["errors"].append(err)
        return results

    results["races_created"] = scrape_data.get("races_created", 0)
    results["races_updated"] = scrape_data.get("races_updated", 0)
    results["runs_created"] = scrape_data.get("runs_created", 0)
    results["runs_updated"] = scrape_data.get("runs_updated", 0)

    total_races = results["races_created"] + results["races_updated"]
    total_runs = results["runs_created"] + results["runs_updated"]

    ok(f"Races: {results['races_created']} created, {results['races_updated']} updated")
    ok(f"Runs: {results['runs_created']} created, {results['runs_updated']} updated")

    if scrape_data.get("errors"):
        for e in scrape_data["errors"][:5]:
            warn(f"Scrape warning: {e}")

    results["success"] = True
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def verify_database():
    """Verify data integrity in database."""
    header("🔍 DATABASE VERIFICATION")

    issues = []

    # Check table counts
    subheader("Table Counts")

    tables = {
        "courses": "courses",
        "horses": "horses",
        "jockeys": "jockeys",
        "trainers": "trainers",
        "races": "races",
        "runs": "runs",
        "racecard_entries": "racecard-entries",
        "horse_race_stats": "horse-race-stats",
        "jockey_stats": "jockey-stats",
        "trainer_stats": "trainer-stats",
        "betfair_prices": "betfair-prices",
    }

    counts = {}
    for name, endpoint in tables.items():
        data, err = api_get(endpoint, {"page_size": 1})
        if err:
            fail(f"{name}: ERROR - {err}")
            issues.append(f"{name}: {err}")
        else:
            count = data.get("count", 0)
            counts[name] = count
            if count > 0:
                ok(f"{name}: {count:,}")
            else:
                info(f"{name}: 0 (empty)")

    # Check pedigree data (THE KEY TEST!)
    subheader("🐴 Pedigree Data (Key Test)")

    horses_data, err = api_get("horses", {"page_size": 10})
    if err:
        fail(f"Cannot fetch horses: {err}")
        issues.append(f"Pedigree check failed: {err}")
    else:
        horse_list = horses_data.get("results", [])
        if horse_list:
            # Check detail for each horse
            with_sire = 0
            with_dam = 0
            with_damsire = 0
            checked = 0

            for horse in horse_list[:5]:
                horse_id = horse.get("horse_id")
                detail, _ = api_get(f"horses/{horse_id}")
                if detail:
                    checked += 1
                    if detail.get("sire"):
                        with_sire += 1
                    if detail.get("dam"):
                        with_dam += 1
                    if detail.get("damsire"):
                        with_damsire += 1

            info(f"Checked {checked} horses:")

            if with_sire > 0:
                ok(f"With sire: {with_sire}/{checked} ✅ PEDIGREE FIX WORKING!")
            else:
                fail(f"With sire: 0/{checked} ❌ Pedigree not saving!")
                issues.append("No sire data found - pedigree fix may not be deployed")

            info(f"With dam: {with_dam}/{checked}")
            info(f"With damsire: {with_damsire}/{checked}")
        else:
            warn("No horses to check")

    # Check race-run relationships
    subheader("Race → Run Relationships")

    if counts.get("races", 0) > 0 and counts.get("runs", 0) > 0:
        avg_runners = counts["runs"] / counts["races"]
        if avg_runners >= 1:
            ok(f"Avg runners/race: {avg_runners:.1f}")
        else:
            warn(f"Low avg runners/race: {avg_runners:.1f}")

    # Check racecard entries have stats
    subheader("Racecard Entry Quality")

    entries_data, err = api_get("racecard-entries", {"page_size": 20})
    if not err and entries_data.get("results"):
        entries = entries_data["results"]
        with_form = sum(1 for e in entries if e.get("form"))
        with_rating = sum(1 for e in entries if e.get("official_rating"))

        info(f"Sample of {len(entries)} entries:")
        info(f"  With form: {with_form}/{len(entries)}")
        info(f"  With rating: {with_rating}/{len(entries)}")

    # Check Betfair data
    subheader("Betfair Data")

    if counts.get("betfair_prices", 0) > 0:
        bf_data, _ = api_get("betfair-prices", {"page_size": 10})
        if bf_data and bf_data.get("results"):
            prices = bf_data["results"]
            with_bsp = sum(1 for p in prices if p.get("bsp"))
            ok(f"Betfair prices: {counts['betfair_prices']} total")
            info(f"  With BSP: {with_bsp}/{len(prices)} sampled")
    else:
        info("No Betfair prices yet")

    # Summary
    subheader("Summary")

    if issues:
        fail(f"Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"    • {issue}")
        return False
    else:
        ok("All checks passed!")
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{c('🧪 RACING POST API JOBS TEST', Colors.BOLD)}")
    print(f"{c(f'   API: {API_BASE}', Colors.CYAN)}")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{c(f'   Time: {timestamp}', Colors.CYAN)}")

    # Check API is reachable
    step("Checking API connectivity...")
    data, err = api_get("courses", {"page_size": 1})
    if err:
        fail(f"Cannot connect to API: {err}")
        sys.exit(1)
    ok("API is reachable")

    # Run AM job
    am_results = run_am_job()

    # Run PM job (yesterday's results)
    pm_results = run_pm_job()

    # Verify database
    db_ok = verify_database()

    # Final summary
    header("📊 FINAL SUMMARY")

    print(f"\n  {c('AM Job (Racecards):', Colors.BOLD)}")
    if am_results["success"]:
        ok(f"Races scraped: {am_results['races']}")
        ok(f"Entries synced: {am_results.get('entries_created', 0)}")
    else:
        fail("AM job failed")
        for e in am_results["errors"]:
            print(f"    • {e}")

    print(f"\n  {c('PM Job (Results):', Colors.BOLD)}")
    if pm_results["success"]:
        ok(f"Date: {pm_results['date']}")
        ok(f"Races: {pm_results['races_created'] + pm_results['races_updated']}")
        ok(f"Runs: {pm_results['runs_created'] + pm_results['runs_updated']}")
    else:
        fail("PM job failed")
        for e in pm_results["errors"]:
            print(f"    • {e}")

    print(f"\n  {c('Database:', Colors.BOLD)}")
    if db_ok:
        ok("All verification checks passed")
    else:
        fail("Some verification checks failed")

    print(f"\n{c('═' * 60, Colors.CYAN)}\n")

    # Exit code
    all_ok = am_results["success"] and pm_results["success"] and db_ok
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
