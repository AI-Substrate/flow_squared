#!/usr/bin/env bash
#
# fs2-scan-on-change.sh - Helper script for fs2-watch.sh
# Shows which files changed and runs fs2 scan
#
# Called by watchexec with environment variables (--emit-events-to=environment):
#   WATCHEXEC_COMMON_PATH - prefix for all paths
#   WATCHEXEC_WRITTEN_PATH, WATCHEXEC_CREATED_PATH, etc.
#

set -euo pipefail

# Colors
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Common path prefix (may be empty) - add trailing slash if present
common="${WATCHEXEC_COMMON_PATH:-}"
if [[ -n "$common" && "${common: -1}" != "/" ]]; then
    common="${common}/"
fi

echo ""
echo -e "${BLUE}[INFO]${NC} Change detected:"

# Map of env var to display label
declare -A event_labels=(
    [WATCHEXEC_WRITTEN_PATH]="modified"
    [WATCHEXEC_CREATED_PATH]="created"
    [WATCHEXEC_REMOVED_PATH]="removed"
    [WATCHEXEC_RENAMED_PATH]="renamed"
    [WATCHEXEC_META_CHANGED_PATH]="meta"
    [WATCHEXEC_OTHERWISE_CHANGED_PATH]="other"
)

found_any=false

for var in "${!event_labels[@]}"; do
    val="${!var:-}"
    if [[ -n "$val" ]]; then
        found_any=true
        label="${event_labels[$var]}"
        # Show each file (colon-separated list)
        echo "$val" | tr ':' '\n' | while read -r file; do
            if [[ -n "$file" ]]; then
                # Prepend common path if present
                full_path="${common}${file}"
                echo -e "       ${YELLOW}[$label]${NC} $full_path"
            fi
        done
    fi
done

if [[ "$found_any" == "false" ]]; then
    echo "       (no file details available)"
fi

echo ""

# Run fs2 scan with any passed arguments
exec "$@"
