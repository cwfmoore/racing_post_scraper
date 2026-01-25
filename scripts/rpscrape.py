#!/usr/bin/env python3

import gzip
import os
import sys

from collections.abc import Callable
from datetime import date
from dotenv import load_dotenv
from lxml import html
from orjson import loads
from pathlib import Path
from typing import TextIO, TYPE_CHECKING

from logging_config import setup_logging, get_logger
from utils.argparser import ArgParser
from utils.betfair import Betfair
from utils.betfair_matching import match_races_to_betfair
from utils.exceptions import RaceFetchError, NetworkError
from utils.network import NetworkClient
from utils.paths import Paths, build_paths
from utils.settings import Settings
from utils.update import Update

logger = get_logger(__name__)

_ = load_dotenv()

settings = Settings()

if TYPE_CHECKING:
    from utils.betfair import Betfair

RACE_TYPES: dict[str, set[str]] = {
    'flat': {'Flat'},
    'jumps': {'Chase', 'Hurdle', 'NH Flat'},
}


def check_for_update() -> bool:
    update = Update()

    try:
        if not update.available():
            return False
    except Exception as e:
        logger.warning(f"Update check failed: {e}")
        return False

    try:
        choice = input('Update available. Do you want to update? [y/N] ').strip().lower()
    except EOFError:
        return False

    if choice != 'y':
        return False

    success = update.pull_latest()
    print('Updated successfully.' if success else 'Failed to update.')
    return success


def sort_key(url: str) -> tuple[str, str]:
    parts = url.split('/')
    race_course = parts[5]
    race_date = parts[6]
    return race_date, race_course


def get_race_urls(
    years: list[str], tracks: list[tuple[str, str]], race_type: str, client: NetworkClient
) -> list[str]:
    url_course_base = 'https://www.racingpost.com:443/profile/course/filter/results'
    url_result_base = 'https://www.racingpost.com/results'

    urls: set[str] = set()

    for course_id, course in tracks:
        for year in years:
            race_list_url = f'{url_course_base}/{course_id}/{year}/{race_type}/all-races'

            status, response = client.get(race_list_url)

            if status != 200:
                logger.error(f'Failed to get race urls. Status: {status}, URL: {race_list_url}')
                sys.exit(1)

            data = loads(response.text).get('data', {})
            races = data.get('principleRaceResults', [])

            if not races:
                continue

            for race in races:
                race_date = race['raceDatetime'][:10]
                race_id = race['raceInstanceUid']
                race_url = f'{url_result_base}/{course_id}/{course}/{race_date}/{race_id}'
                urls.add(race_url.replace(' ', '-').replace("'", ''))

    return sorted(urls, key=sort_key)


def get_race_urls_date(
    dates: list[date], tracks: list[tuple[str, str]], client: NetworkClient
) -> list[str]:
    urls: set[str] = set()
    course_ids: set[str] = {t[0] for t in tracks}

    for race_date in dates:
        url = f'https://www.racingpost.com/results/{race_date}'

        status, response = client.get(url)

        if status != 200:
            logger.warning(f'Failed to get race URLs for {race_date}: status {status}')
            continue

        doc = html.fromstring(response.content)

        races = doc.xpath('//a[@data-test-selector="link-listCourseNameLink"]')
        for race in races:
            course_id = race.attrib['href'].split('/')[2]
            if course_id in course_ids:
                urls.add(f'https://www.racingpost.com{race.attrib["href"]}')

    return sorted(urls, key=sort_key)


def load_or_save_urls(path: Path, builder: Callable[[], list[str]]) -> list[str]:
    if path.exists():
        return [line.strip() for line in path.read_text().splitlines() if line.strip()]

    urls = builder()
    _ = path.write_text('\n'.join(urls))

    return urls


def prepare_betfair(
    race_urls: list[str],
    paths: Paths,
) -> 'Betfair | None':
    if not settings.toml or not settings.toml.get('betfair_data', False):
        return None

    paths.betfair.parent.mkdir(parents=True, exist_ok=True)

    from utils.betfair import Betfair

    logger.info('Getting Betfair data...')

    if paths.betfair.exists():
        logger.info('Using cached Betfair data')
        return Betfair.from_csv(paths.betfair)

    betfair = Betfair(race_urls)

    with open(str(paths.betfair), 'w') as f:
        fields = settings.toml.get('fields', {}).get('betfair', {})
        header = ','.join(['date', 'region', 'off', 'horse'] + list(fields.keys()))
        _ = f.write(header + '\n')

        for row in betfair.rows:
            values = ['' if v is None else str(v) for v in row.to_dict().values()]
            _ = f.write(','.join(values) + '\n')

    return betfair


def scrape_races(
    race_urls: list[str],
    paths: Paths,
    race_type: str,
    client: NetworkClient,
    file_writer: Callable[[str, bool], TextIO],
) -> list[dict]:
    """Scrape races and return list of race info dicts for Betfair matching."""
    from utils.race import Race, VoidRaceError

    scraped_races: list[dict] = []

    betfair = prepare_betfair(
        race_urls=race_urls,
        paths=paths,
    )

    last_url = paths.progress.read_text().strip() if paths.progress.exists() else None

    if last_url:
        try:
            race_urls = race_urls[race_urls.index(last_url) + 1 :]
            logger.info(f'Resuming after {last_url}')
        except ValueError:
            logger.warning(f'Progress URL not found in race list: {last_url}')
    else:
        logger.info('Scraping races')

    append = last_url is not None and paths.output.exists()

    with file_writer(str(paths.output), append=append) as f:
        if not append:
            _ = f.write(settings.csv_header + '\n')

        for url in race_urls:
            status, response = client.get(url)

            if status != 200:
                logger.warning(f'Failed to fetch race {url}: status {status}')
                continue

            doc = html.fromstring(response.content)

            try:
                race = (
                    Race(client, url, doc, race_type, settings.fields, betfair.data)
                    if betfair
                    else Race(client, url, doc, race_type, settings.fields)
                )
            except VoidRaceError:
                continue
            except RaceFetchError as e:
                logger.warning(f'Skipping race due to fetch error: {e}')
                continue
            except NetworkError as e:
                logger.warning(f'Skipping race due to network error: {e}')
                continue

            allowed = RACE_TYPES.get(race_type)
            if allowed is not None and race.race_info.race_type not in allowed:
                continue

            for row in race.csv_data:
                _ = f.write(row + '\n')

            _ = paths.progress.write_text(url)

            # Collect race info for Betfair matching
            scraped_races.append({
                'race_id': race.race_info.race_id,
                'date': str(race.race_info.date),
                'course': race.race_info.course,
                'off_time': race.race_info.off_time,
            })

    logger.info('Finished scraping.')
    logger.info(f'OUTPUT_CSV={paths.output.resolve()}')

    return scraped_races


def writer_csv(file_path: str, append: bool = False) -> TextIO:
    return open(file_path, 'a' if append else 'w', encoding='utf-8')


def writer_gzip(file_path: str, append: bool = False) -> TextIO:
    mode = 'at' if append else 'wt'
    return gzip.open(file_path, mode, encoding='utf-8')


def main():
    setup_logging()

    if settings.toml is None:
        logger.error('Failed to load settings')
        sys.exit(1)

    if settings.toml['auto_update']:
        _ = check_for_update()

    gzip_output = settings.toml.get('gzip_output', False)
    file_writer = writer_gzip if gzip_output else writer_csv

    parser = ArgParser()

    if len(sys.argv) <= 1:
        parser.parser.print_help()
        sys.exit(2)

    args = parser.parse(sys.argv[1:])
    paths = build_paths(args.request, gzip_output)

    client = NetworkClient(
        email=os.getenv('EMAIL'),
        auth_state=os.getenv('AUTH_STATE'),
        access_token=os.getenv('ACCESS_TOKEN'),
    )

    if args.dates != []:
        race_urls = load_or_save_urls(
            paths.urls,
            lambda: get_race_urls_date(args.dates, args.tracks, client),
        )

    else:
        race_urls = load_or_save_urls(
            paths.urls,
            lambda: get_race_urls(args.years, args.tracks, args.race_type, client),
        )

    scraped_races = scrape_races(race_urls, paths, args.race_type, client, file_writer)

    # Match to Betfair markets if we have race data
    if scraped_races and settings.toml.get('betfair_matching', True):
        # Extract unique dates from scraped races
        dates = set()
        for race in scraped_races:
            if race.get('date'):
                dates.add(race['date'])

        for race_date in sorted(dates):
            logger.info(f'Matching {race_date} results to Betfair markets...')
            try:
                result = match_races_to_betfair(
                    [r for r in scraped_races if r.get('date') == race_date],
                    race_date,
                )
                logger.info(
                    f'Betfair matching: {result["races_matched"]}/{result["total_races"]} races, '
                    f'{result["runners_matched"]} runners matched'
                )
            except Exception as e:
                logger.warning(f'Betfair matching failed for {race_date}: {e}')


if __name__ == '__main__':
    main()
