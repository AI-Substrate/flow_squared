# LSP Integration Guide

Enable high-confidence cross-file code analysis using Language Server Protocol (LSP). This guide covers installation, configuration, troubleshooting, and supported languages.

## Overview

LSP integration provides type-aware method call resolution with confidence scores of 1.0, compared to 0.3-0.5 from heuristic-based extraction. This means more accurate answers to questions like "what calls this function?" and better cross-file relationship discovery.

**Benefits:**
- Type-aware call resolution (e.g., `self.auth.validate()` → `AuthHandler.validate()`)
- 40+ languages supported via SolidLSP
- Graceful degradation when LSP servers unavailable
- Actionable error messages with install commands

## Quick Start

```bash
# 1. Install an LSP server (Pyright for Python)
pip install pyright

# 2. Scan your project
fs2 scan --verbose

# 3. Look for LSP output
# "LSP: 18 call edges detected (Python/Pyright)"
```

## Installation

### Python (Pyright)

Pyright is the recommended Python LSP server — fast and accurate.

```bash
# npm (recommended - same version as scripts use)
npm install -g pyright

# pip alternative
pip install pyright

# Verify
pyright --version
```

### TypeScript / JavaScript

```bash
# npm (global)
npm install -g typescript typescript-language-server

# Verify
typescript-language-server --version
```

### Go (gopls)

```bash
# Go 1.18+ required
go install golang.org/x/tools/gopls@latest

# Add to PATH if needed
export PATH="$PATH:$(go env GOPATH)/bin"

# Verify
gopls version
```

### C# (Roslyn)

C# uses Roslyn LSP which is auto-downloaded by fs2 when .NET SDK is available.

```bash
# Linux (Ubuntu/Debian)
wget https://dot.net/v1/dotnet-install.sh -O - | bash -s -- --channel 9.0

# macOS
brew install dotnet

# Windows
# Download from https://dotnet.microsoft.com/download

# Verify
dotnet --version  # Should be 9.0+
```

**Note**: Unlike other languages, C# doesn't require a separate LSP server install. fs2 uses `Microsoft.CodeAnalysis.LanguageServer` which is downloaded automatically from NuGet on first use.

## Using LSP

### Default Behavior

LSP is enabled by default when servers are installed. fs2 auto-detects available servers based on file extensions.

```bash
# Normal scan (LSP enabled if available)
fs2 scan

# Verbose output shows LSP status
fs2 scan --verbose
```

### Disable LSP

```bash
# Disable LSP for faster scanning (text extraction only)
fs2 scan --no-lsp
```

### Verify LSP Status

```bash
# Verbose mode shows LSP detection
fs2 scan --verbose

# Expected output for Python project:
# Discovering files...
# LSP: Initializing Python/Pyright...
# Parsing 42 files...
# LSP: 18 call edges detected
# ✓ Scanned 42 files, created 187 nodes
```

## Configuration

LSP settings in `.fs2/config.yaml`:

```yaml
lsp:
  # Timeout for LSP operations (seconds)
  timeout_seconds: 30
  
  # Enable debug logging for LSP
  enable_logging: false
```

### Environment Variables

```bash
# Override timeout
export FS2_LSP__TIMEOUT_SECONDS=60

# Enable LSP debug logging
export FS2_LSP__ENABLE_LOGGING=true
```

## Troubleshooting

### "LSP server not found" Error

**Symptom**: Error message with install command suggestion.

```
LspServerNotFoundError: 'pyright' not found. Install with:
  pip install pyright
```

**Solution**: Install the recommended LSP server for your language.

### "LSP timeout" Error

**Symptom**: Scan takes too long, times out.

```
LspTimeoutError: Operation 'get_references' timed out after 30s
```

**Solutions**:
1. Increase timeout: `FS2_LSP__TIMEOUT_SECONDS=60`
2. Exclude large generated files from scan
3. Use `--no-lsp` for initial scan, then enable LSP

### "LSP server crashed" Error

**Symptom**: Server exits unexpectedly.

```
LspServerCrashError: pyright exited with code 1
```

**Solutions**:
1. Check LSP server logs: `FS2_LSP__ENABLE_LOGGING=true`
2. Verify project has valid config (pyproject.toml, tsconfig.json, etc.)
3. Update LSP server to latest version

### No LSP Edges Detected

**Symptom**: Scan completes but reports 0 LSP edges.

**Possible causes**:
1. **No LSP servers installed** — Check `which pyright` or equivalent
2. **Project not recognized** — Ensure marker file exists (pyproject.toml, tsconfig.json, go.mod)
3. **No cross-file calls** — Simple projects may not have resolvable calls
4. **Language not supported** — Check supported languages below

### C# Roslyn Issues

**Symptom**: C# LSP fails to start.

**Common fixes**:
1. Ensure .NET SDK 9+ is installed: `dotnet --version`
2. Set DOTNET_ROOT if installed to non-standard location:
   ```bash
   export DOTNET_ROOT="$HOME/.dotnet"
   export PATH="$PATH:$DOTNET_ROOT"
   ```
3. First scan may be slow (downloading Roslyn from NuGet)

## Supported Languages

fs2 uses [SolidLSP](https://github.com/oraios-ai/serena) which supports 40+ languages. Languages are auto-detected from file extensions.

### Fully Tested

These languages have integration tests and are verified working:

| Language | LSP Server | Install Command |
|----------|------------|-----------------|
| Python | Pyright | `pip install pyright` |
| TypeScript | typescript-language-server | `npm install -g typescript typescript-language-server` |
| Go | gopls | `go install golang.org/x/tools/gopls@latest` |
| C# | Roslyn | `.NET SDK 9+` (auto-downloaded) |

### Community Supported

These languages are supported by SolidLSP but not tested by fs2. They should work if the LSP server is installed:

| Language | LSP Server | Notes |
|----------|------------|-------|
| Java | Eclipse JDT | Requires JDK |
| Rust | rust-analyzer | Install via rustup |
| Ruby | Solargraph | `gem install solargraph` |
| PHP | Intelephense | `npm install -g intelephense` |
| Kotlin | kotlin-language-server | Requires JDK |
| Swift | sourcekit-lsp | Included with Xcode |
| Scala | Metals | Install via coursier |
| Lua | lua-language-server | Available via package managers |
| Elixir | elixir-ls | `mix local.hex` |
| Haskell | haskell-language-server | Install via ghcup |
| OCaml | ocaml-lsp | Install via opam |
| Zig | zls | Available via package managers |
| Vue | volar | `npm install -g @vue/language-server` |
| Svelte | svelte-language-server | `npm install -g svelte-language-server` |

### File Extension Detection

fs2 detects languages from file extensions:

```
.py        → Python (Pyright)
.ts, .tsx  → TypeScript
.js, .jsx  → JavaScript (TypeScript server)
.go        → Go (gopls)
.cs        → C# (Roslyn)
.java      → Java (Eclipse JDT)
.rs        → Rust (rust-analyzer)
.rb        → Ruby (Solargraph)
.php       → PHP (Intelephense)
```

## How It Works

1. **File Discovery**: fs2 scans your project for source files
2. **Project Root Detection**: Finds marker files (pyproject.toml, tsconfig.json, etc.)
3. **LSP Initialization**: Starts appropriate LSP server for detected language
4. **Call Site Resolution**: For each function call, queries LSP for definition location
5. **Edge Creation**: Creates `CodeEdge` with confidence 1.0 linking caller → callee
6. **Graceful Degradation**: If LSP fails, falls back to text-based extraction

### Confidence Scores

| Source | Confidence | Example |
|--------|------------|---------|
| LSP call resolution | 1.0 | `auth.validate()` → `AuthHandler.validate()` |
| Explicit node ID in docs | 1.0 | `method:src/auth.py:Auth.login` |
| Backtick filename | 0.5 | `` `auth.py` `` |
| Bare filename | 0.4 | `auth.py` |
| Heuristic (no LSP) | 0.3-0.5 | Pattern matching |

## Performance

LSP adds overhead to scanning but improves relationship accuracy:

| Project Size | Without LSP | With LSP | Edge Quality |
|--------------|-------------|----------|--------------|
| Small (<50 files) | ~2s | ~5s | Much better |
| Medium (50-200 files) | ~10s | ~30s | Much better |
| Large (200+ files) | ~30s | ~2min | Much better |

**Tips for large projects**:
1. First scan without LSP for quick iteration: `fs2 scan --no-lsp`
2. Enable LSP for final relationship extraction: `fs2 scan`
3. Increase timeout for very large projects: `FS2_LSP__TIMEOUT_SECONDS=120`

## See Also

- [Scanning Guide](scanning.md) — General scanning configuration
- [Configuration Guide](configuration-guide.md) — All config options
- [Developer: LSP Adapter Architecture](../dev/lsp-adapter-architecture.md) — For contributors
