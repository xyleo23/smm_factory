FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# System deps required by Playwright and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user early so we can chown at copy time
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -m -s /bin/sh appuser

WORKDIR /app

# --- dependency layer (cached separately from source) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browser + system deps (needs root)
RUN playwright install chromium && playwright install-deps

# --- application source ---
COPY . .

# Ensure logs dir exists and is writable by appuser
RUN mkdir -p logs data && chown -R appuser:appgroup /app

USER appuser

CMD ["python", "main.py"]
