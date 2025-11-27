# Justfile for fs2 project
# Run `just --list` to see available commands

# Default recipe - show available commands
default:
    @just --list

# Run all tests
test:
    python -m pytest tests/ -v

# Run tests with coverage
test-cov:
    python -m pytest tests/ -v --cov=fs2 --cov-report=term-missing

# Run only unit tests
test-unit:
    python -m pytest tests/unit/ -v

# Run tests matching a pattern
test-match PATTERN:
    python -m pytest tests/ -v -k "{{PATTERN}}"

# === Code Quality ===

# Format, fix, and test (the main workflow)
fft: fix test

# Fix and format code (ruff replaces black, isort, autoflake)
fix:
    ruff check --fix src/ tests/
    ruff format src/ tests/

# Just check without fixing
lint:
    ruff check src/ tests/
    ruff format --check src/ tests/
