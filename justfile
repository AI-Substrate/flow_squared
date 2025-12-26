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

# === CLI Examples ===

# Example: get a node by ID (outputs JSON)
example-get-node:
    uv run fs2 get-node "file:src/fs2/cli/get_node.py"

# Example: get a node and pipe to jq
example-get-node-jq:
    uv run fs2 get-node "file:src/fs2/cli/get_node.py" | jq '.node_id, .category'

# Example: get a node and write to file
example-get-node-file:
    uv run fs2 get-node "file:src/fs2/cli/get_node.py" --file /tmp/node.json
    cat /tmp/node.json | jq '.node_id'

# Example: show tree of the project
example-tree:
    uv run fs2 tree

# Example: show tree with depth limit
example-tree-depth:
    uv run fs2 tree --depth 2

# === Reports ===

# Show graph database statistics (nodes by language, type, category)
graph-report:
    uv run python scripts/graph_report.py

# Test semantic search with predefined queries
test-semantic-search:
    uv run python scripts/test_semantic_search.py

# === Fixture Generation ===

# Generate fixture graph for testing (requires Azure credentials for embeddings/smart_content)
# Two-step process per Subtask 001:
# 1. Scan samples with embeddings (fs2 scan handles structure + embeddings)
# 2. Enrich with smart_content via LLM (script handles custom prompts + rate limiting)
generate-fixtures:
    @echo "Step 1: Scanning samples with embeddings..."
    uv run fs2 --graph-file tests/fixtures/fixture_graph.pkl scan \
        --scan-path tests/fixtures/samples \
        --no-smart-content
    @echo "Step 2: Enriching with smart_content..."
    uv run python scripts/enrich_fixture_smart_content.py
    @echo "Done! Fixture graph saved to tests/fixtures/fixture_graph.pkl"

# Generate fixtures without smart_content enrichment (faster, for testing scan changes)
generate-fixtures-quick:
    uv run fs2 --graph-file tests/fixtures/fixture_graph.pkl scan \
        --scan-path tests/fixtures/samples \
        --no-smart-content
