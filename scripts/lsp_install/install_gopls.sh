#!/bin/bash
# install_gopls.sh - Install gopls (Go LSP)
# Portable: Works in devcontainers, CI, bare metal, Docker
# Automatically installs Go if not present
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure Go is installed first
"$SCRIPT_DIR/install_go.sh"

# Source Go paths (in case just installed)
export PATH=$PATH:/usr/local/go/bin
export GOPATH=${GOPATH:-$HOME/go}
export PATH=$PATH:$GOPATH/bin

echo "Installing gopls..."
go install golang.org/x/tools/gopls@latest

# Verify
if command -v gopls &> /dev/null; then
    VERSION=$(gopls version 2>&1 | head -1 || echo "installed")
    echo "✓ gopls installed: $(which gopls) ($VERSION)"
elif [ -f "$GOPATH/bin/gopls" ]; then
    VERSION=$("$GOPATH/bin/gopls" version 2>&1 | head -1 || echo "installed")
    echo "✓ gopls installed: $GOPATH/bin/gopls ($VERSION)"
else
    echo "ERROR: gopls installation failed"
    exit 1
fi
