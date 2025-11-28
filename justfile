# Justfile for fs2 project
# Run `just --list` to see available commands

# Default recipe - show available commands
default:
    @just --list

# === Setup ===

# Install dev dependencies
install:
    uv sync --extra dev

# Run all tests
test:
    uv run pytest tests/ -v

# Run tests with coverage
test-cov:
    uv run pytest tests/ -v --cov=fs2 --cov-report=term-missing

# Run only unit tests
test-unit:
    uv run pytest tests/unit/ -v

# Run tests matching a pattern
test-match PATTERN:
    uv run pytest tests/ -v -k "{{PATTERN}}"

# === Code Quality ===

# Format, fix, and test (the main workflow)
fft: fix test

# Fix and format code (ruff replaces black, isort, autoflake)
fix:
    uv run ruff check --fix src/ tests/
    uv run ruff format src/ tests/

# Just check without fixing
lint:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/
