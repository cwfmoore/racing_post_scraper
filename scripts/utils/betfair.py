import csv
import logging
import time
from random import choice

import curl_cffi.requests

from pathlib import Path
from datetime import date, timedelta, datetime

from models.betfair import BSP, BSPMap

logger = logging.getLogger(__name__)

# Browser impersonation options (same as network.py)
BROWSERS = [
    'chrome110', 'chrome116', 'chrome119', 'chrome120',
    'edge99', 'edge101',
]


class Betfair:
    def __init__(self, race_urls: list[str]):
        self.urls: list[tuple[str, str]] = create_urls(race_urls)
        self.data: BSPMap = {}
        self.rows: list[BSP] = []

        files_found = 0
        files_missing = 0

        for url, region in self.urls:
            rows = get_data(url, region)

            if not rows:
                files_missing += 1
                continue

            files_found += 1
            self.rows.extend(rows)

            for row in rows:
                key = (row.region, row.date, row.off)
                self.data.setdefault(key, []).append(row)

        logger.info(f"BSP fetch complete: {files_found} files found, {files_missing} not available, {len(self.rows)} total rows")

    @classmethod
    def from_csv(cls, path: Path) -> 'Betfair':
        self = cls.__new__(cls)

        self.urls = []
        self.data = {}
        self.rows = []

        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for record in reader:
                bsp = BSP.from_csv(record)
                if not bsp:
                    continue

                self.rows.append(bsp)

                key = (bsp.region, bsp.date, bsp.off)
                self.data.setdefault(key, []).append(bsp)

        return self


def create_date_range(date_start: str, date_end: str) -> list[date]:
    start = datetime.strptime(date_start, '%Y-%m-%d').date() - timedelta(days=1)
    end = datetime.strptime(date_end, '%Y-%m-%d').date() + timedelta(days=1)

    dates: list[date] = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)

    return dates


def create_urls(race_urls: list[str]) -> list[tuple[str, str]]:
    url_base = 'https://promo.betfair.com/betfairsp/prices/dwbfprices'
    regions = ['uk', 'ire', 'usa', 'aus', 'fr', 'uae']

    dates = {x.split('/')[6] for x in race_urls}
    date_start, date_end = min(dates), max(dates)
    dates = create_date_range(date_start, date_end)

    urls: list[tuple[str, str]] = []

    for d in dates:
        formatted = d.strftime('%d%m%Y')
        for region in regions:
            urls.append((f'{url_base}{region}win{formatted}.csv', region.upper()))

    return urls


def get_data(url: str, region: str) -> list[BSP] | None:
    browser = choice(BROWSERS)
    resp = curl_cffi.requests.get(url, impersonate=browser)

    for _ in range(4):
        if resp.status_code == 404:
            # Extract filename for cleaner logging
            filename = url.split('/')[-1]
            logger.warning(f"BSP file not available (404): {filename}")
            return None
        if resp.status_code == 429:
            time.sleep(10)
            resp = curl_cffi.requests.get(url, impersonate=browser)
            continue
        if resp.status_code == 520:
            time.sleep(10)
            resp = curl_cffi.requests.get(url, impersonate=browser)
            continue
        if resp.status_code == 403:
            # Cloudflare block - try different browser
            time.sleep(2)
            browser = choice(BROWSERS)
            resp = curl_cffi.requests.get(url, impersonate=browser)
            continue
        if resp.status_code == 200:
            break
        raise RuntimeError(f'HTTP error {resp.status_code} for URL {url}')

    if resp.status_code != 200:
        raise RuntimeError(f'HTTP error {resp.status_code} for URL {url}')

    reader = csv.DictReader(resp.content.decode().splitlines())
    rows: list[BSP] = []

    for record in reader:
        bsp = BSP.from_record(record, region)
        if bsp:
            rows.append(bsp)

    if rows:
        filename = url.split('/')[-1]
        logger.debug(f"BSP file loaded: {filename} ({len(rows)} rows)")

    return rows
