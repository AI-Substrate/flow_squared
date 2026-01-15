# Phase 0: Environment Preparation - Execution Log

**Started**: 2026-01-14
**Completed**: 2026-01-14
**Status**: ✅ Complete

---

## Task T001: Write verification script (TDD)
**Started**: 2026-01-14
**Status**: ✅ Complete

### What I Did
Created `/scripts/verify-lsp-servers.sh` that checks all LSP servers and runtimes are installed.
TDD approach: Script runs but fails as expected (RED state) - servers aren't installed yet.

### Evidence
```
========================================
Verifying LSP servers and runtimes...
========================================

✗ Pyright not found - run: scripts/lsp_install/install_pyright.sh
✗ Go not found - run: scripts/lsp_install/install_go.sh
✗ gopls not found - run: scripts/lsp_install/install_gopls.sh
✗ typescript-language-server not found - run: scripts/lsp_install/install_typescript_ls.sh
✗ .NET SDK not found - run: scripts/lsp_install/install_dotnet.sh

========================================
Some LSP servers/runtimes are missing.
Run: scripts/lsp_install/install_all.sh
```

Exit code 1 (expected - TDD RED state)

### Files Changed
- `/workspaces/flow_squared/scripts/verify-lsp-servers.sh` — Created verification script

**Completed**: 2026-01-14

---

## Task T002-T006: Create install scripts
**Started**: 2026-01-14
**Status**: ✅ Complete

### What I Did
Created all 5 individual install scripts in `/scripts/lsp_install/`:

1. **install_pyright.sh** (T002)
   - Installs Pyright via `npm install -g pyright`
   - Checks for npm prerequisite
   - Verifies installation

2. **install_go.sh** (T003)
   - Downloads and installs Go toolchain from go.dev
   - Auto-detects architecture (amd64/arm64)
   - Pins to Go 1.22.0
   - Idempotent (skips if Go already installed)

3. **install_gopls.sh** (T004)
   - Calls install_go.sh first (ensures dependency)
   - Installs gopls via `go install golang.org/x/tools/gopls@latest`
   - Sets up Go paths

4. **install_typescript_ls.sh** (T005)
   - Installs typescript and typescript-language-server via npm
   - Checks for npm prerequisite

5. **install_dotnet.sh** (T006)
   - Uses Microsoft's official install script
   - Installs LTS channel .NET SDK
   - Idempotent (skips if .NET already installed)

### Evidence
```bash
$ ls -la /workspaces/flow_squared/scripts/lsp_install/
install_dotnet.sh
install_go.sh
install_gopls.sh
install_pyright.sh
install_typescript_ls.sh
```

All scripts are executable and follow portable pattern (no devcontainer-specific code).

### Files Changed
- `/workspaces/flow_squared/scripts/lsp_install/install_pyright.sh` — Created
- `/workspaces/flow_squared/scripts/lsp_install/install_go.sh` — Created
- `/workspaces/flow_squared/scripts/lsp_install/install_gopls.sh` — Created
- `/workspaces/flow_squared/scripts/lsp_install/install_typescript_ls.sh` — Created
- `/workspaces/flow_squared/scripts/lsp_install/install_dotnet.sh` — Created

**Completed**: 2026-01-14

---

## Task T007: Create install_all.sh orchestrator
**Started**: 2026-01-14
**Status**: ✅ Complete

### What I Did
Created `/scripts/lsp_install/install_all.sh` that orchestrates all individual install scripts.

Order of operations:
1. Install Go toolchain (prerequisite for gopls)
2. Install .NET SDK (runtime for Roslyn LSP)
3. Install Pyright (Python LSP)
4. Install typescript-language-server (TypeScript LSP)
5. Install gopls (Go LSP - requires Go)

### Evidence
```bash
$ ls -la /workspaces/flow_squared/scripts/lsp_install/
install_all.sh
install_dotnet.sh
install_go.sh
install_gopls.sh
install_pyright.sh
install_typescript_ls.sh
```

Script sets up PATH for newly installed tools between runtime and LSP installs.

### Files Changed
- `/workspaces/flow_squared/scripts/lsp_install/install_all.sh` — Created orchestrator

**Completed**: 2026-01-14

---

## Task T008: Update post-install.sh
**Started**: 2026-01-14
**Status**: ✅ Complete

### What I Did
Updated `.devcontainer/post-install.sh` to:
1. Call `/workspaces/flow_squared/scripts/lsp_install/install_all.sh` to install LSP servers
2. Update PATH export to include Go and .NET paths

### Evidence
```bash
# Added to post-install.sh:
# Install LSP servers and runtimes for fs2 development
echo "Installing LSP servers..."
/workspaces/flow_squared/scripts/lsp_install/install_all.sh

# Updated PATH:
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/usr/local/go/bin:$HOME/go/bin:$HOME/.dotnet:$PATH"
export GOPATH="$HOME/go"
export DOTNET_ROOT="$HOME/.dotnet"
```

### Files Changed
- `/workspaces/flow_squared/.devcontainer/post-install.sh` — Added LSP install call and PATH updates

**Completed**: 2026-01-14

---

## Task T009: Run install_all.sh and verify (TDD GREEN)
**Started**: 2026-01-14
**Status**: ✅ Complete

### What I Did
1. Ran `/workspaces/flow_squared/scripts/lsp_install/install_all.sh` to install all LSP servers
2. Ran verification script to confirm TDD GREEN state (all tests pass)

### Installation Results
```
--- Installing Go toolchain ---
✓ Go installed: go version go1.22.0 linux/arm64

--- Installing .NET SDK ---
✓ .NET SDK installed: 10.0.102

--- Installing Pyright (Python LSP) ---
✓ Pyright installed: pyright 1.1.408

--- Installing TypeScript Language Server ---
✓ typescript-language-server installed: 5.1.3

--- Installing gopls (Go LSP) ---
✓ gopls installed: golang.org/x/tools/gopls v0.21.0
```

### Verification Results (TDD GREEN)
```
========================================
Verifying LSP servers and runtimes...
========================================

✓ Pyright: /home/vscode/.npm-global/bin/pyright (pyright 1.1.408)
✓ Go: /usr/local/go/bin/go (go version go1.22.0 linux/arm64)
✓ gopls: /home/vscode/go/bin/gopls (golang.org/x/tools/gopls v0.21.0)
✓ typescript-language-server: /home/vscode/.npm-global/bin/typescript-language-server (5.1.3)
✓ .NET SDK: 10.0.102 (Roslyn LSP runtime)

========================================
All LSP servers and runtimes verified!
```

Exit code 0 (SUCCESS - TDD GREEN state achieved!)

### TDD Summary
- **RED**: Verification script failed (all 5 checks missing)
- **GREEN**: After install_all.sh, all 5 checks pass

### Files Changed
None (verification only)

**Completed**: 2026-01-14

---

## Phase Summary

### Deliverables

| Deliverable | Path | Status |
|-------------|------|--------|
| Verification script | `/scripts/verify-lsp-servers.sh` | ✅ |
| install_pyright.sh | `/scripts/lsp_install/install_pyright.sh` | ✅ |
| install_go.sh | `/scripts/lsp_install/install_go.sh` | ✅ |
| install_gopls.sh | `/scripts/lsp_install/install_gopls.sh` | ✅ |
| install_typescript_ls.sh | `/scripts/lsp_install/install_typescript_ls.sh` | ✅ |
| install_dotnet.sh | `/scripts/lsp_install/install_dotnet.sh` | ✅ |
| install_all.sh | `/scripts/lsp_install/install_all.sh` | ✅ |
| post-install.sh update | `/.devcontainer/post-install.sh` | ✅ |

### Installed Versions

| Component | Version | Path |
|-----------|---------|------|
| Go | 1.22.0 | /usr/local/go/bin/go |
| .NET SDK | 10.0.102 | ~/.dotnet/dotnet |
| Pyright | 1.1.408 | ~/.npm-global/bin/pyright |
| typescript-language-server | 5.1.3 | ~/.npm-global/bin/typescript-language-server |
| gopls | v0.21.0 | ~/go/bin/gopls |

### Acceptance Criteria Met

- [x] All 4 LSP servers available via `which` command
- [x] Verification script passes in devcontainer
- [x] Servers persist across container rebuilds (via post-install.sh)
- [ ] CI workflow can validate server availability (out of scope)

### Suggested Commit Message

```
feat: Add LSP server installation scripts for devcontainer

- Create portable install scripts in scripts/lsp_install/
- Install Pyright, gopls, typescript-language-server, .NET SDK
- Add verification script to check all LSP servers
- Integrate with devcontainer post-install.sh

This enables Phase 0 of 025-lsp-research plan.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

---

## End of Phase 0 Execution Log
