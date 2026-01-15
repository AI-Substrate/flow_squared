#!/bin/bash
# install_pyright.sh - Install Pyright (Python LSP)
# Portable: Works in devcontainers, CI, bare metal, Docker
# Requires: Node.js/npm in PATH
set -e

echo "Installing Pyright..."

# Check prerequisite
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm not found. Install Node.js first."
    exit 1
fi

# Install globally
npm install -g pyright

# Verify
if command -v pyright &> /dev/null; then
    VERSION=$(pyright --version 2>&1 || echo "installed")
    echo "✓ Pyright installed: $(which pyright) ($VERSION)"
else
    echo "ERROR: Pyright installation failed"
    exit 1
fi
