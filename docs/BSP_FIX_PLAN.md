# BSP Collection Reliability Fix Plan

## Problem Summary

BSP data for Jan 27, 2026 was not collected despite the scraper running successfully. This happened because:
1. BSP fetch errors are logged as warnings but don't fail the job
2. No validation that BSP data was actually saved
3. No alerting when BSP coverage drops

## Root Cause Analysis

| Component | Issue |
|-----------|-------|
| `views.py:505-506` | BSP errors silently ignored |
| API response | No BSP count returned |
| Post-import | No validation check |
| Monitoring | No coverage alerts |

## Proposed Fixes

### 1. Add BSP Count to API Response

**File:** `nas_api_003/racing_post/views.py`

```python
# After import loop, count BSP records
bsp_count = BetfairPrice.objects.filter(
    run__race__date=race_date
).count()

return Response({
    "success": True,
    "races_created": total_result.races_created,
    "runs_created": total_result.runs_created,
    "bsp_created": bsp_count,  # NEW
    ...
})
```

### 2. Improve BSP Error Handling

**File:** `nas_api_003/racing_post/views.py`

```python
# Current (line 505-506):
except Exception as e:
    logger.warning(f"Failed to fetch Betfair data: {e}")

# Proposed:
except Exception as e:
    logger.error(f"BSP FETCH FAILED: {e}")
    # Store error for response
    total_result.errors.append(f"BSP fetch failed: {e}")
```

### 3. Add BSP Validation to Docker Script

**File:** `racing_post_scraper/docker-entrypoint.sh`

```bash
# After results scrape, check BSP count
BSP=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('bsp_created',0))")
RUNS=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('runs_created',0))")

# Alert if BSP coverage < 80%
if [ "$RUNS" -gt 0 ]; then
    COVERAGE=$((BSP * 100 / RUNS))
    if [ "$COVERAGE" -lt 80 ]; then
        log_warn "BSP coverage low: $BSP/$RUNS ($COVERAGE%)"
    fi
fi
```

### 4. Add EOD Validation Check

**File:** `racing_post_scraper/claude_tools.py`

Add to `get_eod_validation()`:

```python
# Check BSP coverage for yesterday
bsp_check = self.run_sql("""
    SELECT
        COUNT(DISTINCT ru.id) as total_runs,
        COUNT(DISTINCT bp.run_id) as with_bsp
    FROM rp_race r
    JOIN rp_run ru ON r.race_id = ru.race_id
    LEFT JOIN rp_betfair_price bp ON ru.id = bp.run_id
    WHERE r.date = CURRENT_DATE - 1
""")

bsp_pct = (bsp_check['with_bsp'] / bsp_check['total_runs'] * 100) if bsp_check['total_runs'] > 0 else 0
if bsp_pct < 80:
    issues.append(f"BSP coverage low: {bsp_pct:.0f}%")
```

### 5. Add Retry for BSP Fetch

**File:** `nas_api_003/racing_post/views.py`

```python
# Retry BSP fetch up to 3 times
for attempt in range(3):
    try:
        betfair = Betfair(race_urls)
        betfair_data = betfair.data
        if betfair_data:
            break
    except Exception as e:
        logger.warning(f"BSP fetch attempt {attempt+1}/3 failed: {e}")
        if attempt < 2:
            time.sleep(5)
```

## Implementation Priority

| Priority | Fix | Effort |
|----------|-----|--------|
| 1 | Add BSP count to response | Low |
| 2 | Improve error logging | Low |
| 3 | Add EOD validation | Medium |
| 4 | Add Docker coverage check | Low |
| 5 | Add retry logic | Medium |

## Testing

After implementation:
1. Run scraper with `betfair: true`
2. Verify BSP count in response
3. Check EOD validation catches low coverage
4. Test retry by temporarily blocking Betfair URL

## Backfill Script

For future BSP backfills, use:
```bash
python scripts/generate_bsp_sql.py
psql -f scripts/bsp_backfill.sql
```
