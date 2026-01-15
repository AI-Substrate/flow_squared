# Subtask 001 Execution Log: Validate LSP Cross-File Reference Resolution

**Started**: 2026-01-15
**Status**: COMPLETE
**Final Result**: 4/4 languages passing

---

## Task ST000: Install SolidLSP Dependencies
**Status**: Complete

### What I Did
- Ran `uv sync` in `scratch/serena/` to install SolidLSP dependencies
- Note: SolidLSP uses its own venv at `scratch/serena/.venv/` with Python 3.11
- Key dependency: `sensai-utils` required for SolidLSP imports

### Evidence
```
$ cd /workspaces/flow_squared/scratch/serena && uv sync
Resolved 201 packages in 1ms
Audited 64 packages in 78ms
```

### Discovery: SolidLSP Dependency Model
**Type**: insight

SolidLSP has a **mixed dependency model** - investigated via subagent:

| Language | Auto-downloads LSP? | User Prerequisites |
|----------|--------------------|--------------------|
| C# | YES (Roslyn + .NET runtime) | None (fully self-contained) |
| TypeScript | YES (npm packages) | Node.js + npm must be installed |
| Python | NO | `pyright` pip package required |
| Go | NO | Go toolchain + `gopls` required |

**RuntimeDependency system**: Located at `solidlsp/language_servers/common.py` (lines 17-165)
- Provides download/install orchestration for some languages
- Not used for Python or Go

---

## Tasks ST001-ST004: Create Fixtures
**Status**: Complete

### Files Created
- `tests/fixtures/lsp/python_multi_project/packages/auth/models.py` - User.validate() method
- `tests/fixtures/lsp/python_multi_project/packages/auth/handler.py` - calls user.validate()
- `tests/fixtures/lsp/typescript_multi_project/packages/client/utils.ts` - formatDate() function
- `tests/fixtures/lsp/typescript_multi_project/packages/client/index.tsx` - calls formatDate()
- `tests/fixtures/lsp/go_project/internal/auth/auth.go` - Validate() function
- `tests/fixtures/lsp/go_project/cmd/server/main.go` - calls auth.Validate()
- `tests/fixtures/lsp/csharp_multi_project/src/Api/Models.cs` - User.Validate() method
- `tests/fixtures/lsp/csharp_multi_project/src/Api/Program.cs` - calls user.Validate()

---

## Task ST005: Write SolidLSP Validation Script
**Status**: Complete

### File Created
`scripts/lsp/validate_solidlsp_cross_file.py`

### Key Implementation Notes
- Uses SolidLSP's `start()`/`stop()` lifecycle (NOT `start_server()` context manager)
- Created wrapper `@contextmanager language_server()` for clean lifecycle management
- LSP uses 0-indexed line/column positions
- Returns `list[ls_types.Location]` with `relativePath` field

---

## Task ST006: Run SolidLSP Validation
**Status**: In Progress

### Attempt 1: Initial Run
**Result**: 0/4 passed

**Errors**:
1. Python: `ModuleNotFoundError: No module named 'pyright'`
2. Go: "Go is not installed"
3. TypeScript: 0 references found
4. C#: MSBuild errors

### Discovery: Phase 0 Scripts Not Integrated
**Type**: gotcha

Phase 0 created LSP installation scripts at `scripts/lsp_install/`:
- `install_all.sh` - Orchestrator
- `install_go.sh`, `install_gopls.sh`, `install_pyright.sh`, `install_typescript_ls.sh`, `install_dotnet.sh`

**BUT**: These were never integrated into `post-install.sh` or devcontainer.json.
The scripts exist but weren't persisted to run on container rebuild.

### Fix Applied: Run Install Scripts
```bash
$ /workspaces/flow_squared/scripts/lsp_install/install_all.sh
```

All 5 components installed:
- Go 1.22.0 ✓
- gopls v0.21.0 ✓
- .NET SDK 10.0.102 ✓
- Pyright 1.1.408 ✓
- typescript-language-server 5.1.3 ✓

### Attempt 2: After Installing LSP Servers
**Result**: 1/4 passed (Go)

```
Python: FAIL - subprocess uses PATH python which didn't have pyright
TypeScript: FAIL - 0 references found
Go: PASS - Found cross-file reference in main.go!
C#: FAIL - MSBuild errors
```

### Discovery: Pyright Subprocess Issue
**Type**: gotcha

SolidLSP's PyrightServer spawns: `python -m pyright.langserver --stdio`

This uses `python` from PATH, which resolves to project venv (`/workspaces/flow_squared/.venv/bin/python`).
But pyright was installed in user site-packages, not project venv.

**Fix**: Install pyright in project venv:
```bash
$ uv pip install pyright
Installed 2 packages: nodeenv, pyright
```

### Attempt 3: After Installing Pyright in Venv + pyproject.toml
**Result**: 2/4 passed (Python, Go)

```
Python: PASS - Found cross-file reference in handler.py (line 12)
Go: PASS - Found cross-file reference in main.go (line 10)
TypeScript: FAIL - 0 references found
C#: FAIL - MSBuild errors, only found self-reference (Models.cs line 11)
```

**Fix Applied**: Added pyright to pyproject.toml dependencies:
```toml
"pyright>=1.1.400",  # Python LSP server for SolidLSP integration
```

### Investigation: TypeScript 0 References
**Status**: Resolved

**Root Cause**: TypeScript LSP needs BOTH files opened to index cross-file references.
- Python/Go index the whole project on startup
- TypeScript only indexes opened files

**Fix**: Open referencing file (`index.tsx`) before querying definition file (`utils.ts`):
```python
with ls.open_file("packages/client/index.tsx"):
    pass  # Just opening triggers indexing
refs = ls.request_references("packages/client/utils.ts", ...)
```

### Attempt 4: After Opening Both Files for TypeScript
**Result**: 3/4 passed (Python, TypeScript, Go)

```
Python: PASS - Found cross-file reference in handler.py (line 12)
TypeScript: PASS - Found cross-file references in index.tsx (lines 1, 9)
Go: PASS - Found cross-file reference in main.go (line 10)
C#: FAIL - MSBuild errors, only found self-reference
```

### Investigation: C# MSBuild Errors
**Status**: Unresolved (Known Limitation)

**Error**: `We don't have an MSBuild to use; HasUsableMSBuild should have been called first to check`

**Root Cause**: Roslyn LSP requires MSBuild to load .csproj files. While .NET SDK includes MSBuild (`dotnet msbuild` works), the Roslyn LSP auto-downloaded by SolidLSP doesn't have access to it.

**Attempted Fixes**:
1. Updated target framework from net8.0 to net9.0 - No effect
2. Opened both files before query - No effect
3. Verified `dotnet msbuild` works from CLI - Yes, but LSP subprocess doesn't see it

**Assessment**: This is an environment configuration issue with the auto-downloaded Roslyn LSP, not a SolidLSP code issue. The Roslyn LSP needs either:
- Full Visual Studio MSBuild
- Proper .NET SDK environment setup that the LSP subprocess can access

---

## Task ST008: Fix C# MSBuild Issue

**Status**: Complete

### Root Cause Analysis (via subagent)

The issue was two-fold:
1. **Version check too strict**: SolidLSP only accepted `.NET 9` exactly, but we have `.NET 10 SDK`
2. **Missing environment variables**: Roslyn LSP's `BuildHost` subprocess needs `DOTNET_ROOT` to find MSBuild

### Fix Applied

Modified `scratch/serena/src/solidlsp/language_servers/csharp_language_server.py`:

**Fix 1**: Accept .NET 9+ (lines 294-298):
```python
has_compatible_runtime = any(
    f"Microsoft.NETCore.App {major}." in runtime_result.stdout
    for major in range(9, 20)  # .NET 9 through 19
)
```

**Fix 2**: Pass DOTNET_ROOT to subprocess (lines 235-242):
```python
dotnet_root = os.path.dirname(dotnet_path)
env = {
    "DOTNET_ROOT": dotnet_root,
    "DOTNET_HOST_PATH": dotnet_path,
    "DOTNET_MSBUILD_SDK_RESOLVER_CLI_DIR": dotnet_root,
}
```

### Attempt 5: After C# Fix
**Result**: 4/4 passed!

```
Python: PASS - Found cross-file reference in handler.py (line 12)
TypeScript: PASS - Found cross-file references in index.tsx (lines 1, 9)
Go: PASS - Found cross-file reference in main.go (line 10)
C#: PASS - Found cross-file references in Models.cs (line 11), Program.cs (line 5)
```

---

## Final Results Summary

| Language | Status | References Found | Notes |
|----------|--------|-----------------|-------|
| Python (Pyright) | ✅ PASS | handler.py line 12 | Works out of box with pyright pip package |
| TypeScript | ✅ PASS | index.tsx lines 1, 9 | Requires opening both files |
| Go (gopls) | ✅ PASS | main.go line 10 | Works out of box |
| C# (Roslyn) | ✅ PASS | Program.cs line 5 | Requires .NET SDK (not just runtime) |

**Validation Outcome**: 4/4 languages validated successfully. SolidLSP is suitable for vendoring.

---

## Discoveries & Learnings (Running Log)

| Date | Task | Type | Discovery | Resolution | References |
|------|------|------|-----------|------------|------------|
| 2026-01-15 | ST006 | insight | SolidLSP has mixed dependency model | Document for users | RuntimeDependency in common.py |
| 2026-01-15 | ST006 | gotcha | Phase 0 scripts not in post-install.sh | Need to fix devcontainer | scripts/lsp_install/ |
| 2026-01-15 | ST006 | gotcha | Pyright needs pip install in project venv | `uv pip install pyright` | pyright_server.py:37 |
| 2026-01-15 | ST008 | gotcha | C# version check too strict (.NET 9 only) | Accept .NET 9+ | csharp_language_server.py:291 |
| 2026-01-15 | ST008 | gotcha | Roslyn needs DOTNET_ROOT for MSBuild | Pass env to ProcessLaunchInfo | csharp_language_server.py:235-242 |

---

## Environment Notes

**Python Interpreters**:
- Project venv: `/workspaces/flow_squared/.venv/bin/python` (Python 3.12)
- Serena venv: `/workspaces/flow_squared/scratch/serena/.venv/bin/python` (Python 3.11)
- SolidLSP subprocesses use PATH python

**PATH Requirements** (for Go/gopls to work):
```bash
export PATH="/usr/local/go/bin:$HOME/go/bin:$HOME/.dotnet:$PATH"
export GOPATH="$HOME/go"
export DOTNET_ROOT="$HOME/.dotnet"
```

---

## Complete Error Messages (For Troubleshooting Reference)

### Python Error (before fix)
```
[Python] Fixture: /workspaces/flow_squared/tests/fixtures/lsp/python_multi_project
  [ERROR] Python: Traceback (most recent call last):
  File "/workspaces/flow_squared/scratch/serena/src/solidlsp/language_servers/pyright_server.py", line 37, in _start_server
    ...
ModuleNotFoundError: No module named 'pyright'
```

### TypeScript Error (before opening both files)
```
[TypeScript] Fixture: /workspaces/flow_squared/tests/fixtures/lsp/typescript_multi_project
  References found: 0
  [FAIL] TypeScript: No cross-file reference found
```

### C# Error (before DOTNET_ROOT fix)
```
LSP: [project/open] [LanguageServerProjectLoader] Error while loading
/workspaces/flow_squared/tests/fixtures/lsp/csharp_multi_project/src/Api/Api.csproj:
Exception thrown: Microsoft.CodeAnalysis.MSBuild.RemoteInvocationException:
An exception of type System.InvalidOperationException was thrown:
We don't have an MSBuild to use; HasUsableMSBuild should have been called first to check.
- file BuildHost.cs line 132
   at Microsoft.CodeAnalysis.MSBuild.RpcClient.InvokeCoreAsync(...)
   at Microsoft.CodeAnalysis.MSBuild.RpcClient.InvokeAsync[T](...)
   at Microsoft.CodeAnalysis.MSBuild.RemoteBuildHost.LoadProjectFileAsync(...)
   at Microsoft.CodeAnalysis.LanguageServer.HostWorkspace.LanguageServerProjectSystem.TryLoadProjectInMSBuildHostAsync(...)
```

---

## Validation Commands

**Full validation (all 4 languages):**
```bash
export PATH="$HOME/.dotnet:$HOME/go/bin:/usr/local/go/bin:$PATH"
/workspaces/flow_squared/scratch/serena/.venv/bin/python \
    /workspaces/flow_squared/scripts/lsp/validate_solidlsp_cross_file.py
```

**Expected output after all fixes:**
```
SolidLSP Cross-File Reference Validation
==================================================
SolidLSP Path: /workspaces/flow_squared/scratch/serena/src
Fixtures Path: /workspaces/flow_squared/tests/fixtures/lsp

[Python] Fixture: /workspaces/flow_squared/tests/fixtures/lsp/python_multi_project
  References found: 1
    - packages/auth/handler.py: line 12
  [PASS] Python: Found cross-file reference in handler.py

[TypeScript] Fixture: /workspaces/flow_squared/tests/fixtures/lsp/typescript_multi_project
  References found: 2
    - packages/client/index.tsx: line 1
    - packages/client/index.tsx: line 9
  [PASS] TypeScript: Found cross-file reference in index.tsx

[Go] Fixture: /workspaces/flow_squared/tests/fixtures/lsp/go_project
  References found: 1
    - cmd/server/main.go: line 10
  [PASS] Go: Found cross-file reference in main.go

[C#] Fixture: /workspaces/flow_squared/tests/fixtures/lsp/csharp_multi_project
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

## Key Files Reference

| File | Purpose | Location |
|------|---------|----------|
| Validation Script | Main test script | `/workspaces/flow_squared/scripts/lsp/validate_solidlsp_cross_file.py` |
| Research Document | Findings summary | `./cross-file-lsp-validation.md` |
| Python Fixture | Test fixture | `/workspaces/flow_squared/tests/fixtures/lsp/python_multi_project/` |
| TypeScript Fixture | Test fixture | `/workspaces/flow_squared/tests/fixtures/lsp/typescript_multi_project/` |
| Go Fixture | Test fixture | `/workspaces/flow_squared/tests/fixtures/lsp/go_project/` |
| C# Fixture | Test fixture | `/workspaces/flow_squared/tests/fixtures/lsp/csharp_multi_project/` |
| C# LSP Fix | DOTNET_ROOT fix | `/workspaces/flow_squared/scratch/serena/src/solidlsp/language_servers/csharp_language_server.py` |
| fs2 Dependencies | pyright added | `/workspaces/flow_squared/pyproject.toml` |
| LSP Install Scripts | Phase 0 scripts | `/workspaces/flow_squared/scripts/lsp_install/` |
