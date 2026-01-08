#!/usr/bin/env python3
"""
Test script for Racing Post API endpoints.

Usage:
    python test_api.py
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


def main():
    parser = argparse.ArgumentParser(description="Test Racing Post API")
    parser.add_argument("--api-url", default="http://localhost:8000/api/racing-post",
                        help="API base URL")
    parser.add_argument("--skip-scrape", action="store_true",
                        help="Skip scraping tests (just test GET endpoints)")
    args = parser.parse_args()

    API = args.api_url.rstrip("/")

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
