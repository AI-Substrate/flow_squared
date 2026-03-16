# Justfile for fs2 project
# Run `just --list` to see available commands

# Default recipe - show available commands
default:
    @just --list

# === Setup ===

# Install dev dependencies
install:
    uv sync --extra dev

# Install/reinstall the fs2 CLI tool (use after code changes)
install-cli:
    uv tool install --force --reinstall fs2 --from .

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

# Dump MCP tools (shows what agents see when connecting)
mcp-dump TOOL="":
    @uv run python scripts/mcp_tools_dump.py {{TOOL}} 2>/dev/null

# === Documentation Build ===

# Build bundled docs: copy from docs/how/user/ to src/fs2/docs/
doc-build:
    uv run python scripts/doc_build.py

# === Fixture Generation ===

# Generate fixture graph with embeddings and smart content (requires Azure credentials)
generate-fixtures:
    uv run fs2 --graph-file tests/fixtures/fixture_graph.pkl scan \
        --scan-path tests/fixtures/samples
    @echo "Done! Fixture graph saved to tests/fixtures/fixture_graph.pkl"

# Generate fixtures without smart_content (faster, for testing scan changes)
generate-fixtures-quick:
    uv run fs2 --graph-file tests/fixtures/fixture_graph.pkl scan \
        --scan-path tests/fixtures/samples \
        --no-smart-content

# Generate the interactive codebase graph report
report:
    uv run python -m fs2 --graph-file .fs2/graph-full-crossrefs.pickle report codebase-graph

# === Watch Mode ===

# Start watch mode with full scans (embeddings + smart content)
watch:
    uv run fs2 watch

# Start watch mode with verbose output
watch-verbose:
    uv run fs2 watch --verbose

# Start watch mode without embeddings/smart content (faster for testing)
watch-quick:
    uv run fs2 watch --no-embeddings --no-smart-content

# Demo: Start watch mode, then in another terminal run `just watch-trigger` to see it work
watch-demo:
    @echo "Starting watch mode (quick mode for demo)..."
    @echo "In another terminal, run: just watch-trigger"
    @echo "Press Ctrl+C to stop"
    @echo ""
    uv run fs2 watch --no-embeddings --no-smart-content

# Trigger a file change to test watch mode (run in separate terminal)
watch-trigger:
    @echo "Triggering file change..."
    @touch src/fs2/__init__.py
    @echo "Done! Check the watch terminal for scan output."
