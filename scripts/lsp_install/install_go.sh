#!/bin/bash
# install_go.sh - Install Go toolchain (prerequisite for gopls)
# Portable: Works in devcontainers, CI, bare metal, Docker
set -e

# Skip if Go is already installed
if command -v go &> /dev/null; then
    echo "✓ Go already installed: $(go version)"
    exit 0
fi

echo "Installing Go..."

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64) GOARCH="amd64" ;;
    aarch64|arm64) GOARCH="arm64" ;;
    *) echo "ERROR: Unsupported architecture: $ARCH"; exit 1 ;;
esac

# Detect OS
OS=$(uname -s | tr '[:upper:]' '[:lower:]')

# Pin to known good version
GO_VERSION="1.22.0"
TARBALL="go${GO_VERSION}.${OS}-${GOARCH}.tar.gz"

echo "Downloading Go $GO_VERSION for ${OS}/${GOARCH}..."
curl -fsSL "https://go.dev/dl/${TARBALL}" -o "/tmp/${TARBALL}"

echo "Installing to /usr/local/go..."
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf "/tmp/${TARBALL}"
rm "/tmp/${TARBALL}"

# Add to PATH for current session
export PATH=$PATH:/usr/local/go/bin
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin

# Create GOPATH directory
mkdir -p "$HOME/go/bin"

# Verify
if command -v /usr/local/go/bin/go &> /dev/null; then
    echo "✓ Go installed: $(/usr/local/go/bin/go version)"
    echo ""
    echo "NOTE: Add to your shell profile for persistent PATH:"
    echo '  export PATH=$PATH:/usr/local/go/bin'
    echo '  export GOPATH=$HOME/go'
    echo '  export PATH=$PATH:$GOPATH/bin'
else
    echo "ERROR: Go installation failed"
    exit 1
fi
