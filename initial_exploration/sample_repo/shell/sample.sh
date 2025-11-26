#!/usr/bin/env bash
# Sample shell script for tree-sitter exploration
# Includes various Bash constructs and idioms

# ==================================
# Script Configuration
# ==================================

# Strict mode
set -euo pipefail
IFS=$'\n\t'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

# Constants
readonly VERSION="1.0.0"
readonly CONFIG_FILE="${HOME}/.config/sample/config"
readonly LOG_FILE="/var/log/sample.log"
readonly MAX_RETRIES=3

# Default values
DEBUG=${DEBUG:-false}
VERBOSE=${VERBOSE:-false}

# ==================================
# Functions
# ==================================

# Logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" >&2
}

info() { log "INFO" "$@"; }
warn() { log "WARN" "$@"; }
error() { log "ERROR" "$@"; }
debug() { [[ "$DEBUG" == "true" ]] && log "DEBUG" "$@" || true; }

# Error handling
die() {
    error "$@"
    exit 1
}

# Cleanup function (trap handler)
cleanup() {
    local exit_code=$?
    info "Cleaning up..."
    # Remove temporary files
    rm -rf "${TMP_DIR:-/tmp/sample-$$}" 2>/dev/null || true
    exit "$exit_code"
}

# Set up traps
trap cleanup EXIT
trap 'die "Interrupted"' INT TERM

# Usage function
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] COMMAND [ARGS...]

Sample script demonstrating various Bash constructs.

Commands:
    init        Initialize the environment
    run         Run the main process
    status      Check status
    cleanup     Clean up resources

Options:
    -h, --help      Show this help message
    -v, --version   Show version
    -d, --debug     Enable debug mode
    -V, --verbose   Enable verbose output
    -c, --config    Path to config file
    -n, --dry-run   Dry run mode

Examples:
    $(basename "$0") init
    $(basename "$0") -d run --input file.txt
    $(basename "$0") --config /path/to/config run

EOF
}

# Version function
version() {
    echo "sample.sh version ${VERSION}"
}

# ==================================
# Helper Functions
# ==================================

# Check if command exists
command_exists() {
    command -v "$1" &>/dev/null
}

# Require a command
require_command() {
    local cmd="$1"
    command_exists "$cmd" || die "Required command not found: ${cmd}"
}

# Check if running as root
is_root() {
    [[ $EUID -eq 0 ]]
}

# Retry a command
retry() {
    local max_attempts="$1"
    local delay="$2"
    shift 2
    local cmd=("$@")
    local attempt=1

    while ((attempt <= max_attempts)); do
        if "${cmd[@]}"; then
            return 0
        fi
        warn "Attempt ${attempt}/${max_attempts} failed, retrying in ${delay}s..."
        sleep "$delay"
        ((attempt++))
    done

    error "All ${max_attempts} attempts failed"
    return 1
}

# Read config file
load_config() {
    local config_file="${1:-$CONFIG_FILE}"

    if [[ -f "$config_file" ]]; then
        info "Loading config from ${config_file}"
        # shellcheck source=/dev/null
        source "$config_file"
    else
        warn "Config file not found: ${config_file}"
    fi
}

# Validate input
validate_input() {
    local input="$1"

    [[ -z "$input" ]] && die "Input cannot be empty"
    [[ -f "$input" ]] || die "Input file not found: ${input}"
    [[ -r "$input" ]] || die "Input file not readable: ${input}"
}

# ==================================
# Command Functions
# ==================================

# Initialize command
cmd_init() {
    info "Initializing..."

    # Create directories
    mkdir -p "${HOME}/.config/sample"
    mkdir -p "${HOME}/.local/share/sample"

    # Create default config if not exists
    if [[ ! -f "$CONFIG_FILE" ]]; then
        cat > "$CONFIG_FILE" <<'CONF'
# Sample configuration file
SAMPLE_VAR="default_value"
SAMPLE_ENABLED=true
CONF
        info "Created default config at ${CONFIG_FILE}"
    fi

    info "Initialization complete"
}

# Run command
cmd_run() {
    local input=""
    local output=""

    # Parse subcommand arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -i|--input)
                input="$2"
                shift 2
                ;;
            -o|--output)
                output="$2"
                shift 2
                ;;
            *)
                die "Unknown option: $1"
                ;;
        esac
    done

    # Validate
    [[ -n "$input" ]] || die "Input file required"
    validate_input "$input"

    # Process
    info "Processing ${input}..."

    # Create temp directory
    TMP_DIR=$(mktemp -d)

    # Example: process file line by line
    local line_count=0
    while IFS= read -r line; do
        ((line_count++))
        debug "Processing line ${line_count}: ${line:0:50}..."

        # Example processing with parameter expansion
        local processed="${line^^}"  # Uppercase
        processed="${processed// /_}"  # Replace spaces

        echo "$processed" >> "${TMP_DIR}/processed.txt"
    done < "$input"

    # Output results
    if [[ -n "$output" ]]; then
        mv "${TMP_DIR}/processed.txt" "$output"
        info "Output written to ${output}"
    else
        cat "${TMP_DIR}/processed.txt"
    fi

    info "Processed ${line_count} lines"
}

# Status command
cmd_status() {
    echo "=== System Status ==="
    echo "User: $(whoami)"
    echo "Host: $(hostname)"
    echo "Date: $(date)"
    echo "Uptime: $(uptime -p 2>/dev/null || uptime)"
    echo ""
    echo "=== Script Status ==="
    echo "Version: ${VERSION}"
    echo "Config: ${CONFIG_FILE}"
    echo "Debug: ${DEBUG}"
    echo ""
    echo "=== Dependencies ==="

    local deps=(bash grep sed awk curl jq)
    for dep in "${deps[@]}"; do
        if command_exists "$dep"; then
            local ver
            ver=$("$dep" --version 2>&1 | head -1) || ver="unknown"
            printf "  %-10s %s\n" "$dep:" "installed ($ver)"
        else
            printf "  %-10s %s\n" "$dep:" "NOT FOUND"
        fi
    done
}

# Cleanup command
cmd_cleanup() {
    info "Cleaning up resources..."

    # Remove temp files
    find /tmp -name "sample-*" -mtime +1 -delete 2>/dev/null || true

    # Clear cache
    rm -rf "${HOME}/.cache/sample" 2>/dev/null || true

    info "Cleanup complete"
}

# ==================================
# Demonstration of Bash Features
# ==================================

demo_features() {
    # Arrays
    local -a array=("one" "two" "three")
    local -A assoc_array=(["key1"]="value1" ["key2"]="value2")

    # Array operations
    echo "Array length: ${#array[@]}"
    echo "Array elements: ${array[*]}"
    echo "Assoc value: ${assoc_array[key1]}"

    # Arithmetic
    local x=5 y=3
    local sum=$((x + y))
    local product=$((x * y))
    echo "Sum: ${sum}, Product: ${product}"

    # String operations
    local str="Hello, World!"
    echo "Length: ${#str}"
    echo "Substring: ${str:0:5}"
    echo "Replace: ${str/World/Bash}"
    echo "Uppercase: ${str^^}"
    echo "Lowercase: ${str,,}"

    # Conditionals
    if [[ "$str" == *"World"* ]]; then
        echo "Contains 'World'"
    fi

    # Case statement
    local status="active"
    case "$status" in
        active)
            echo "Status is active"
            ;;
        inactive|disabled)
            echo "Status is not active"
            ;;
        *)
            echo "Unknown status"
            ;;
    esac

    # Loops
    for item in "${array[@]}"; do
        echo "Item: $item"
    done

    for i in {1..5}; do
        echo "Number: $i"
    done

    local counter=0
    while ((counter < 3)); do
        echo "Counter: $counter"
        ((counter++))
    done

    # Process substitution
    diff <(echo "a") <(echo "b") || true

    # Command substitution
    local files
    files=$(ls -la)

    # Here document
    cat <<EOF
This is a here document.
Variable expansion: ${VERSION}
EOF

    # Here string
    grep "pattern" <<< "pattern matching"
}

# ==================================
# Main Entry Point
# ==================================

main() {
    local config_file="$CONFIG_FILE"
    local dry_run=false

    # Parse global options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                usage
                exit 0
                ;;
            -v|--version)
                version
                exit 0
                ;;
            -d|--debug)
                DEBUG=true
                shift
                ;;
            -V|--verbose)
                VERBOSE=true
                shift
                ;;
            -c|--config)
                config_file="$2"
                shift 2
                ;;
            -n|--dry-run)
                dry_run=true
                shift
                ;;
            -*)
                die "Unknown option: $1"
                ;;
            *)
                break
                ;;
        esac
    done

    # Load configuration
    load_config "$config_file"

    # Get command
    local command="${1:-}"
    shift || true

    # Execute command
    case "$command" in
        init)
            cmd_init "$@"
            ;;
        run)
            cmd_run "$@"
            ;;
        status)
            cmd_status "$@"
            ;;
        cleanup)
            cmd_cleanup "$@"
            ;;
        demo)
            demo_features "$@"
            ;;
        "")
            usage
            exit 1
            ;;
        *)
            die "Unknown command: ${command}"
            ;;
    esac
}

# Run main if not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
