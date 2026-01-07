# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Response Style

All responses must be ADHD-friendly:
- **Short and concise** - No walls of text
- **Visual** - Use tables, bullet points, code blocks
- **Emojis** - Use to highlight key points and improve scannability
- **Colors** - Use markdown formatting for emphasis

## Project Overview

rpscrape is a Python web scraper that gathers historical horse racing data from Racing Post. It requires Python 3.13+ and uses browser impersonation via curl_cffi to access the site.

## Environment

A virtual environment exists in the codebase and must be used:
```bash
# Activate venv (Windows)
.venv\Scripts\activate

# Activate venv (Linux/Mac)
source .venv/bin/activate
```

## Commands

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run historical race scraper
```bash
# Single date
python scripts/rpscrape.py -d 2020/10/01

# Date range with region filter
python scripts/rpscrape.py -d 2019/12/15-2019/12/18 -r gb

# Full year by region and type (type required for year mode)
python scripts/rpscrape.py -r ire -y 2019 -t flat

# By course code with year range
python scripts/rpscrape.py -c 2 -y 1999-2018 -t jumps

# From date file
python scripts/rpscrape.py --date-file dates.txt
```

### Run racecard scraper
```bash
python scripts/racecards.py --day 1           # Today
python scripts/racecards.py --day 2           # Tomorrow
python scripts/racecards.py --days 2 --region gb  # Both days, GB only
```

### Search courses and regions
```bash
python scripts/rpscrape.py --regions          # List all regions
python scripts/rpscrape.py --courses ascot    # Search courses
python scripts/rpscrape.py --courses gb       # List courses in region
```

## Architecture

### Entry Points
- `scripts/rpscrape.py` - Historical race data scraper (main tool)
- `scripts/racecards.py` - Upcoming race card scraper

### Data Models (`scripts/models/`)
- `race.py` - `RaceInfo` and `RunnerInfo` dataclasses for historical data
- `racecard.py` - `Racecard` and `Runner` dataclasses for upcoming races
- `betfair.py` - `BSP` dataclass for Betfair odds data

### Utilities (`scripts/utils/`)
- `network.py` - `NetworkClient` handles HTTP with curl_cffi browser impersonation and retry logic
- `race.py` - Core `Race` class that extracts historical race data from HTML (684 lines, most complex)
- `argparser.py` - CLI argument parsing and validation
- `settings.py` - TOML settings loader with user override support
- `paths.py` - Output directory structure management

### Configuration
- `settings/default_settings.toml` - Default field toggles for historical scraper
- `settings/default_racecard_settings.toml` - Default field toggles for racecards
- Copy to `user_settings.toml` / `user_racecard_settings.toml` to customize without git tracking

### Data Files (`courses/`)
- `_courses` - JSON lookup: course ID → name
- `_regions` - JSON lookup: region code → name

## Authentication

Requires `.env` file in root with Racing Post credentials:
```
EMAIL=your@email.com
AUTH_STATE=your_auth_state_cookie
ACCESS_TOKEN=your_cognito_access_token
```

Get tokens from browser dev tools → Storage → Cookies after logging into Racing Post. The access token is from the `CognitoIdentityServiceProvider...accessToken` cookie.

## Output

- Historical data: `data/{region|course}/{type}/{filename}.csv[.gz]`
- Racecards: `racecards/*.json`
- Cache: `.cache/urls/`, `.cache/betfair/`

## Key Technical Notes

- When scraping jumps data by year, the year refers to season start (2019 Cheltenham = use 2018)
- `-d` (date) and `-y` (year) are mutually exclusive
- `-r` (region) and `-c` (course) are mutually exclusive
- Year mode requires `-t flat|jumps`
- NetworkClient randomizes browser types and has built-in retry with exponential backoff for 406 errors
