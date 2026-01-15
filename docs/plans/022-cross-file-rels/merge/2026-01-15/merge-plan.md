# Merge Plan: Integrating Upstream Changes

**Generated**: 2026-01-15
**Your Branch**: `022-cross-file` @ `02291bc`
**Merging From**: `origin/main` @ `b10755a`
**Common Ancestor**: `9ceff1d` @ 2026-01-12

---

## Executive Summary

### What Happened While You Worked

You branched from `main` **3 days ago**. Since then, **1 plan** landed in `origin/main`:

| Plan | Merged | Purpose | Risk to You |
|------|--------|---------|-------------|
| [023-multi-graphs](../../../023-multi-graphs/) | PR #1 | Multi-graph support: configure and query multiple named graphs | **Low** |

### Conflict Summary

- **Direct File Conflicts**: 4 files (all Complementary - different sections modified)
- **Semantic Conflicts**: 0
- **Regression Risks**: 0

### Recommended Approach

```
Single merge - changes are orthogonal and auto-mergeable
```

---

## Timeline

```
origin/main:    9ceff1d ─── 61f0228 ─── 2a74d0e ─── 135b18c ─── 139e346 ─── 40c37ba ─── d347e0d ─── 1d7401a ─── 7ba8d90 ─── b10755a
                   │                                                                                                      (9 commits)
                   │
022-cross-file:    └─── 3861631 ─── b9c455f ─── 27a2b15 ─── 0cf158c ─── f53e8c5 ─── 3be506e ─── 02291bc
                        (7 commits)
```

---

## Upstream Plan Analysis

### Plan 023-multi-graphs

**Purpose**: Enable fs2 to load and query multiple named graph files beyond the default `.fs2/graph.pickle`, configured via YAML with names, paths, descriptions, and source URLs.

| Attribute | Value |
|-----------|-------|
| Merged | PR #1 merged to main |
| Files Changed | 73 files |
| Tests Added | 13 test files |
| Conflicts with You | 4 files (Complementary) |

**Key Changes**:
- Added `OtherGraph` and `OtherGraphsConfig` models in `config/objects.py`
- Added `GraphService` with thread-safe caching and staleness detection
- Added `list-graphs` CLI command (`src/fs2/cli/list_graphs.py`)
- Added `--graph-name` parameter to CLI commands
- Extended MCP tools with `graph_name` parameter
- Updated devcontainer to use `uv run fs2 mcp` instead of `flowspace mcp`
- Added GitHub CLI feature to devcontainer
- Added `.mcp.json` configuration file
- Comprehensive documentation in `docs/how/user/multi-graphs.md`

**Potential Conflicts with Your Work**:
- `.devcontainer/post-install.sh` - Both modified, different sections (Complementary)
- `src/fs2/config/objects.py` - Both modified, different sections (Complementary)
- `docs/how/user/configuration-guide.md` - Both modified, different sections (Complementary)

---

## Your Changes Summary

**Branch**: `022-cross-file` @ `02291bc`
**Commits**: 7 since branching
**Files Modified**: 79 files

**What You're Building**:
Cross-file relationship extraction research and implementation. Includes CodeEdge/EdgeType models for representing cross-file relationships, experiment scripts for node ID detection, import/call extraction, and LSP integration research.

**Key Changes Made**:
- Added `CodeEdge` and `EdgeType` models (`src/fs2/core/models/code_edge.py`, `edge_type.py`)
- Extended `GraphStore` interface with edge storage methods
- Added LSP installation scripts (`scripts/lsp_install/`)
- Added cross-file relationship research scripts (`scripts/cross-files-rels-research/`)
- Modified token limits in `SmartContentConfig` (200/150/100 → 1000)
- Added Go and .NET to devcontainer PATH
- Plan folders: 022-cross-file-rels, 024-cross-file-impl, 025-lsp-research

**Components You Depend On**:
- `GraphStore` interface (you extended it with edge methods)
- `config/objects.py` (you modified SmartContentConfig defaults)
- devcontainer setup (you added LSP server installation)

---

## Conflict Analysis

### Conflict 1: `.devcontainer/post-install.sh`

**Conflict Type**: Complementary (both branches made non-conflicting changes to different sections)

**Your Change**:
```bash
# Added LSP server installation (lines 20-22)
echo "Installing LSP servers..."
/workspaces/flow_squared/scripts/lsp_install/install_all.sh

# Extended PATH with Go and .NET (lines 35-37)
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/usr/local/go/bin:$HOME/go/bin:$HOME/.dotnet:$PATH"
export GOPATH="$HOME/go"
export DOTNET_ROOT="$HOME/.dotnet"
```

**Upstream Change**:
```bash
# Added uv sync block at top (lines 6-10)
if [ -f "pyproject.toml" ]; then
    echo "Installing Python dependencies via uv sync..."
    uv sync
fi

# Changed MCP command (line 43)
claude mcp add flowspace -- uv run fs2 mcp  # was: flowspace mcp
```

**Reasoning Chain**:
1. Your change adds LSP installation in the middle of the script
2. Upstream adds uv sync at the top and changes MCP command at the bottom
3. These are complementary - both can coexist
4. The PATH line may need manual merge (combine both changes)

**Resolution**: Auto-merge with minor manual adjustment for PATH line

**Verification**:
- [ ] Rebuild devcontainer and verify all installations work
- [ ] Verify `fs2 mcp` command works correctly

---

### Conflict 2: `src/fs2/config/objects.py`

**Conflict Type**: Complementary (different sections modified)

**Your Change**:
```python
# Modified SmartContentConfig.token_limits defaults (lines 411-425)
token_limits: dict[str, int] = Field(
    default_factory=lambda: {
        "file": 1000,      # was: 200
        "type": 1000,      # was: 200
        "callable": 1000,  # was: 150
        # ... all changed to 1000
    }
)
```

**Upstream Change**:
```python
# Added new imports (lines 15-17)
from pathlib import Path
from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator

# Added new classes (lines 740-846)
class OtherGraph(BaseModel):
    """Configuration for an external graph reference."""
    ...

class OtherGraphsConfig(BaseModel):
    """Configuration for external graph references."""
    ...

# Added to YAML_CONFIG_TYPES list (line 925)
YAML_CONFIG_TYPES: list[type[BaseModel]] = [
    ...
    OtherGraphsConfig,
]
```

**Reasoning Chain**:
1. Your change modifies existing defaults in `SmartContentConfig` class
2. Upstream adds entirely new classes (`OtherGraph`, `OtherGraphsConfig`)
3. Changes are in completely different sections
4. No semantic conflict - both modifications are valid

**Resolution**: Auto-merge (git will handle cleanly)

**Verification**:
- [ ] Run `pytest tests/unit/config/` to verify config models
- [ ] Verify both your token limits and upstream's multi-graph config work

---

### Conflict 3: `docs/how/user/configuration-guide.md`

**Conflict Type**: Complementary (different sections modified)

**Your Change**:
- Updated token_limits documentation to reflect new 1000 defaults
- 9 insertions, 9 deletions (localized to smart_content section)

**Upstream Change**:
- Added multi-graph configuration documentation
- 46 insertions, 2 deletions (new sections added)

**Reasoning Chain**:
1. Your changes update existing documentation values
2. Upstream adds new documentation sections
3. No overlap in content

**Resolution**: Auto-merge

**Verification**:
- [ ] Review merged documentation for consistency

---

### Conflict 4: `src/fs2/docs/configuration-guide.md`

**Conflict Type**: Same as Conflict 3 (duplicate documentation file)

**Resolution**: Auto-merge

---

## Regression Risk Analysis

| Risk | Direction | Upstream Plan | Your Change | Likelihood | Test Command |
|------|-----------|---------------|-------------|------------|--------------|
| None identified | - | - | - | - | - |

**Reasoning**: Changes are orthogonal - multi-graph support and cross-file relationships don't interact.

**Recommended Test Sequence:**
1. `pytest tests/unit/` - Unit tests for all changes
2. `pytest tests/integration/` - Integration tests including multi-graph
3. `fs2 scan` - Verify scanning still works
4. `fs2 tree` - Verify tree command
5. `fs2 list-graphs` - Verify new upstream command works

---

## Merge Order Recommendation

**Single Merge** - All upstream changes come from one plan (023-multi-graphs) and are auto-mergeable.

**Overall Risk Assessment:**
- Total Direct Conflicts: 4 files
- Total Semantic Conflicts: 0
- Total Regression Risks: 0
- Estimated Manual Resolution: 0-1 files (PATH line in post-install.sh)
- Recommended Approach: **Single merge with verification**

---

## Merge Execution Plan

### Pre-Merge: Create Backup

```bash
# Create backup branch (already done by user awareness)
git branch backup-2026-01-15-before-merge
```

### Phase 1: Execute Merge

```bash
# Ensure we're on the correct branch
git checkout 022-cross-file

# Merge origin/main
git merge origin/main --no-commit

# Check what changed
git diff --staged --name-only
```

### Phase 2: Verify Merge Result

```bash
# Expected: 4 files may need review
# .devcontainer/post-install.sh
# src/fs2/config/objects.py
# docs/how/user/configuration-guide.md
# src/fs2/docs/configuration-guide.md

# If conflicts marked, resolve them:
# git status will show "both modified" files
```

### Phase 3: Handle post-install.sh (if needed)

If git marks `.devcontainer/post-install.sh` as conflicting:

1. The merged file should include:
   - Upstream's `uv sync` block at top
   - Your LSP installation in the middle
   - Upstream's `uv run fs2 mcp` command
   - Your extended PATH with Go/.NET

2. Verify the PATH line combines both needs:
```bash
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/usr/local/go/bin:$HOME/go/bin:$HOME/.dotnet:$PATH"
```

### Phase 4: Complete Merge

```bash
# Stage resolved files
git add .

# Commit the merge
git commit -m "$(cat <<'EOF'
Merge origin/main: integrate 023-multi-graphs

Integrates multi-graph support from PR #1:
- OtherGraph/OtherGraphsConfig models
- GraphService with caching
- list-graphs CLI command
- MCP graph_name parameter
- Updated devcontainer (uv sync, gh CLI)

Resolved complementary changes in:
- post-install.sh (kept both LSP install and uv sync)
- config/objects.py (kept token limits + new models)
- configuration-guide.md (kept both doc updates)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

### Phase 5: Validation

```bash
# Run full test suite
pytest tests/

# Verify type checks
# (if mypy/pyright configured)

# Verify fs2 commands work
fs2 scan --help
fs2 tree --help
fs2 list-graphs --help
```

---

## Post-Merge Validation Checklist

- [ ] All tests pass: `pytest tests/`
- [ ] `fs2 scan` works correctly
- [ ] `fs2 tree` works correctly
- [ ] `fs2 list-graphs` works (new upstream command)
- [ ] Devcontainer rebuilds successfully
- [ ] MCP server starts with `uv run fs2 mcp`
- [ ] Your cross-file models still work (`CodeEdge`, `EdgeType`)
- [ ] Token limits are 1000 (your change preserved)

---

## Rollback Procedure

If merge fails:

```bash
# Abort merge in progress
git merge --abort

# Or reset to pre-merge state
git reset --hard backup-2026-01-15-before-merge

# Clean up backup branch when confident
# git branch -D backup-2026-01-15-before-merge
```

---

## Human Approval Required

Before executing this merge plan, please review:

### Summary Review
- [ ] I understand that 1 upstream plan (023-multi-graphs) changed 73 files
- [ ] I understand the 4 file conflicts are Complementary (different sections)
- [ ] I understand there are 0 semantic conflicts or regression risks

### Conflict Review
- [ ] I have reviewed each conflict's resolution strategy
- [ ] I understand only `post-install.sh` may need minor manual review
- [ ] I am prepared to verify the PATH line if needed

### Risk Acknowledgment
- [ ] I will run `pytest tests/` after merging
- [ ] I have a backup branch for rollback if needed

---

**Proceed with merge execution?**

Type **"PROCEED"** to begin merge execution, or **"ABORT"** to cancel.
