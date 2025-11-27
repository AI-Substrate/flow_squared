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

fft: format fix test

# === Code Quality ===
ff: format fix

# Format code automatically (like dart format)
format:
    black src/ tests/
    isort src/ tests/

# Fix code issues automatically (like dart fix)
fix:
    autoflake --remove-all-unused-imports --remove-unused-variables --in-place --recursive src/ tests/
