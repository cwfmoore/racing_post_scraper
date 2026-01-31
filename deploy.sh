#!/bin/bash
# deploy.sh - NAS deployment script for Racing Post scraper
set -e

# Ensure PATH is set for cron environment
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# Script directory (works from anywhere)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="racing_post_scraper"
API_URL="http://192.168.1.145:8000/api/logs/"
HOSTNAME=$(hostname)
START_TIME=$(date +%s)

# Post log to central API with metadata (fails silently)
api_log() {
    local message="$1"
    local metadata="$2"
    local time_stamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    if [ -z "$metadata" ]; then
        metadata="null"
    fi

    curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -d "{\"time_stamp\": \"$time_stamp\", \"app_name\": \"$APP_NAME\", \"log_type\": \"deployment\", \"message\": \"$message\", \"hostname\": \"$HOSTNAME\", \"metadata\": $metadata}" \
        >/dev/null 2>&1 || true
}

api_log "Deploy started" "{\"stage\": \"start\"}"

echo "========================================="
echo "Deploy started: $(date '+%Y-%m-%d %H:%M:%S UTC')"
echo "========================================="

# Trust git directory (needed for cron)
git config --global --add safe.directory "$SCRIPT_DIR" 2>/dev/null || true

# Pull latest code
echo "[1/3] Pulling latest code..."
git pull origin master

# Capture git info after pull
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# Build container (quiet mode to avoid log spam)
echo "[2/3] Building Docker image..."
docker compose build --quiet

# Run scraper (both racecards + results)
echo "[3/3] Running scraper..."
docker compose run --rm scraper

echo ""
echo "========================================="
echo "Deploy completed: $(date '+%Y-%m-%d %H:%M:%S UTC')"
echo "========================================="

# Calculate duration
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

api_log "Deploy complete [${GIT_BRANCH}@${GIT_COMMIT}] (${DURATION}s)" "{\"stage\": \"complete\", \"git_commit\": \"$GIT_COMMIT\", \"git_branch\": \"$GIT_BRANCH\", \"duration_seconds\": $DURATION}"
