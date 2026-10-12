# ========================================================
# C30 Digital - Production Container for Google Cloud Run
# Python 3.12-slim base image matching GATED_CONTENT_SPEC.md
# ========================================================

FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Cloud Run injects PORT environment variable (default 8080)
ENV PORT=8080

EXPOSE 8080

# Production WSGI server (gunicorn) with worker timeout configuration
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
