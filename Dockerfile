FROM python:3.12-slim

WORKDIR /app

# Prevent Python from writing .pyc files and force logs to flush
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies into the image
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the actual app code
COPY . .

# Default command can be overridden by docker-compose
CMD ["celery", "-A", "worker.worker:celery_app", "worker", "--loglevel=info"]