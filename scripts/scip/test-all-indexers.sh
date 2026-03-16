#!/usr/bin/env bash
# Test SCIP indexers against multi-file fixtures.
# Each test: index → inspect with `scip print` → report results.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURES="$SCRIPT_DIR/fixtures"
export PATH="$HOME/bin:$HOME/go/bin:$HOME/.dotnet/tools:$PATH"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass=0
fail=0

header() { echo -e "\n${CYAN}══════════════════════════════════════════${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}══════════════════════════════════════════${NC}"; }
ok()     { echo -e "  ${GREEN}✓ $1${NC}"; ((pass++)); }
err()    { echo -e "  ${RED}✗ $1${NC}"; ((fail++)); }
info()   { echo -e "  ${YELLOW}→ $1${NC}"; }

check_tool() {
    if command -v "$1" &>/dev/null; then
        ok "$1 found: $(command -v "$1")"
        return 0
    else
        err "$1 not found"
        return 1
    fi
}

# ─── Python ────────────────────────────────────────────────────
test_python() {
    header "SCIP-PYTHON"
    check_tool scip-python || return

    cd "$FIXTURES/python"
    rm -f index.scip
    info "Indexing Python fixtures..."
    if scip-python index . --project-name=test-python 2>&1; then
        if [ -f index.scip ]; then
            ok "index.scip created ($(wc -c < index.scip) bytes)"
            info "Inspecting index..."
            scip print index.scip 2>&1 | head -40
            echo ""
            info "Stats:"
            scip stats index.scip 2>&1 | head -20
        else
            err "index.scip not created"
        fi
    else
        err "scip-python indexing failed"
    fi
}

# ─── TypeScript ────────────────────────────────────────────────
test_typescript() {
    header "SCIP-TYPESCRIPT"
    check_tool scip-typescript || return

    cd "$FIXTURES/typescript"
    rm -f index.scip
    info "Indexing TypeScript fixtures..."
    if scip-typescript index --output index.scip 2>&1; then
        if [ -f index.scip ]; then
            ok "index.scip created ($(wc -c < index.scip) bytes)"
            info "Inspecting index..."
            scip print index.scip 2>&1 | head -40
            echo ""
            info "Stats:"
            scip stats index.scip 2>&1 | head -20
        else
            err "index.scip not created"
        fi
    else
        err "scip-typescript indexing failed"
    fi
}

# ─── Go ────────────────────────────────────────────────────────
test_go() {
    header "SCIP-GO"
    check_tool scip-go || return

    cd "$FIXTURES/go"
    rm -f index.scip
    info "Indexing Go fixtures..."
    if scip-go --output=index.scip ./... 2>&1; then
        if [ -f index.scip ]; then
            ok "index.scip created ($(wc -c < index.scip) bytes)"
            info "Inspecting index..."
            scip print index.scip 2>&1 | head -40
            echo ""
            info "Stats:"
            scip stats index.scip 2>&1 | head -20
        else
            err "index.scip not created"
        fi
    else
        err "scip-go indexing failed"
    fi
}

# ─── .NET / C# ────────────────────────────────────────────────
test_dotnet() {
    header "SCIP-DOTNET"
    check_tool scip-dotnet || return

    cd "$FIXTURES/dotnet"
    rm -f index.scip
    info "Building .NET project first..."
    dotnet build --nologo -q 2>&1 || true
    info "Indexing .NET fixtures..."
    if scip-dotnet index 2>&1; then
        if [ -f index.scip ]; then
            ok "index.scip created ($(wc -c < index.scip) bytes)"
            info "Inspecting index..."
            scip print index.scip 2>&1 | head -40
            echo ""
            info "Stats:"
            scip stats index.scip 2>&1 | head -20
        else
            err "index.scip not created"
        fi
    else
        err "scip-dotnet indexing failed"
    fi
}

# ─── Main ──────────────────────────────────────────────────────
header "SCIP INDEXER TEST SUITE"
echo ""
info "Checking prerequisites..."
check_tool scip

test_python
test_typescript
test_go
test_dotnet

echo ""
header "RESULTS"
echo -e "  ${GREEN}Passed: $pass${NC}"
echo -e "  ${RED}Failed: $fail${NC}"
echo ""

# Clean up generated files
info "Cleaning up index.scip files..."
find "$FIXTURES" -name "index.scip" -delete 2>/dev/null || true
find "$FIXTURES" -name "*.scip" -delete 2>/dev/null || true

exit $fail
