#!/bin/bash
set -e

echo "Running post-install script..."

# Install Python dependencies via uv (includes ruff and all dev deps from pyproject.toml)
if [ -f "pyproject.toml" ]; then
    echo "Installing Python dependencies via uv sync..."
    uv sync
fi

# Legacy: Install Python dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip3 install --user -r requirements.txt
fi

# Legacy: Install dev dependencies if requirements-dev.txt exists
if [ -f "requirements-dev.txt" ]; then
    echo "Installing dev dependencies..."
    pip3 install --user -r requirements-dev.txt
fi



# Install LSP servers and runtimes for fs2 development
echo "Installing LSP servers..."
/workspaces/flow_squared/scripts/lsp_install/install_all.sh

# Add any additional post-install commands here
uvx --from git+https://github.com/jakkaj/tools jk-tools-setup

echo "Installing wormhole..."
npx --yes github:AI-Substrate/wormhole --help

echo "Pulling flowspace image"

flowspace update

# Source updated PATH to make newly installed tools available
# Includes: npm globals, local bin, Go, and .NET
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/usr/local/go/bin:$HOME/go/bin:$HOME/.dotnet:$PATH"
export GOPATH="$HOME/go"
export DOTNET_ROOT="$HOME/.dotnet"

claude mcp add flowspace -- uv run fs2 mcp
claude mcp add wormhole -- npx github:AI-Substrate/wormhole mcp --workspace .

echo "Post-install script completed!"
