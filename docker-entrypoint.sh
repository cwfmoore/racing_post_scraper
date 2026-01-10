#!/bin/bash
# Racing Post Scraper Entrypoint
#
# Usage:
#   docker run rpscrape am              # AM job: racecards
#   docker run rpscrape pm              # PM job: yesterday's results
#   docker run rpscrape pm 2026/01/05   # PM job: specific date

set -e

JOB="${1:-help}"
API_URL="${API_URL:-http://host.docker.internal:8000/api/racing-post}"
REGIONS="${REGIONS:-gb,ire}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

case "$JOB" in
    am|racecards)
        log "AM JOB: Scraping racecards for regions=$REGIONS"

        TOTAL_RACES=0
        TOTAL_ENTRIES=0

        # Loop through each region
        IFS=',' read -ra REGION_ARRAY <<< "$REGIONS"
        for REGION in "${REGION_ARRAY[@]}"; do
            log "--- Processing region: $REGION ---"

            # Scrape racecards
            log "Step 1: Scraping from Racing Post..."
            SCRAPE=$(curl -sf -X POST "$API_URL/scrape-racecards/" \
                -H "Content-Type: application/json" \
                -d "{\"day\":1,\"region\":\"$REGION\",\"fetch_stats\":true,\"fetch_profiles\":true}" \
                --max-time 300)

            RACES=$(echo "$SCRAPE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('races',0))")
            DATE=$(echo "$SCRAPE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('date',''))")
            log "Scraped $RACES races for $DATE ($REGION)"

            if [ "$RACES" = "0" ]; then
                log "No races found for $REGION. Skipping."
                continue
            fi

            TOTAL_RACES=$((TOTAL_RACES + RACES))

            # Sync to database (pipe data to curl to avoid argument length limits)
            log "Step 2: Syncing to database..."
            SYNC=$(echo "$SCRAPE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({'data':d.get('data',{}),'scrape_date':d.get('date','')}))" | \
                curl -sf -X POST "$API_URL/sync-racecards/" \
                -H "Content-Type: application/json" \
                --data-binary @- \
                --max-time 300)

            ENTRIES=$(echo "$SYNC" | python3 -c "import sys,json; print(json.load(sys.stdin).get('entries_created',0))")
            log "Synced $ENTRIES racecard entries for $REGION"
            TOTAL_ENTRIES=$((TOTAL_ENTRIES + ENTRIES))
        done

        log "AM JOB COMPLETE: $TOTAL_RACES races, $TOTAL_ENTRIES entries across all regions"
        ;;

    pm|results)
        DATE="${2:-$(date -d 'yesterday' '+%Y/%m/%d')}"
        log "PM JOB: Scraping results for $DATE, regions=$REGIONS"

        TOTAL_RACES=0
        TOTAL_RUNS=0

        # Loop through each region
        IFS=',' read -ra REGION_ARRAY <<< "$REGIONS"
        for REGION in "${REGION_ARRAY[@]}"; do
            log "--- Processing region: $REGION ---"

            RESULT=$(curl -sf -X POST "$API_URL/scrape/" \
                -H "Content-Type: application/json" \
                -d "{\"date\":\"$DATE\",\"region\":\"$REGION\",\"race_type\":\"all\",\"betfair\":true}" \
                --max-time 600)

            RACES=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('races_created',0)+d.get('races_updated',0))")
            RUNS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('runs_created',0)+d.get('runs_updated',0))")
            log "Processed $RACES races, $RUNS runs for $REGION"

            TOTAL_RACES=$((TOTAL_RACES + RACES))
            TOTAL_RUNS=$((TOTAL_RUNS + RUNS))
        done

        log "PM JOB COMPLETE: $TOTAL_RACES races, $TOTAL_RUNS runs across all regions"
        ;;

    help|*)
        echo "Racing Post Scraper"
        echo ""
        echo "Usage:"
        echo "  docker run rpscrape am              # Scrape today's racecards"
        echo "  docker run rpscrape pm              # Scrape yesterday's results"
        echo "  docker run rpscrape pm 2026/01/05   # Scrape specific date"
        echo ""
        echo "Environment:"
        echo "  API_URL  - API endpoint (default: http://host.docker.internal:8000/api/racing-post)"
        echo "  REGIONS  - Comma-separated region codes (default: gb,ire)"
        ;;
esac
