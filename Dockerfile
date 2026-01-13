# Racing Post Scraper
# Containerized scraper for daily cron deployment

FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy scraper code
COPY scripts/ ./scripts/
COPY courses/ ./courses/
COPY settings/ ./settings/

# Copy entrypoint
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Create log directories (standardised structure)
RUN mkdir -p /app/logs/error /app/logs/deploy /app/logs/cron /app/error_logs

# Environment
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Healthcheck (verifies entrypoint is running)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "docker-entrypoint" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
