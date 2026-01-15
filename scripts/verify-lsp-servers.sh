#!/bin/bash
# verify-lsp-servers.sh - Verify all LSP servers and runtimes are installed
# Portable: Works in devcontainers, CI, bare metal, Docker
# Exit: 0 if all found, 1 if any missing
#
# Checks:
#   - Pyright (Python LSP)
#   - Go toolchain (prerequisite for gopls)
#   - gopls (Go LSP)
#   - typescript-language-server (TypeScript LSP)
#   - .NET SDK (C# Roslyn LSP runtime - SolidLSP auto-downloads the LSP server)

echo "========================================"
echo "Verifying LSP servers and runtimes..."
echo "========================================"
echo ""

MISSING=0

# Check Pyright (Python)
if command -v pyright &> /dev/null; then
    VERSION=$(pyright --version 2>&1 || echo "version check failed")
    echo "✓ Pyright: $(which pyright) ($VERSION)"
else
    echo "✗ Pyright not found - run: scripts/lsp_install/install_pyright.sh"
    MISSING=1
fi

# Check Go (prerequisite for gopls)
if command -v go &> /dev/null; then
    VERSION=$(go version 2>&1 || echo "version check failed")
    echo "✓ Go: $(which go) ($VERSION)"
else
    echo "✗ Go not found - run: scripts/lsp_install/install_go.sh"
    MISSING=1
fi

# Check gopls (Go LSP)
if command -v gopls &> /dev/null; then
    VERSION=$(gopls version 2>&1 | head -1 || echo "version check failed")
    echo "✓ gopls: $(which gopls) ($VERSION)"
else
    echo "✗ gopls not found - run: scripts/lsp_install/install_gopls.sh"
    MISSING=1
fi

# Check typescript-language-server (TypeScript)
if command -v typescript-language-server &> /dev/null; then
    VERSION=$(typescript-language-server --version 2>&1 || echo "version check failed")
    echo "✓ typescript-language-server: $(which typescript-language-server) ($VERSION)"
else
    echo "✗ typescript-language-server not found - run: scripts/lsp_install/install_typescript_ls.sh"
    MISSING=1
fi

# Check .NET SDK (C# Roslyn LSP runtime - SolidLSP auto-downloads the LSP server)
if command -v dotnet &> /dev/null; then
    VERSION=$(dotnet --version 2>&1 || echo "version check failed")
    echo "✓ .NET SDK: $VERSION (Roslyn LSP runtime)"
else
    echo "✗ .NET SDK not found - run: scripts/lsp_install/install_dotnet.sh"
    MISSING=1
fi

echo ""
echo "========================================"

if [ $MISSING -eq 1 ]; then
    echo "Some LSP servers/runtimes are missing."
    echo "Run: scripts/lsp_install/install_all.sh"
    exit 1
fi

echo "All LSP servers and runtimes verified!"
exit 0
