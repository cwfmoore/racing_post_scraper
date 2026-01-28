#!/bin/bash
# Racing Post Scraper Entrypoint
#
# Usage:
#   docker run rpscrape racecards           # Scrape today's racecards
#   docker run rpscrape results             # Scrape yesterday's results
#   docker run rpscrape results 2026/01/05  # Scrape specific date
#
# Features:
#   - Multi-region support (GB + IRE by default)
#   - Retry with exponential backoff (up to 23 hours)
#   - Clear error logging

set -o pipefail  # Catch errors in pipes

JOB="${1:-all}"
API_URL="${API_URL:-http://host.docker.internal:8000/api/racing-post}"
REGIONS="${REGIONS:-gb,ire}"

# Retry settings
MAX_RETRY_HOURS=23
INITIAL_BACKOFF_SECS=60      # 1 minute
MAX_BACKOFF_SECS=1800        # 30 minutes
MAX_RETRY_SECS=$((MAX_RETRY_HOURS * 3600))

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR: $1" >&2
}

log_warn() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  WARN: $1"
}

log_success() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $1"
}

# Retry a command with exponential backoff
# Usage: retry_with_backoff "description" command [args...]
# NOTE: All logs go to stderr to avoid polluting the JSON response on stdout
retry_with_backoff() {
    local description="$1"
    shift
    local cmd=("$@")

    local attempt=1
    local backoff=$INITIAL_BACKOFF_SECS
    local total_wait=0
    local result=""

    while [ $total_wait -lt $MAX_RETRY_SECS ]; do
        log "Attempt $attempt: $description" >&2

        # Run command and capture output
        if result=$("${cmd[@]}" 2>&1); then
            # Check if result is valid JSON with data
            if echo "$result" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
                echo "$result"
                return 0
            else
                log_warn "Invalid JSON response, retrying..." >&2
            fi
        else
            log_warn "Command failed (exit code: $?)" >&2
        fi

        # Check if we've exceeded max time
        total_wait=$((total_wait + backoff))
        if [ $total_wait -ge $MAX_RETRY_SECS ]; then
            log_error "Max retry time exceeded (${MAX_RETRY_HOURS}h). Giving up on: $description"
            return 1
        fi

        # Wait with backoff
        log "Waiting ${backoff}s before retry (total wait: ${total_wait}s / ${MAX_RETRY_SECS}s)..." >&2
        sleep $backoff

        # Exponential backoff, capped at max
        backoff=$((backoff * 2))
        if [ $backoff -gt $MAX_BACKOFF_SECS ]; then
            backoff=$MAX_BACKOFF_SECS
        fi

        attempt=$((attempt + 1))
    done

    log_error "Max retry time exceeded. Giving up on: $description"
    return 1
}

# API call with timeout
api_post() {
    local endpoint="$1"
    local data="$2"
    local timeout="${3:-300}"

    curl -sf -X POST "$API_URL/$endpoint/" \
        -H "Content-Type: application/json" \
        -d "$data" \
        --max-time "$timeout" \
        --connect-timeout 30
}

# API call that accepts piped data
api_post_stdin() {
    local endpoint="$1"
    local timeout="${2:-300}"

    curl -sf -X POST "$API_URL/$endpoint/" \
        -H "Content-Type: application/json" \
        --data-binary @- \
        --max-time "$timeout" \
        --connect-timeout 30
}

# ═══════════════════════════════════════════════════════════════════════════════
# RACECARDS JOB
# ═══════════════════════════════════════════════════════════════════════════════

run_racecards() {
    log "═══════════════════════════════════════════════════════════"
    log "RACECARDS JOB: Scraping for regions=$REGIONS"
    log "═══════════════════════════════════════════════════════════"

    local total_races=0
    local total_entries=0
    local failed_regions=()

    # Loop through each region
    IFS=',' read -ra REGION_ARRAY <<< "$REGIONS"
    for REGION in "${REGION_ARRAY[@]}"; do
        log ""
        log "--- Processing region: $REGION ---"

        # Step 1: Scrape racecards (with retry)
        log "Step 1: Scraping from Racing Post..."

        SCRAPE=$(retry_with_backoff "Scrape racecards for $REGION" \
            api_post "scrape-racecards" \
            "{\"day\":1,\"region\":\"$REGION\",\"fetch_stats\":true,\"fetch_profiles\":true}")

        if [ $? -ne 0 ] || [ -z "$SCRAPE" ]; then
            log_error "Failed to scrape racecards for $REGION after all retries"
            failed_regions+=("$REGION")
            continue
        fi

        RACES=$(echo "$SCRAPE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('races',0))" 2>/dev/null || echo "0")
        DATE=$(echo "$SCRAPE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('date','unknown'))" 2>/dev/null || echo "unknown")

        log "Scraped $RACES races for $DATE ($REGION)"

        if [ "$RACES" = "0" ]; then
            log "No races found for $REGION. Skipping sync."
            continue
        fi

        total_races=$((total_races + RACES))

        # Step 2: Sync to database (with retry)
        log "Step 2: Syncing to database..."

        SYNC_DATA=$(echo "$SCRAPE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({'data':d.get('data',{}),'scrape_date':d.get('date','')}))" 2>/dev/null)

        if [ -z "$SYNC_DATA" ]; then
            log_error "Failed to prepare sync data for $REGION"
            failed_regions+=("$REGION")
            continue
        fi

        SYNC=$(echo "$SYNC_DATA" | retry_with_backoff "Sync racecards for $REGION" api_post_stdin "sync-racecards")

        if [ $? -ne 0 ] || [ -z "$SYNC" ]; then
            log_error "Failed to sync racecards for $REGION after all retries"
            failed_regions+=("$REGION")
            continue
        fi

        ENTRIES=$(echo "$SYNC" | python3 -c "import sys,json; print(json.load(sys.stdin).get('entries_created',0))" 2>/dev/null || echo "0")
        UPDATED=$(echo "$SYNC" | python3 -c "import sys,json; print(json.load(sys.stdin).get('entries_updated',0))" 2>/dev/null || echo "0")

        log_success "Synced $ENTRIES created, $UPDATED updated for $REGION"
        total_entries=$((total_entries + ENTRIES + UPDATED))
    done

    # Summary
    log ""
    log "═══════════════════════════════════════════════════════════"
    if [ ${#failed_regions[@]} -eq 0 ]; then
        log_success "RACECARDS JOB COMPLETE: $total_races races, $total_entries entries"
        return 0
    else
        log_error "RACECARDS JOB COMPLETED WITH ERRORS"
        log_error "Failed regions: ${failed_regions[*]}"
        log "Successful: $total_races races, $total_entries entries"
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS JOB
# ═══════════════════════════════════════════════════════════════════════════════

run_results() {
    local DATE="${1:-$(date -d 'yesterday' '+%Y/%m/%d')}"

    log "═══════════════════════════════════════════════════════════"
    log "RESULTS JOB: Scraping for $DATE, regions=$REGIONS"
    log "═══════════════════════════════════════════════════════════"

    local total_races=0
    local total_runs=0
    local total_bsp=0
    local failed_regions=()

    # Loop through each region
    IFS=',' read -ra REGION_ARRAY <<< "$REGIONS"
    for REGION in "${REGION_ARRAY[@]}"; do
        log ""
        log "--- Processing region: $REGION ---"

        # Scrape results (with retry)
        RESULT=$(retry_with_backoff "Scrape results for $REGION ($DATE)" \
            api_post "scrape" \
            "{\"date\":\"$DATE\",\"region\":\"$REGION\",\"race_type\":\"all\",\"betfair\":true}" \
            600)

        if [ $? -ne 0 ] || [ -z "$RESULT" ]; then
            log_error "Failed to scrape results for $REGION after all retries"
            failed_regions+=("$REGION")
            continue
        fi

        RACES=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('races_created',0)+d.get('races_updated',0))" 2>/dev/null || echo "0")
        RUNS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('runs_created',0)+d.get('runs_updated',0))" 2>/dev/null || echo "0")
        BSP=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('bsp_rows_fetched',0))" 2>/dev/null || echo "0")

        # Check BSP coverage
        if [ "$RUNS" -gt 0 ] && [ "$BSP" -gt 0 ]; then
            BSP_PCT=$((BSP * 100 / RUNS))
            if [ "$BSP_PCT" -lt 80 ]; then
                log_warn "BSP coverage low: $BSP/$RUNS ($BSP_PCT%)"
            else
                log_success "BSP: $BSP rows ($BSP_PCT% coverage)"
            fi
        elif [ "$RUNS" -gt 0 ] && [ "$BSP" -eq 0 ]; then
            log_warn "BSP: 0 rows fetched (0% coverage)"
        fi

        log_success "Processed $RACES races, $RUNS runs for $REGION"

        total_races=$((total_races + RACES))
        total_runs=$((total_runs + RUNS))
        total_bsp=$((total_bsp + BSP))
    done

    # Summary
    log ""
    log "═══════════════════════════════════════════════════════════"
    if [ ${#failed_regions[@]} -eq 0 ]; then
        # Calculate overall BSP coverage
        if [ "$total_runs" -gt 0 ]; then
            TOTAL_BSP_PCT=$((total_bsp * 100 / total_runs))
            log_success "RESULTS JOB COMPLETE: $total_races races, $total_runs runs, $total_bsp BSP ($TOTAL_BSP_PCT%)"
        else
            log_success "RESULTS JOB COMPLETE: $total_races races, $total_runs runs"
        fi
        return 0
    else
        log_error "RESULTS JOB COMPLETED WITH ERRORS"
        log_error "Failed regions: ${failed_regions[*]}"
        log "Successful: $total_races races, $total_runs runs"
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

case "$JOB" in
    am|racecards)
        run_racecards
        exit $?
        ;;

    pm|results)
        run_results "$2"
        exit $?
        ;;

    all)
        # Run both jobs: racecards (today) + results (yesterday)
        log "═══════════════════════════════════════════════════════════"
        log "DAILY SCRAPE: Running racecards + results"
        log "═══════════════════════════════════════════════════════════"

        RC_EXIT=0
        RES_EXIT=0

        run_racecards || RC_EXIT=$?
        echo ""
        run_results || RES_EXIT=$?

        log ""
        log "═══════════════════════════════════════════════════════════"
        if [ $RC_EXIT -eq 0 ] && [ $RES_EXIT -eq 0 ]; then
            log_success "DAILY SCRAPE COMPLETE"
            exit 0
        else
            log_error "DAILY SCRAPE COMPLETED WITH ERRORS"
            [ $RC_EXIT -ne 0 ] && log_error "  Racecards job failed"
            [ $RES_EXIT -ne 0 ] && log_error "  Results job failed"
            exit 1
        fi
        ;;

    help)
        echo "Racing Post Scraper"
        echo ""
        echo "Usage:"
        echo "  docker run rpscrape                     # Run both jobs (default)"
        echo "  docker run rpscrape all                 # Run both jobs"
        echo "  docker run rpscrape racecards           # Scrape today's racecards only"
        echo "  docker run rpscrape results             # Scrape yesterday's results only"
        echo "  docker run rpscrape results 2026/01/05  # Scrape specific date"
        echo ""
        echo "Environment:"
        echo "  API_URL   - API endpoint (default: http://host.docker.internal:8000/api/racing-post)"
        echo "  REGIONS   - Comma-separated region codes (default: gb,ire)"
        echo ""
        echo "Retry Settings:"
        echo "  - Max retry time: ${MAX_RETRY_HOURS} hours"
        echo "  - Initial backoff: ${INITIAL_BACKOFF_SECS}s (1 min)"
        echo "  - Max backoff: ${MAX_BACKOFF_SECS}s (30 min)"
        echo "  - Exponential backoff between retries"
        ;;

    *)
        # Unknown argument - show help
        echo "Unknown command: $JOB"
        exec "$0" help
        ;;
esac
