#!/usr/bin/env python3
"""
Test script for Racing Post API endpoints.

Usage:
    python test_api.py                    # Test all endpoints
    python test_api.py --am               # Test AM job (racecards)
    python test_api.py --pm               # Test PM job (results)
    python test_api.py --skip-scrape      # Skip scraping, just test GETs
    python test_api.py --api-url http://localhost:8000/api/racing-post
"""
import argparse
import json
import sys
from datetime import date, timedelta

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)


def log(msg, level="INFO"):
    symbols = {"INFO": "[*]", "OK": "[+]", "FAIL": "[-]", "WARN": "[!]"}
    print(f"{symbols.get(level, '[*]')} {msg}")


def test_endpoint(name, method, url, json_data=None, expect_key=None):
    """Test an endpoint and return success status."""
    try:
        if method == "GET":
            r = requests.get(url, timeout=30)
        else:
            r = requests.post(url, json=json_data, timeout=300)

        if r.status_code == 200:
            data = r.json()
            if expect_key and expect_key in data:
                log(f"{name}: OK (status=200, {expect_key}={data[expect_key]})", "OK")
            else:
                log(f"{name}: OK (status=200)", "OK")
            return True, data
        else:
            log(f"{name}: FAILED (status={r.status_code})", "FAIL")
            try:
                log(f"   Response: {r.json()}", "FAIL")
            except:
                log(f"   Response: {r.text[:200]}", "FAIL")
            return False, None
    except requests.exceptions.ConnectionError:
        log(f"{name}: FAILED (connection refused)", "FAIL")
        return False, None
    except Exception as e:
        log(f"{name}: FAILED ({e})", "FAIL")
        return False, None


def test_am_job(api_url):
    """Test AM job: Scrape racecards + sync to DB."""
    print("=" * 60)
    print("AM JOB TEST: Scrape Racecards + Sync")
    print("=" * 60)
    print(f"API URL: {api_url}")
    print(f"Date: {date.today()}")
    print("=" * 60)

    # Step 1: Scrape racecards
    print("\n[STEP 1] Scrape racecards from Racing Post")
    print("-" * 40)
    ok, scrape_data = test_endpoint(
        "Scrape racecards",
        "POST",
        f"{api_url}/scrape-racecards/",
        json_data={"day": 1, "region": "gb", "fetch_stats": True, "fetch_profiles": True},
        expect_key="races"
    )

    if not ok:
        log("AM JOB FAILED at scrape step", "FAIL")
        return False

    races = scrape_data.get("races", 0)
    if races == 0:
        log("No races found today - this may be expected", "WARN")
        return True

    # Step 2: Sync to database
    print("\n[STEP 2] Sync to database")
    print("-" * 40)
    ok, sync_data = test_endpoint(
        "Sync racecards",
        "POST",
        f"{api_url}/sync-racecards/",
        json_data={
            "data": scrape_data.get("data", {}),
            "scrape_date": str(date.today())
        },
        expect_key="entries_created"
    )

    if not ok:
        log("AM JOB FAILED at sync step", "FAIL")
        return False

    # Summary
    print("\n[RESULT]")
    print("-" * 40)
    log(f"Races scraped: {races}")
    log(f"Entries created: {sync_data.get('entries_created', 0)}")
    log(f"Entries updated: {sync_data.get('entries_updated', 0)}")
    log(f"Horse stats: {sync_data.get('stats_created', 0)}")
    log(f"Jockey stats: {sync_data.get('jockey_stats_created', 0)}")
    log(f"Trainer stats: {sync_data.get('trainer_stats_created', 0)}")
    log(f"Trainer history: {sync_data.get('trainer_history_created', 0)}")
    log(f"Owner history: {sync_data.get('owner_history_created', 0)}")
    log(f"Medical records: {sync_data.get('medical_created', 0)}")

    errors = sync_data.get("errors", [])
    if errors:
        log(f"Errors: {len(errors)}", "WARN")
        for e in errors[:3]:
            log(f"  - {e}", "WARN")

    print("\n" + "=" * 60)
    log("AM JOB COMPLETE", "OK")
    print("=" * 60)
    return True


def test_pm_job(api_url, target_date=None):
    """Test PM job: Scrape results."""
    if target_date is None:
        target_date = (date.today() - timedelta(days=1)).strftime("%Y/%m/%d")

    print("=" * 60)
    print("PM JOB TEST: Scrape Results")
    print("=" * 60)
    print(f"API URL: {api_url}")
    print(f"Target date: {target_date}")
    print("=" * 60)

    # Scrape results
    print("\n[STEP 1] Scrape results from Racing Post")
    print("-" * 40)
    ok, result_data = test_endpoint(
        f"Scrape results ({target_date})",
        "POST",
        f"{api_url}/scrape/",
        json_data={"date": target_date, "region": "gb", "race_type": "all", "betfair": True},
        expect_key="races_created"
    )

    if not ok:
        log("PM JOB FAILED", "FAIL")
        return False

    # Summary
    print("\n[RESULT]")
    print("-" * 40)
    log(f"Races created: {result_data.get('races_created', 0)}")
    log(f"Races updated: {result_data.get('races_updated', 0)}")
    log(f"Runs created: {result_data.get('runs_created', 0)}")
    log(f"Runs updated: {result_data.get('runs_updated', 0)}")

    errors = result_data.get("errors", [])
    if errors:
        log(f"Errors: {len(errors)}", "WARN")
        for e in errors[:3]:
            log(f"  - {e}", "WARN")

    print("\n" + "=" * 60)
    log("PM JOB COMPLETE", "OK")
    print("=" * 60)
    return True


def main():
    parser = argparse.ArgumentParser(description="Test Racing Post API")
    parser.add_argument("--api-url", default="http://localhost:8000/api/racing-post",
                        help="API base URL")
    parser.add_argument("--am", action="store_true",
                        help="Test AM job only (scrape racecards + sync)")
    parser.add_argument("--pm", action="store_true",
                        help="Test PM job only (scrape results)")
    parser.add_argument("--date", help="Date for PM job (YYYY/MM/DD), default: yesterday")
    parser.add_argument("--skip-scrape", action="store_true",
                        help="Skip scraping tests (just test GET endpoints)")
    args = parser.parse_args()

    API = args.api_url.rstrip("/")

    # Run specific job tests if requested
    if args.am:
        success = test_am_job(API)
        sys.exit(0 if success else 1)

    if args.pm:
        success = test_pm_job(API, args.date)
        sys.exit(0 if success else 1)

    print("=" * 60)
    print("RACING POST API TEST")
    print("=" * 60)
    print(f"API URL: {API}")
    print(f"Date: {date.today()}")
    print("=" * 60)

    results = {"passed": 0, "failed": 0}

    # Test 1: Health check
    print("\n[1] HEALTH CHECK")
    print("-" * 40)
    ok, _ = test_endpoint("Health", "GET", f"{API.replace('/racing-post', '')}/health/")
    results["passed" if ok else "failed"] += 1

    if not args.skip_scrape:
        # Test 2: Scrape racecards
        print("\n[2] SCRAPE RACECARDS")
        print("-" * 40)
        ok, scrape_data = test_endpoint(
            "Scrape racecards",
            "POST",
            f"{API}/scrape-racecards/",
            json_data={"day": 1, "region": "gb", "fetch_stats": True, "fetch_profiles": True},
            expect_key="races"
        )
        results["passed" if ok else "failed"] += 1

        # Test 3: Sync racecards
        if ok and scrape_data and scrape_data.get("races", 0) > 0:
            print("\n[3] SYNC RACECARDS")
            print("-" * 40)
            ok, sync_data = test_endpoint(
                "Sync racecards",
                "POST",
                f"{API}/sync-racecards/",
                json_data={
                    "data": scrape_data.get("data", {}),
                    "scrape_date": str(date.today())
                },
                expect_key="entries_created"
            )
            results["passed" if ok else "failed"] += 1

            if ok and sync_data:
                log(f"   Entries: {sync_data.get('entries_created', 0)} created, {sync_data.get('entries_updated', 0)} updated")
                log(f"   Stats: {sync_data.get('stats_created', 0)} created")
                log(f"   Jockey stats: {sync_data.get('jockey_stats_created', 0)}")
                log(f"   Trainer stats: {sync_data.get('trainer_stats_created', 0)}")
        else:
            print("\n[3] SYNC RACECARDS")
            print("-" * 40)
            log("Skipped (no races to sync)", "WARN")

        # Test 4: Scrape results (yesterday)
        print("\n[4] SCRAPE RESULTS")
        print("-" * 40)
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y/%m/%d")
        ok, _ = test_endpoint(
            f"Scrape results ({yesterday})",
            "POST",
            f"{API}/scrape/",
            json_data={"date": yesterday, "region": "gb", "race_type": "all", "betfair": True},
            expect_key="races_created"
        )
        results["passed" if ok else "failed"] += 1

    # Test 5: GET endpoints
    print("\n[5] GET ENDPOINTS")
    print("-" * 40)

    endpoints = [
        ("Racecard entries", "/racecard-entries/", "count"),
        ("Horse race stats", "/horse-race-stats/", "count"),
        ("Jockey stats", "/jockey-stats/", "count"),
        ("Trainer stats", "/trainer-stats/", "count"),
        ("Trainer history", "/trainer-history/", "count"),
        ("Owner history", "/owner-history/", "count"),
        ("Medical records", "/medical/", "count"),
        ("Races", "/races/", "count"),
        ("Runs", "/runs/", "count"),
        ("Horses", "/horses/", "count"),
        ("Jockeys", "/jockeys/", "count"),
        ("Trainers", "/trainers/", "count"),
    ]

    for name, endpoint, key in endpoints:
        ok, _ = test_endpoint(name, "GET", f"{API}{endpoint}?page_size=1", expect_key=key)
        results["passed" if ok else "failed"] += 1

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total = results["passed"] + results["failed"]
    print(f"Passed: {results['passed']}/{total}")
    print(f"Failed: {results['failed']}/{total}")

    if results["failed"] == 0:
        print("\n[+] ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n[-] SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
