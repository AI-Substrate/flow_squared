#!/bin/bash
# install_dotnet.sh - Install .NET SDK (runtime for Roslyn LSP)
# Portable: Works in devcontainers, CI, bare metal, Docker
# SolidLSP auto-downloads Microsoft.CodeAnalysis.LanguageServer at runtime
set -e

# Skip if .NET SDK is already installed
if command -v dotnet &> /dev/null; then
    VERSION=$(dotnet --version 2>&1 || echo "unknown")
    echo "✓ .NET SDK already installed: $VERSION"
    exit 0
fi

echo "Installing .NET SDK..."

# Use Microsoft's official install script
curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh
chmod +x /tmp/dotnet-install.sh
/tmp/dotnet-install.sh --channel LTS
rm /tmp/dotnet-install.sh

# Add to PATH for current session
export DOTNET_ROOT="$HOME/.dotnet"
export PATH="$PATH:$DOTNET_ROOT:$DOTNET_ROOT/tools"

# Verify
if [ -f "$DOTNET_ROOT/dotnet" ]; then
    VERSION=$("$DOTNET_ROOT/dotnet" --version 2>&1 || echo "installed")
    echo "✓ .NET SDK installed: $DOTNET_ROOT/dotnet ($VERSION)"
    echo ""
    echo "NOTE: Add to your shell profile for persistent PATH:"
    echo '  export DOTNET_ROOT="$HOME/.dotnet"'
    echo '  export PATH="$PATH:$DOTNET_ROOT:$DOTNET_ROOT/tools"'
else
    echo "ERROR: .NET SDK installation failed"
    exit 1
fi
