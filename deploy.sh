#!/bin/bash
# deploy.sh - NAS deployment script for Racing Post scraper
# Cron: 0 6 * * * /path/to/racing_post_scraper/deploy.sh >> /path/to/racing_post_scraper/logs/cron/$(date +\%Y-\%m-\%d)_cron.txt 2>&1
#
# Flow: git pull → docker build → run (racecards + results) → exit

set -e

# Ensure PATH is set for cron environment
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# Script directory (works from anywhere)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create log directories if missing
mkdir -p logs/deploy logs/cron logs/error

# Remove .gitkeep files (not needed at runtime)
find logs -name ".gitkeep" -delete 2>/dev/null || true

# Log file for this run
LOG_FILE="logs/deploy/$(date +%Y-%m-%d)_deploy_log.txt"

{
    echo "========================================="
    echo "Deploy started: $(date '+%Y-%m-%d %H:%M:%S UTC')"
    echo "========================================="

    # Trust git directory (needed for cron)
    git config --global --add safe.directory "$SCRIPT_DIR" 2>/dev/null || true

    # Pull latest code
    echo "[1/3] Pulling latest code..."
    git pull origin main

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

} 2>&1 | tee -a "$LOG_FILE"

# Cleanup old logs (90 days)
find logs/deploy -name "*.txt" -mtime +90 -delete 2>/dev/null || true
find logs/cron -name "*.txt" -mtime +90 -delete 2>/dev/null || true
find logs/error -name "*.txt" -mtime +90 -delete 2>/dev/null || true
