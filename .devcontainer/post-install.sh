#!/bin/bash
set -e

echo "Running post-install script..."

# Install Python dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip3 install --user -r requirements.txt
fi

# Install dev dependencies if requirements-dev.txt exists
if [ -f "requirements-dev.txt" ]; then
    echo "Installing dev dependencies..."
    pip3 install --user -r requirements-dev.txt
fi



# Add any additional post-install commands here
uvx --from git+https://github.com/jakkaj/tools jk-tools-setup

echo "Installing wormhole..."
npx --yes github:AI-Substrate/wormhole --help

echo "Pulling flowspace image"

flowspace update

claude mcp add flowspace -- flowspace mcp
claude mcp add wormhole -- npx github:AI-Substrate/wormhole mcp --workspace .

echo "Post-install script completed!"
