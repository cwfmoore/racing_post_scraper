# Racing Post Scraper
# Containerized scraper for AM/PM cron jobs

FROM python:3.13-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
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

# Create error logs directory
RUN mkdir -p /app/error_logs

# Environment
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/London

ENTRYPOINT ["./docker-entrypoint.sh"]
