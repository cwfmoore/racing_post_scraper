# Racing Post Scraper

> **Fork of [joenano/rpscrape](https://github.com/joenano/rpscrape)** with Docker support, API integration, and automated scheduling.

Scrapes historical horse racing data from Racing Post. This fork adds:
- Docker containerization
- API sync to PostgreSQL database
- Automated cron scheduling (GB + Ireland)
- Retry logic with exponential backoff
- Error logging with daily rotation

---

## Table of Contents

| Section | Description |
|---------|-------------|
| [Quick Start](#-quick-start) | Get running in 2 minutes |
| [Installation](#-installation) | Docker and manual setup |
| [Authentication](#-authentication) | Racing Post credentials |
| [Docker Usage](#-docker-usage) | Commands and environment |
| [Cron Jobs](#-cron-jobs) | Automated scheduling |
| [Retry Logic](#-retry-logic) | Built-in resilience |
| [Error Logging](#-error-logging) | Daily log files with retention |
| [Manual Scraper Usage](#-manual-scraper-usage) | CLI reference |
| [Regions](#-regions) | Supported regions |
| [Data Collected](#-data-collected) | Fields and outputs |
| [Settings](#%EF%B8%8F-settings) | Configuration options |
| [Project Structure](#%EF%B8%8F-project-structure) | File organization |
| [Testing](#-testing) | Test commands |
| [API Integration](#-api-integration) | Database sync |
| [Troubleshooting](#%EF%B8%8F-troubleshooting) | Common issues |
| [Credits](#-credits) | Attribution |
| [License](#-license) | MIT |

---

## Quick Start

```bash
# Docker (recommended)
docker compose run --rm scraper racecards    # Today's racecards
docker compose run --rm scraper results      # Yesterday's results

# Manual
python scripts/rpscrape.py -d 2026/01/10 -r gb
python scripts/racecards.py --day 1 --region gb
```

---

## Installation

### Docker (Recommended)

```bash
git clone https://github.com/cwfmoore/racing_post_scraper.git
cd racing_post_scraper
cp .env.example .env   # Edit with your credentials
docker compose build
```

### Manual

```bash
git clone https://github.com/cwfmoore/racing_post_scraper.git
cd racing_post_scraper
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

> [!IMPORTANT]
> Requires Python 3.13+

---

## Authentication

Create `.env` file with Racing Post credentials:

```env
EMAIL=your@email.com
AUTH_STATE=your_auth_state_cookie
ACCESS_TOKEN=your_cognito_access_token
```

> [!TIP]
> **Finding tokens:** Login to Racing Post > DevTools (F12) > Storage > Cookies
> - `auth_state` > Copy value
> - `CognitoIdentityServiceProvider...accessToken` > Copy value

---

## Docker Usage

### Commands

| Command | Description |
|---------|-------------|
| `scraper racecards` | Scrape today's racecards + stats |
| `scraper results` | Scrape yesterday's results |
| `scraper results 2026/01/05` | Scrape specific date |
| `scraper help` | Show help |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REGIONS` | `gb,ire` | Comma-separated region codes |
| `API_URL` | `http://host.docker.internal:8000/api/racing-post` | API endpoint |

```bash
# Single region only
REGIONS=gb docker compose run --rm scraper racecards
```

---

## Cron Jobs

```bash
# Recommended schedule (crontab -e)
0 6 * * *  cd /path/to/scraper && docker compose run --rm scraper racecards >> logs/cron.log 2>&1
15 6 * * * cd /path/to/scraper && docker compose run --rm scraper results >> logs/cron.log 2>&1
```

| Time | Job | What it does |
|------|-----|--------------|
| 06:00 | `racecards` | Today's entries, jockey/trainer stats, pedigree |
| 06:15 | `results` | Yesterday's finishing positions, SP, BSP |

> [!NOTE]
> Both run in morning - results scraped for **yesterday** when all races complete.

---

## Retry Logic

Built-in resilience for network failures:

| Setting | Value |
|---------|-------|
| Max retry time | 23 hours |
| Initial backoff | 1 minute |
| Max backoff | 30 minutes |
| Pattern | 1m > 2m > 4m > 8m > 16m > 30m > 30m... |

> [!IMPORTANT]
> Each region processed independently. If GB fails, IRE still runs.

---

## Error Logging

Standardized logging system with daily file rotation:

### Log Levels

| Level | Console | File | Use Case |
|-------|---------|------|----------|
| `INFO` | Yes | No | Normal operations |
| `WARNING` | Yes | Yes | Unexpected but handled |
| `ERROR` | Yes | Yes | Operation failures |

### Log Format

```
LEVEL    [YYYY-MM-DD HH:MM:SS] module: message
```

Example:
```
INFO     [2026-01-11 14:32:14] rpscrape: Scraping races
WARNING  [2026-01-11 14:32:15] network: 406 error (attempt 2/7): https://...
ERROR    [2026-01-11 14:32:16] profiles: Failed to get profiles
```

### File Location

| Environment | Path |
|-------------|------|
| Docker | `./error_logs/` (mounted volume) |
| Manual | `error_logs/` in project root |

Files named `YYYY-MM-DD_error_log.txt` with 90-day automatic retention.

### Searching Logs

```bash
# Today's errors
cat error_logs/$(date +%Y-%m-%d)_error_log.txt

# Search all logs
grep -r "406" error_logs/

# Count errors per day
wc -l error_logs/*_error_log.txt
```

---

## Manual Scraper Usage

### Results (rpscrape.py)

```bash
# Single date
python scripts/rpscrape.py -d 2026/01/10

# Date range
python scripts/rpscrape.py -d 2026/01/01-2026/01/10

# Region filter
python scripts/rpscrape.py -d 2026/01/10 -r gb

# Full year (requires -t type)
python scripts/rpscrape.py -r ire -y 2025 -t flat

# Course + year range
python scripts/rpscrape.py -c 2 -y 2020-2025 -t jumps

# From date file
python scripts/rpscrape.py --date-file dates.txt
```

### Racecards (racecards.py)

```bash
python scripts/racecards.py --day 1              # Today
python scripts/racecards.py --day 2              # Tomorrow
python scripts/racecards.py --days 2 --region gb # Both days, GB only
```

### Search Courses/Regions

```bash
python scripts/rpscrape.py --regions             # List all regions
python scripts/rpscrape.py --regions gb          # Search regions
python scripts/rpscrape.py --courses             # List all courses
python scripts/rpscrape.py --courses ascot       # Search courses
python scripts/rpscrape.py --courses gb          # Courses in region
```

---

## Regions

| Code | Region |
|------|--------|
| `gb` | Great Britain |
| `ire` | Ireland |
| `fr` | France |
| `usa` | United States |
| `aus` | Australia |

> [!NOTE]
> Docker default: `gb,ire`. Other regions available for manual scraping.

---

## Data Collected

### Racecards

| Field | Description |
|-------|-------------|
| Entries | Horse, jockey, trainer, owner, draw |
| Pedigree | Sire, dam, damsire (with IDs) |
| Stats | C/D/G win rates, jockey/trainer P/L |
| Medical | Wind operations, procedures |
| Form | Recent form figures |

### Results

| Field | Description |
|-------|-------------|
| Position | Finishing position, beaten lengths |
| Odds | SP (decimal), BSP |
| Time | Race time in seconds |
| Ratings | RPR, TS, Official Rating |
| Prize | Prize money won |

---

## Settings

### Results Settings

Copy and edit:
```bash
cp settings/default_settings.toml settings/user_settings.toml
```

Key options:
```toml
betfair_data = true   # Include BSP prices
gzip_output = false   # Compress output files

[fields.runner_info]
sire_id = true        # Include pedigree IDs
dam_id = true
damsire_id = true
```

### Racecard Settings

Copy and edit:
```bash
cp settings/default_racecard_settings.toml settings/user_racecard_settings.toml
```

Key options:
```toml
[data_collection]
fetch_stats = true     # Jockey/trainer P/L
fetch_profiles = true  # Medical, trainer changes

[field_groups]
breeding = true        # Sire, dam, damsire
```

---

## Project Structure

```
racing_post_scraper/
├── docker-compose.yml       # Container config
├── docker-entrypoint.sh     # Job runner + retry logic
├── Dockerfile
├── .env                     # Credentials (git-ignored)
│
├── scripts/
│   ├── rpscrape.py          # Results scraper
│   ├── racecards.py         # Racecard scraper
│   ├── logging_config.py    # Logging setup
│   ├── models/              # Data models
│   └── utils/               # Network, parsing, logging handlers
│
├── settings/
│   ├── default_settings.toml
│   ├── user_settings.toml   # Your overrides
│   └── *_racecard_settings.toml
│
├── tests/
│   ├── test_api_jobs.py             # Test scrape + sync
│   └── test_database_integrity.py   # Verify DB data
│
├── data/                    # CSV output (manual scraper)
├── racecards/               # JSON output (racecard scraper)
├── error_logs/              # Error log files (WARNING+)
└── logs/                    # Cron logs
```

---

## Testing

### Test Full Pipeline

```bash
python tests/test_api_jobs.py
```

Runs racecards + results jobs, verifies:
- API connectivity
- Data synced
- Pedigree saved
- No duplicates

### Test Database Only

```bash
python tests/test_database_integrity.py
```

---

## API Integration

Syncs to [nas_api_003](https://github.com/cwfmoore/nas_api_003) Django API.

| Endpoint | Purpose |
|----------|---------|
| `POST /scrape-racecards/` | Scrape racecards |
| `POST /sync-racecards/` | Save to database |
| `POST /scrape/` | Scrape + save results |

---

## Troubleshooting

### 403 Forbidden

**Cause:** Expired tokens

**Fix:** Update `AUTH_STATE` and `ACCESS_TOKEN` in `.env`

---

### No races found

**Cause:** No racing scheduled

**Fix:** Normal on non-race days. Check Racing Post calendar.

---

### API connection failed

**Fix:** Check API is running:
```bash
curl http://localhost:8000/api/racing-post/courses/
```

---

### Jumps year confusion

> [!WARNING]
> For jumps racing, the year refers to **season start**.
>
> Example: 2025 Cheltenham Festival > Use `-y 2024` (2024-25 season)

---

### Persistent 406 errors

**Cause:** Racing Post rate limiting or blocking

**Fix:** The scraper automatically retries with exponential backoff. Check `error_logs/` for details:
```bash
grep "406" error_logs/*.txt
```

---

## Credits

This project is a fork of [joenano/rpscrape](https://github.com/joenano/rpscrape).

Original tool provides the core scraping functionality. This fork adds containerization, API integration, error logging, and production scheduling features.

---

## License

MIT
