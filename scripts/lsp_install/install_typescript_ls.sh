#!/bin/bash
# install_typescript_ls.sh - Install TypeScript Language Server
# Portable: Works in devcontainers, CI, bare metal, Docker
# Requires: Node.js/npm in PATH
set -e

echo "Installing TypeScript Language Server..."

# Check prerequisite
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm not found. Install Node.js first."
    exit 1
fi

# Install globally (both typescript and the language server)
npm install -g typescript typescript-language-server

# Verify
if command -v typescript-language-server &> /dev/null; then
    VERSION=$(typescript-language-server --version 2>&1 || echo "installed")
    echo "✓ typescript-language-server installed: $(which typescript-language-server) ($VERSION)"
else
    echo "ERROR: typescript-language-server installation failed"
    exit 1
fi
