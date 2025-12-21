# Multi-stage Dockerfile for Python web application
#
# Stages:
# 1. builder - Install dependencies and build wheels
# 2. runtime - Minimal production image
#
# Build: docker build -t app:latest .
# Run:   docker run -p 8080:8080 app:latest

# ==============================================================================
# Stage 1: Builder
# ==============================================================================
FROM python:3.12-slim-bookworm AS builder

# Prevent Python from writing bytecode and buffering output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
WORKDIR /build

# Copy dependency files first for better layer caching
COPY requirements.txt requirements-dev.txt* ./

# Install production dependencies
RUN pip install --upgrade pip wheel setuptools && \
    pip install -r requirements.txt

# Copy and install application
COPY pyproject.toml setup.py* ./
COPY src/ ./src/

# Install application package
RUN pip install . --no-deps

# ==============================================================================
# Stage 2: Runtime
# ==============================================================================
FROM python:3.12-slim-bookworm AS runtime

# Application metadata
LABEL maintainer="team@example.com" \
      version="1.0.0" \
      description="Production web application"

# Security: Run as non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Application configuration
ENV APP_HOST=0.0.0.0 \
    APP_PORT=8080 \
    APP_WORKERS=4 \
    APP_LOG_LEVEL=info

# Create application directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup scripts/entrypoint.sh ./

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${APP_PORT}/health || exit 1

# Expose application port
EXPOSE ${APP_PORT}

# Default command
ENTRYPOINT ["./entrypoint.sh"]
CMD ["serve"]
