#!/usr/bin/env bash
#
# fs2-watch.sh - Watch directories and re-run fs2 scan on changes
#
# Usage:
#   ./scripts/fs2-watch.sh                     # Watch current directory
#   ./scripts/fs2-watch.sh src/                # Watch single directory
#   ./scripts/fs2-watch.sh src/ tests/ docs/   # Watch multiple directories
#   ./scripts/fs2-watch.sh --no-embeddings src/
#   ./scripts/fs2-watch.sh --help
#
# Requires: watchexec (recommended), fswatch (macOS), or inotify-tools (Linux)
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*) echo "macos" ;;
        Linux*)  echo "linux" ;;
        *)       echo "unknown" ;;
    esac
}

OS=$(detect_os)

# Print colored message
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Show help
show_help() {
    cat << 'EOF'
fs2-watch - Watch directories and re-run fs2 scan on changes

USAGE:
    ./scripts/fs2-watch.sh [OPTIONS] [PATHS...]

OPTIONS:
    --no-embeddings    Skip embedding generation (faster, no API calls)
    --verbose, -v      Show verbose scan output
    --help, -h         Show this help message

PATHS:
    Directories to watch (relative to current working directory)
    Defaults to current directory if none specified

EXAMPLES:
    ./scripts/fs2-watch.sh                        # Watch current dir
    ./scripts/fs2-watch.sh src/                   # Watch src/
    ./scripts/fs2-watch.sh src/ tests/            # Watch multiple dirs
    ./scripts/fs2-watch.sh --no-embeddings src/   # Fast mode

REQUIREMENTS:
    Requires one of these file watchers (in order of preference):
    - watchexec (recommended): cargo install watchexec-cli / brew install watchexec
    - fswatch (macOS only):    brew install fswatch
    - inotifywait (Linux):     apt install inotify-tools

EOF
}

# Check if a command exists
has_cmd() {
    command -v "$1" &>/dev/null
}

# Install instructions for watchexec
show_watchexec_install() {
    echo ""
    echo "Install watchexec (recommended):"
    echo ""

    if [[ "$OS" == "macos" ]]; then
        echo "  brew install watchexec"
        echo ""
        echo "Or via Cargo (requires Rust):"
    elif [[ "$OS" == "linux" ]]; then
        echo "  # Debian/Ubuntu:"
        echo "  sudo apt install watchexec"
        echo ""
        echo "  # Or via Cargo (requires Rust):"
    fi

    echo "  cargo install watchexec-cli"
    echo ""

    if ! has_cmd cargo; then
        echo -e "${YELLOW}Rust/Cargo not installed.${NC} Install Rust first:"
        echo ""
        echo "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
        echo ""
    fi
}

# Show fallback options
show_fallback_install() {
    echo "Alternative file watchers:"
    echo ""

    if [[ "$OS" == "macos" ]]; then
        echo "  brew install fswatch    # macOS native"
    elif [[ "$OS" == "linux" ]]; then
        echo "  sudo apt install inotify-tools   # Linux inotify"
    fi
    echo ""
}

# Find the best available watcher
find_watcher() {
    if has_cmd watchexec; then
        echo "watchexec"
    elif has_cmd fswatch && [[ "$OS" == "macos" ]]; then
        echo "fswatch"
    elif has_cmd inotifywait && [[ "$OS" == "linux" ]]; then
        echo "inotifywait"
    else
        echo "none"
    fi
}

# Run with watchexec (best option)
run_watchexec() {
    local watch_args=("${WATCH_PATHS[@]}")
    local cmd_args=()

    for path in "${watch_args[@]}"; do
        cmd_args+=(-w "$path")
    done

    info "Using watchexec (recommended)"
    info "Watching: ${watch_args[*]}"
    [[ ${#SCAN_ARGS[@]} -gt 0 ]] && info "Scan options: ${SCAN_ARGS[*]}"
    echo ""
    success "Watching for changes... (Ctrl+C to stop)"
    echo ""

    # Note: --restart kills running scan on new changes (always get latest)
    # --debounce waits for activity to settle before triggering
    # Using longer debounce (2s) to batch rapid file changes
    exec watchexec "${cmd_args[@]}" \
        --debounce 2s \
        --ignore ".fs2/**" \
        --ignore "**/*.pickle" \
        --ignore "**/__pycache__/**" \
        --ignore ".git/**" \
        --ignore "**/*.pyc" \
        --ignore ".uv_cache/**" \
        --no-vcs-ignore \
        -- fs2 scan "${SCAN_ARGS[@]}"
}

# Run with fswatch (macOS)
run_fswatch() {
    local watch_paths="${WATCH_PATHS[*]}"

    warn "Using fswatch (events may queue during long scans)"
    info "Watching: $watch_paths"
    echo ""
    success "Watching for changes... (Ctrl+C to stop)"
    echo ""

    # shellcheck disable=SC2086
    fswatch -o \
        --exclude ".fs2" \
        --exclude ".git" \
        --exclude "__pycache__" \
        --exclude "*.pickle" \
        $watch_paths | while read -r _; do
        echo ""
        info "Change detected, running fs2 scan..."
        fs2 scan "${SCAN_ARGS[@]}" || true
    done
}

# Run with inotifywait (Linux)
run_inotifywait() {
    local watch_paths="${WATCH_PATHS[*]}"

    warn "Using inotifywait (events may be missed during scans)"
    info "Watching: $watch_paths"
    echo ""
    success "Watching for changes... (Ctrl+C to stop)"
    echo ""

    while true; do
        # shellcheck disable=SC2086
        inotifywait -r -e modify,create,delete \
            --exclude '(\.fs2|\.git|__pycache__|\.pickle$)' \
            $watch_paths 2>/dev/null || true

        echo ""
        info "Change detected, running fs2 scan..."
        fs2 scan "${SCAN_ARGS[@]}" || true
    done
}

# Main
main() {
    # Parse arguments
    WATCH_PATHS=()
    SCAN_ARGS=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                show_help
                exit 0
                ;;
            --no-embeddings)
                SCAN_ARGS+=(--no-embeddings)
                shift
                ;;
            --verbose|-v)
                SCAN_ARGS+=(--verbose)
                shift
                ;;
            -*)
                error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
            *)
                # Resolve path relative to current working directory
                if [[ -d "$1" ]]; then
                    WATCH_PATHS+=("$1")
                else
                    error "Directory not found: $1"
                    exit 1
                fi
                shift
                ;;
        esac
    done

    # Default to current directory
    if [[ ${#WATCH_PATHS[@]} -eq 0 ]]; then
        WATCH_PATHS=(.)
    fi

    # Check for fs2
    if ! has_cmd fs2; then
        error "fs2 not found in PATH"
        echo ""
        echo "Install fs2 first:"
        echo "  uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 install"
        exit 1
    fi

    # Find and run appropriate watcher
    WATCHER=$(find_watcher)

    case "$WATCHER" in
        watchexec)
            run_watchexec
            ;;
        fswatch)
            run_fswatch
            ;;
        inotifywait)
            run_inotifywait
            ;;
        none)
            error "No file watcher found!"
            echo ""
            show_watchexec_install
            show_fallback_install
            exit 1
            ;;
    esac
}

main "$@"
