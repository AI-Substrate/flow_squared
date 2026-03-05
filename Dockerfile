# fs2 Server — Development Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ src/

# Expose port
EXPOSE 8000

# Default command (overridden by docker-compose)
CMD ["uv", "run", "uvicorn", "fs2.server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
