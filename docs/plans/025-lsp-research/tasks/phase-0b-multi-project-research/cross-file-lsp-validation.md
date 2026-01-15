# Cross-File LSP Reference Validation Research

**Date**: 2026-01-15
**Phase**: Phase 0b: Multi-Project Research (Subtask 001)
**Status**: COMPLETE
**Validation**: 4/4 languages passing

---

## Quick Start for Future Phases

**If you're starting Phase 1 (Vendoring) or Phase 3 (Integration) with no prior context, read this first.**

### TL;DR

SolidLSP works for all 4 languages. The integration is simple:

```python
from solidlsp import SolidLanguageServer
from solidlsp.ls_config import Language, LanguageServerConfig

config = LanguageServerConfig(code_language=Language.PYTHON)
ls = SolidLanguageServer.create(config, "/path/to/repo")
ls.start()
try:
    refs = ls.request_references("file.py", line=9, column=8)  # 0-indexed!
    for ref in refs:
        print(ref["relativePath"])  # e.g., "other_file.py"
finally:
    ls.stop()
```

### Critical Gotchas (Must Know)

| Language | Gotcha | Solution |
|----------|--------|----------|
| Python | Needs `pyright` pip package | Already added to fs2's pyproject.toml |
| TypeScript | Won't find refs without opening files first | Call `ls.open_file("referencing_file.tsx")` before query |
| Go | Needs gopls on PATH | Run `scripts/lsp_install/install_gopls.sh` |
| C# | Needs .NET SDK (not runtime) + our fixes | Fixes already in `scratch/serena/src/solidlsp/` |

### Files You'll Need

| Purpose | Location |
|---------|----------|
| SolidLSP source (to vendor) | `scratch/serena/src/solidlsp/` |
| C# fixes (MUST preserve) | `scratch/serena/src/solidlsp/language_servers/csharp_language_server.py` |
| Test fixtures | `tests/fixtures/lsp/{python,typescript,go,csharp}_*` |
| Validation script | `scripts/lsp/validate_solidlsp_cross_file.py` |

### For Phase 1 Vendoring

Copy `scratch/serena/src/solidlsp/` to `src/fs2/vendor/solidlsp/`. **Preserve all C# fixes** (lines 237-242, 294-298, 444-448 in `csharp_language_server.py`).

### For Phase 3 Integration

The adapter will be thin - just wrap these SolidLSP calls:
- `SolidLanguageServer.create(config, repo_path)`
- `ls.start()` / `ls.stop()`
- `ls.request_references(file, line, column)` → returns `list[Location]`
- `ls.open_file(file)` → context manager (needed for TypeScript)

---

## Executive Summary

This document captures the results of validating SolidLSP's cross-file reference resolution capabilities. SolidLSP successfully resolves cross-file method/function calls for **all 4 languages: Python, TypeScript, Go, and C#**.

**Recommendation**: Proceed with SolidLSP vendoring. The 4/4 pass rate validates the core capability we need.

---

## Validation Results

| Language | LSP Server | Status | Cross-File References Found |
|----------|-----------|--------|---------------------------|
| Python | Pyright | ✅ PASS | `handler.py:12` calling `User.validate()` |
| TypeScript | typescript-language-server | ✅ PASS | `index.tsx:1,9` calling `formatDate()` |
| Go | gopls | ✅ PASS | `main.go:10` calling `auth.Validate()` |
| C# | Roslyn (Microsoft.CodeAnalysis.LanguageServer) | ✅ PASS | `Program.cs:5` calling `user.Validate()` |

---

## SolidLSP API Findings

### `SolidLanguageServer` Lifecycle

```python
from solidlsp import SolidLanguageServer
from solidlsp.ls_config import Language, LanguageServerConfig

# Create and start
config = LanguageServerConfig(code_language=Language.PYTHON)
ls = SolidLanguageServer.create(config, str(repo_path.absolute()))
ls.start()

try:
    # Use the server
    refs = ls.request_references("path/to/file.py", line=9, column=8)
finally:
    ls.stop()
```

### Key Methods

| Method | Signature | Notes |
|--------|-----------|-------|
| `start()` | `def start(self) -> SolidLanguageServer` | Starts LSP subprocess |
| `stop()` | `def stop(self, timeout=2.0) -> None` | Graceful shutdown |
| `request_references()` | `def request_references(relative_path, line, column) -> list[Location]` | **0-indexed line/column** |
| `open_file()` | `def open_file(relative_path) -> ContextManager` | Opens file in LSP |

### `Location` Response Type

```python
class Location(TypedDict):
    uri: str           # file:// URI
    range: Range       # {start: {line, character}, end: {line, character}}
    absolutePath: str  # Full filesystem path
    relativePath: str | None  # Path relative to repo root
```

---

## Language-Specific Findings

### Python (Pyright)

**Prerequisites**:
- `pyright` pip package installed
- SolidLSP spawns: `python -m pyright.langserver --stdio`

**fs2 Integration** (DONE):
```toml
# In /workspaces/flow_squared/pyproject.toml dependencies array:
"pyright>=1.1.400",  # Python LSP server for SolidLSP integration
```

**Behavior**:
- Indexes entire project on startup
- No need to open referencing files first
- SolidLSP handles internal wait times (typically 2 seconds for cross-file references)

**Gotcha**: npm `pyright` package is different from pip `pyright`. SolidLSP requires the **pip version** because it spawns `python -m pyright.langserver`. The npm version provides a different binary that doesn't work with SolidLSP's Python language server implementation.

### TypeScript

**Prerequisites**:
- Node.js and npm installed
- SolidLSP auto-downloads `typescript` and `typescript-language-server` to `~/.solidlsp/`

**Behavior**:
- Does NOT index all files on startup (unlike Python/Go/C#)
- **Must open referencing files** before querying definition file
- SolidLSP handles internal wait times automatically (no explicit sleep needed)

**Critical Pattern** (REQUIRED for TypeScript):
```python
# Open referencing file FIRST to trigger indexing
# This is REQUIRED for TypeScript - without it, you get 0 references
with ls.open_file("packages/client/index.tsx"):
    pass  # Just opening triggers the LSP to index this file

# Then query the definition file
refs = ls.request_references("packages/client/utils.ts", line=4, column=16)
# Now returns references from index.tsx
```

**Why This Is Needed**: TypeScript LSP uses a lazy indexing model. It only indexes files that are explicitly opened. Python, Go, and C# LSPs index the entire project on startup, but TypeScript does not.

### Go (gopls)

**Prerequisites**:
- Go toolchain installed (`go version`)
- gopls installed (`go install golang.org/x/tools/gopls@latest`)
- Both must be on PATH

**Behavior**:
- Indexes entire project on startup (like Python)
- Respects go.mod module paths
- No need to open referencing files first
- Wait time: 2 seconds (default)

**Gotcha**: Import paths must match go.mod module name exactly:
```go
// go.mod: module github.com/example/goproject
import "github.com/example/goproject/internal/auth"  // Correct
import "project/internal/auth"  // WRONG - won't resolve
```

### C# (Roslyn)

**Prerequisites**:
- .NET 9+ SDK installed (includes MSBuild)
- SolidLSP auto-downloads Roslyn LSP to `~/.solidlsp/`

**Behavior**:
- Roslyn LSP requires MSBuild (from SDK) to load .csproj files
- Must use system .NET SDK, not standalone runtime
- Indexes entire project on startup
- Wait time: 2 seconds (default)

**Fix Applied**: Updated `CSharpLanguageServer` to:
1. Accept .NET 9+ (was hardcoded to .NET 9 only)
2. Pass `DOTNET_ROOT` env var to LSP subprocess for MSBuild discovery
3. Prefer system SDK over auto-downloaded runtime (which lacks MSBuild)

```python
# In csharp_language_server.py __init__:
dotnet_root = os.path.dirname(dotnet_path)
env = {
    "DOTNET_ROOT": dotnet_root,
    "DOTNET_HOST_PATH": dotnet_path,
    "DOTNET_MSBUILD_SDK_RESOLVER_CLI_DIR": dotnet_root,
}
```

---

## SolidLSP Dependency Model

SolidLSP has a **mixed dependency model**:

| Component | Auto-Downloaded? | User Must Install |
|-----------|-----------------|-------------------|
| Roslyn LSP (.NET) | ✅ Yes | Nothing |
| TypeScript + TS LSP | ✅ Yes (npm) | Node.js, npm |
| Pyright | ❌ No | `pip install pyright` |
| gopls | ❌ No | Go toolchain + gopls |

**RuntimeDependency System**: Located at `solidlsp/language_servers/common.py`
- Handles auto-downloads for C#, TypeScript, Bash, etc.
- Not used for Python or Go

---

## Fixture Ground Truth

These fixtures serve as ground truth for Phase 3 `SolidLspAdapter` testing.

### Python Fixture
```
tests/fixtures/lsp/python_multi_project/
├── pyproject.toml
└── packages/auth/
    ├── __init__.py
    ├── models.py      # User.validate() at line 10 (0-indexed: 9)
    └── handler.py     # Calls user.validate() at line 12
```

### TypeScript Fixture
```
tests/fixtures/lsp/typescript_multi_project/
├── tsconfig.json
├── package.json
└── packages/client/
    ├── tsconfig.json
    ├── utils.ts       # formatDate() at line 5 (0-indexed: 4)
    └── index.tsx      # Calls formatDate() at lines 1, 9
```

### Go Fixture
```
tests/fixtures/lsp/go_project/
├── go.mod             # module github.com/example/goproject
├── internal/auth/
│   └── auth.go        # Validate() at line 6 (0-indexed: 5)
└── cmd/server/
    └── main.go        # Calls auth.Validate() at line 10
```

### C# Fixture
```
tests/fixtures/lsp/csharp_multi_project/
├── Solution.sln
└── src/Api/
    ├── Api.csproj
    ├── Models.cs      # User.Validate() at line 11 (0-indexed: 10)
    └── Program.cs     # Calls user.Validate() at line 5
```

---

## Recommendations for Phase 1+

### For Vendoring (Phase 1)
1. **Proceed with vendoring** - 4/4 languages validated
2. Keep RuntimeDependency system for auto-downloads
3. Document Python/Go as requiring pre-installation
4. Keep C# fixes (DOTNET_ROOT env, .NET 9+ version check)

### For fs2 Integration (Phase 3)
1. Add `pyright` to fs2 dependencies (done: pyproject.toml)
2. Document TypeScript's "open both files" requirement
3. Consider adding helper method: `ensure_files_indexed()`
4. C# now works - requires .NET SDK (not just runtime)

### For Devcontainer
1. Run `scripts/lsp_install/install_all.sh` in postCreateCommand
2. Add PATH exports for Go and .NET to shell profile
3. Consider adding as devcontainer features instead

---

## Appendix: Validation Script

**Location**: `scripts/lsp/validate_solidlsp_cross_file.py`

**Usage**:
```bash
# Ensure PATH includes Go and .NET
export PATH="/usr/local/go/bin:$HOME/go/bin:$HOME/.dotnet:$PATH"

# Run with serena's Python (has SolidLSP dependencies)
/workspaces/flow_squared/scratch/serena/.venv/bin/python \
    scripts/lsp/validate_solidlsp_cross_file.py
```

**Output** (after all fixes applied):
```
SolidLSP Cross-File Reference Validation
==================================================
[Python] Fixture: .../python_multi_project
  References found: 1
    - packages/auth/handler.py: line 12
  [PASS] Python: Found cross-file reference in handler.py

[TypeScript] Fixture: .../typescript_multi_project
  References found: 2
    - packages/client/index.tsx: line 1
    - packages/client/index.tsx: line 9
  [PASS] TypeScript: Found cross-file reference in index.tsx

[Go] Fixture: .../go_project
  References found: 1
    - cmd/server/main.go: line 10
  [PASS] Go: Found cross-file reference in main.go

[C#] Fixture: .../csharp_multi_project
  References found: 2
    - src/Api/Models.cs: line 11
    - src/Api/Program.cs: line 5
  [PASS] C#: Found cross-file reference in Program.cs

Summary
--------------------------------------------------
  Python: PASS
  TypeScript: PASS
  Go: PASS
  C#: PASS

Result: 4/4 languages passed
```

---

## Common Errors & Troubleshooting

This section documents errors encountered during validation and their resolutions. Use this for debugging similar issues in future phases.

### Python Errors

**Error**: `ModuleNotFoundError: No module named 'pyright'`
```
Traceback (most recent call last):
  File "/.../pyright_server.py", line 37, in ...
ModuleNotFoundError: No module named 'pyright'
```

**Cause**: SolidLSP's PyrightServer spawns `python -m pyright.langserver --stdio`. This uses the `python` from PATH, which must have the `pyright` pip package installed.

**Resolution**:
```bash
# Install pyright in the project venv (not globally)
uv pip install pyright
# Or add to pyproject.toml: "pyright>=1.1.400"
```

**Prevention**: fs2 now includes `pyright>=1.1.400` in its dependencies.

---

### TypeScript Errors

**Error**: `References found: 0` (no cross-file references returned)
```
[TypeScript] Fixture: .../typescript_multi_project
  References found: 0
  [FAIL] TypeScript: No cross-file reference found
```

**Cause**: TypeScript LSP uses lazy indexing. It only indexes files that are explicitly opened. Unlike Python/Go/C#, it does NOT index the entire project on startup.

**Resolution**:
```python
# WRONG - won't find cross-file references
refs = ls.request_references("utils.ts", line=4, column=16)

# CORRECT - open referencing file first
with ls.open_file("index.tsx"):
    pass  # Triggers indexing
refs = ls.request_references("utils.ts", line=4, column=16)
```

**Prevention**: Always open files that reference the definition before querying.

---

### Go Errors

**Error**: `Go is not installed` or `gopls not found`
```
SolidLSPException: Go is not installed
```

**Cause**: Go and gopls must be installed and on PATH. SolidLSP does NOT auto-download these.

**Resolution**:
```bash
# Install Go
/workspaces/flow_squared/scripts/lsp_install/install_go.sh

# Install gopls
/workspaces/flow_squared/scripts/lsp_install/install_gopls.sh

# Add to PATH
export PATH="/usr/local/go/bin:$HOME/go/bin:$PATH"
```

---

### C# Errors

**Error**: `We don't have an MSBuild to use`
```
Microsoft.CodeAnalysis.MSBuild.RemoteInvocationException:
An exception of type System.InvalidOperationException was thrown:
We don't have an MSBuild to use; HasUsableMSBuild should have been called first to check.
```

**Cause**: Two issues combined:
1. SolidLSP's version check was hardcoded to `.NET 9` exactly, but we have `.NET 10`
2. Roslyn LSP's BuildHost subprocess needs `DOTNET_ROOT` env var to find MSBuild

**Resolution** (APPLIED to SolidLSP):

Fix 1 - Accept .NET 9+ in `csharp_language_server.py` lines 294-298:
```python
has_compatible_runtime = any(
    f"Microsoft.NETCore.App {major}." in runtime_result.stdout
    for major in range(9, 20)  # .NET 9 through 19
)
```

Fix 2 - Pass DOTNET_ROOT env vars in `csharp_language_server.py` lines 237-242:
```python
dotnet_root = os.path.dirname(dotnet_path)
env = {
    "DOTNET_ROOT": dotnet_root,
    "DOTNET_HOST_PATH": dotnet_path,
    "DOTNET_MSBUILD_SDK_RESOLVER_CLI_DIR": dotnet_root,
}
```

**Prevention**: These fixes are now in the SolidLSP codebase at `scratch/serena/src/solidlsp/language_servers/csharp_language_server.py`. They must be preserved during Phase 1 vendoring.

---

### General Errors

**Error**: `SolidLSPException: Failed to start language server`

**Cause**: Usually a PATH issue - the underlying LSP server binary isn't found.

**Resolution**:
```bash
# Ensure all LSP servers are installed
/workspaces/flow_squared/scripts/lsp_install/install_all.sh

# Set PATH before running
export PATH="/usr/local/go/bin:$HOME/go/bin:$HOME/.dotnet:$PATH"
export GOPATH="$HOME/go"
export DOTNET_ROOT="$HOME/.dotnet"
```

---

## Code Changes Summary

**Files Modified in SolidLSP** (must preserve during vendoring):

| File | Line(s) | Change | Purpose |
|------|---------|--------|---------|
| `csharp_language_server.py` | 237-242 | Add `env` dict with DOTNET_ROOT vars | MSBuild discovery |
| `csharp_language_server.py` | 244 | Pass `env=env` to ProcessLaunchInfo | Pass env to subprocess |
| `csharp_language_server.py` | 294-298 | Check for .NET 9+ (not just .NET 9) | Support .NET 10+ |
| `csharp_language_server.py` | 444-448 | Same .NET 9+ check in fallback method | Consistency |

**Files Added to fs2**:

| File | Purpose |
|------|---------|
| `pyproject.toml` | Added `pyright>=1.1.400` dependency |
| `scripts/lsp/validate_solidlsp_cross_file.py` | Validation script |
| `tests/fixtures/lsp/*` | Ground truth fixtures for 4 languages |

---

## Related Documents

- [Subtask Dossier](./001-subtask-validate-lsp-cross-file.md)
- [Execution Log](./001-subtask-validate-lsp-cross-file.execution.log.md)
- [Phase 0b Research Results](./research-results.md)
- [Parent Plan](../../lsp-integration-plan.md)
