#!/bin/bash
# install_all.sh - Install all LSP servers and runtimes
# Portable: Works in devcontainers, CI, bare metal, Docker
#
# Installs:
#   - Go toolchain (prerequisite for gopls)
#   - .NET SDK (runtime for Roslyn LSP)
#   - Pyright (Python LSP)
#   - typescript-language-server (TypeScript LSP)
#   - gopls (Go LSP)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================"
echo "Installing all LSP servers and runtimes"
echo "========================================"
echo ""

# Install runtimes first (prerequisites for LSP servers)
echo "--- Installing Go toolchain ---"
"$SCRIPT_DIR/install_go.sh"
echo ""

echo "--- Installing .NET SDK ---"
"$SCRIPT_DIR/install_dotnet.sh"
echo ""

# Source paths for newly installed tools
export PATH=$PATH:/usr/local/go/bin
export GOPATH=${GOPATH:-$HOME/go}
export PATH=$PATH:$GOPATH/bin
export DOTNET_ROOT="$HOME/.dotnet"
export PATH="$PATH:$DOTNET_ROOT:$DOTNET_ROOT/tools"

# Install LSP servers
echo "--- Installing Pyright (Python LSP) ---"
"$SCRIPT_DIR/install_pyright.sh"
echo ""

echo "--- Installing TypeScript Language Server ---"
"$SCRIPT_DIR/install_typescript_ls.sh"
echo ""

echo "--- Installing gopls (Go LSP) ---"
"$SCRIPT_DIR/install_gopls.sh"
echo ""

echo "========================================"
echo "All LSP servers and runtimes installed!"
echo ""
echo "Run to verify: scripts/verify-lsp-servers.sh"
echo "========================================"
