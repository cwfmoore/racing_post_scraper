# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ PUBLIC REPOSITORY WARNING

**This is a PUBLIC GitHub repo.** Never commit:
- API keys, tokens, passwords
- Internal IP addresses (e.g., 192.168.x.x)
- Email addresses
- Database connection strings
- Any credentials or secrets

All sensitive data must go in `.env` (gitignored).

### Before Every Commit

⚠️ **ALWAYS scan for sensitive data before committing:**

```bash
# Search for potential secrets
git diff --cached | grep -iE "(password|secret|token|api.?key|192\.168\.|@.*\.(com|net|org))"
```

| Pattern | Example | Risk |
|---------|---------|------|
| `192.168.x.x` | `192.168.1.145` | Internal network exposure |
| `password=` | `DB_PASSWORD="abc123"` | Credential leak |
| `@*.com` | `user@email.com` | PII exposure |
| `sk-`, `pk_` | API key prefixes | Service compromise |

**If found:** Remove the sensitive data and use environment variables instead.

## Response Style

All responses must be ADHD-friendly:
- **Short and concise** - No walls of text
- **Visual** - Use tables, bullet points, code blocks
- **Emojis** - Use to highlight key points and improve scannability
- **Colors** - Use markdown formatting for emphasis

## ⚠️ No Assumptions Rule

**NEVER guess or assume.** If you have a hypothesis, test it first.

| ❌ Don't | ✅ Do |
|----------|-------|
| "The issue is probably X" | Query data to verify X |
| "This should work because..." | Test with actual code/data |
| Assume config values | Read the actual config files |
| Guess API responses | Make a test request |

**Before concluding a root cause:**
1. Form hypothesis
2. Find non-destructive way to test (read-only queries, curl, test scripts)
3. Verify with actual data
4. Only then state the conclusion

## ⚠️ SQL Safety Rules

**NEVER guess table names, column names, or SQL syntax.** This could cause data loss.

- Always query the database schema first before writing SQL
- Use `SELECT tablename FROM pg_tables WHERE schemaname = 'public'` to list tables
- Use `\d tablename` or query `information_schema.columns` for column names
- Ask the user to verify table names if uncertain

### Racing Post Tables (rp_*)

| Table | Description |
|-------|-------------|
| `rp_course` | Race courses/tracks |
| `rp_horse` | Horse records |
| `rp_jockey` | Jockey records |
| `rp_trainer` | Trainer records |
| `rp_owner` | Owner records |
| `rp_breeder` | Breeder records |
| `rp_race` | Race events |
| `rp_run` | Individual horse runs in races |
| `rp_racecard_entry` | Pre-race entries (point-in-time) |
| `rp_horse_race_stats` | C/D/G stats per horse per race |
| `rp_jockey_stats_daily` | Jockey P/L snapshots |
| `rp_trainer_stats_daily` | Trainer P/L snapshots |
| `rp_horse_trainer_history` | Trainer change history |
| `rp_horse_owner_history` | Owner change history |
| `rp_horse_medical` | Medical/wind surgery records |
| `rp_betfair_price` | BSP prices linked to runs |
| `rp_betfair_mapping` | Racing Post ↔ Betfair ID mappings |

## Documentation Formatting

When creating or editing markdown files (README.md, docs, etc.), follow the standards in:
📄 **[docs-formatting-instructions.md](docs-formatting-instructions.md)**

Key rules:
- H2 sections: emoji + title + `---` separator
- H3 sections: no emoji (clean hierarchy)
- Use tables for structured data
- Use `[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]` alerts
- Professional emoji usage only (see approved list in guide)

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

## Data Collection Strategy

### What Each Scraper Provides

| Scraper | Output | Data |
|---------|--------|------|
| `rpscrape.py` | CSV | Results, SP, BSP, finishing positions, connections |
| `racecards.py` | JSON | Pre-race entries, stats (C/D/G), jockey/trainer P/L, profiles |

### Time-Sensitive Data ⚠️

| Data | Backfillable? | Source |
|------|---------------|--------|
| Race results | ✅ Yes - anytime | rpscrape.py |
| BSP/Betfair prices | ✅ Yes - anytime | rpscrape.py |
| Jockey/Trainer P/L | ❌ **No** - day of race only | racecards.py |
| C/D/G stats | ❌ **No** - day of race only | racecards.py |
| Racecard entries | ❌ **No** - pre-race only | racecards.py |

**Critical:** Stats from racecards.py are point-in-time snapshots. Miss a day = data lost forever.

### Recommended Daily Schedule

| Time | Task | Command |
|------|------|---------|
| 🌅 Morning (before racing) | Scrape racecards + stats | `racecards.py --day 1 --region gb` |
| 🌙 Evening (after racing) | Scrape yesterday's results | `rpscrape.py -d YYYY/MM/DD -r gb` |

### Settings for Full Data Collection

```toml
# user_settings.toml
betfair_data = true    # Include BSP in historical CSV

# user_racecard_settings.toml
fetch_stats = true     # Jockey/trainer P/L, C/D/G
fetch_profiles = true  # Medical history, trainer changes
```

### Related Documentation

Full database schema (17 tables) documented in:
`C:\Users\Craig\OneDrive - West Lothian College\Obsidian\cmoore\Betfair Analysis Platform\2026-01-08 - Racing Post Database Schema.md`

## Linking to Betfair IDs

### The Problem

Racing Post uses `horse_id` and `race_id`. Betfair uses `selection_id` and `market_id`. To join datasets, you need a mapping.

### The Solution: Name Matching

```
Racing Post                           Betfair
───────────                           ───────
race_id: 909776        ──────────►    market_id: 1.234567890
horse_id: 1234567      ──────────►    selection_id: 12345678
horse_name: "Saint Patrick (IRE)"     runner_name: "St Patrick"
```

**Note:** `selection_id` changes every market - it's NOT a permanent ID. Must match per-race.

### Name Normalization

Before comparing names, normalize both sides:

| Step | Example |
|------|---------|
| Remove country code | `(IRE)`, `(FR)` → removed |
| Lowercase | `FRANKEL` → `frankel` |
| Accents → ASCII | `étoile` → `etoile` |
| Abbreviations | `Saint` → `st` |
| Remove punctuation | `King's` → `kings` |

### Matching Logic

```
1. Normalize Racing Post name
2. Normalize Betfair runner name
3. Compare:
   - Exact match? → 100% confidence
   - Fuzzy match ≥95%? → Accept with confidence score
   - Below 95%? → Flag for manual review
```

**Library:** `rapidfuzz` with `token_sort_ratio` (handles word order differences)

### Existing Implementation

Name matching logic already exists in the API codebase:
- **File:** `nas_api_003/oddschecker/services/runner_matching.py`
- **Function:** `normalize_name()`
- **Threshold:** 95% match confidence

### Database Table: `betfair_rp_mapping`

| Column | Type | Description |
|--------|------|-------------|
| `race_id` | INT | Racing Post race ID |
| `horse_id` | INT | Racing Post horse ID |
| `market_id` | VARCHAR | Betfair market ID |
| `selection_id` | BIGINT | Betfair selection ID |
| `match_confidence` | DECIMAL | 0.0 - 1.0 |
| `match_method` | VARCHAR | 'exact', 'fuzzy', 'manual' |
| `needs_review` | BOOLEAN | Flag low-confidence matches |

**Unique constraint:** `(race_id, horse_id)`

## Development & Production Workflow

### Two-Machine Setup

| Machine | OS | Purpose |
|---------|-----|---------|
| **Windows** | Windows | Development & testing |
| **Linux (NAS)** | Linux | Production (scheduled scraping) |

Both machines use the **same codebase** via git.

### Related Codebases

| Codebase | Location | Purpose |
|----------|----------|---------|
| racing_post_scraper | This repo | Scrapes Racing Post data |
| nas_api_003 | `C:\Users\Craig\Documents\Python\nas_api_003` | Django API + PostgreSQL database |

The scraper outputs CSV/JSON files. These feed into the API database via parsing scripts.

### Environment Files

| File | Purpose | In Git? |
|------|---------|---------|
| `.env` | Racing Post credentials | ❌ No (.gitignore) |

**Note:** Same `.env` structure on both machines (Racing Post login credentials).

### Deployment Workflow

```
WINDOWS (dev)                         LINUX (prod)
─────────────                         ────────────

1. Make code changes
2. Test scraper locally
3. git commit & push
                                      4. git pull
                                      5. Scheduler runs scraper
```

### Key Rules

| Rule | Reason |
|------|--------|
| Test scraper changes on dev first | Avoid breaking scheduled jobs |
| Keep `.env` synced manually | Same credentials both machines |
| Output files are gitignored | Only code in repo |
