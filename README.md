# 🏇 Racing Post Scraper

Automated scraper for Racing Post horse racing data. Collects racecards (pre-race) and results (post-race) for GB and Ireland.

---

## ⚡ Quick Start

```bash
# Docker (recommended)
docker compose run --rm scraper racecards    # Today's racecards
docker compose run --rm scraper results      # Yesterday's results

# Manual
python scripts/rpscrape.py -d 2026/01/10 -r gb
python scripts/racecards.py --day 1 --region gb
```

---

## 📦 Installation

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

## 🔐 Authentication

Create `.env` file with Racing Post credentials:

```env
EMAIL=your@email.com
AUTH_STATE=your_auth_state_cookie
ACCESS_TOKEN=your_cognito_access_token
```

> [!TIP]
> **Finding tokens:** Login to Racing Post → DevTools (F12) → Storage → Cookies
> - `auth_state` → Copy value
> - `CognitoIdentityServiceProvider...accessToken` → Copy value

---

## 🐳 Docker Usage

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

## ⏰ Cron Jobs

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

## 🔄 Retry Logic

Built-in resilience for network failures:

| Setting | Value |
|---------|-------|
| Max retry time | 23 hours |
| Initial backoff | 1 minute |
| Max backoff | 30 minutes |
| Pattern | 1m → 2m → 4m → 8m → 16m → 30m → 30m... |

> [!IMPORTANT]
> Each region processed independently. If GB fails, IRE still runs.

---

## 📜 Manual Scraper Usage

### Results (`rpscrape.py`)

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

### Racecards (`racecards.py`)

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

## 🌍 Regions

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

## 📊 Data Collected

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

## ⚙️ Settings

### Results Settings

Copy and edit:
```bash
cp settings/default_settings.toml settings/user_settings.toml
```

Key options:
```toml
betfair_data = true   # Include BSP prices
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

## 🗂️ Project Structure

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
│   ├── models/              # Data models
│   └── utils/               # Network, parsing helpers
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
└── logs/                    # Cron logs
```

---

## 🧪 Testing

### Test Full Pipeline

```bash
python tests/test_api_jobs.py
```

Runs racecards + results jobs, verifies:
- ✅ API connectivity
- ✅ Data synced
- ✅ Pedigree saved
- ✅ No duplicates

### Test Database Only

```bash
python tests/test_database_integrity.py
```

---

## 🔗 API Integration

Syncs to [nas_api_003](https://github.com/cwfmoore/nas_api_003) Django API.

| Endpoint | Purpose |
|----------|---------|
| `POST /scrape-racecards/` | Scrape racecards |
| `POST /sync-racecards/` | Save to database |
| `POST /scrape/` | Scrape + save results |

---

## ⚠️ Troubleshooting

### 🔴 403 Forbidden

**Cause:** Expired tokens

**Fix:** Update `AUTH_STATE` and `ACCESS_TOKEN` in `.env`

---

### 🔴 No races found

**Cause:** No racing scheduled

**Fix:** Normal on non-race days. Check Racing Post calendar.

---

### 🔴 API connection failed

**Fix:** Check API is running:
```bash
curl http://localhost:8000/api/racing-post/courses/
```

---

### 🔴 Jumps year confusion

> [!WARNING]
> For jumps racing, the year refers to **season start**.
>
> Example: 2025 Cheltenham Festival → Use `-y 2024` (2024-25 season)

---

## 📝 License

MIT
