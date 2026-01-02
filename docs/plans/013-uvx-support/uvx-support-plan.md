# uvx Support Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-01-02
**Spec**: [./uvx-support-spec.md](./uvx-support-spec.md)
**Status**: READY

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: Users and AI agent operators need a zero-install way to run fs2 CLI and MCP commands without cloning the repo or managing Python environments.

**Solution**: Document `uvx --from git+https://github.com/AI-Substrate/flow_squared` patterns across README.md, CLAUDE.md, and docs/how/AGENTS.md, plus update the mcp.py docstring.

**Expected Outcome**: Users can copy-paste uvx commands to run fs2 immediately; Claude Desktop configs work with uvx.

---

## Critical Research Findings (Concise)

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | uvx already works with current pyproject.toml (verified) | No code changes needed |
| 02 | High | README.md has MCP section at lines 89-128 | Add uvx subsection after existing setup |
| 03 | High | CLAUDE.md fs2 MCP section at lines 214-244 | Add uvx alternative to existing `claude mcp add` pattern |
| 04 | High | docs/how/AGENTS.md exists (183 lines) but no installation section | Add "Installation" section at top with uvx commands |
| 05 | High | mcp.py module docstring shows only local `fs2 mcp` usage | Add uvx example to Usage section |
| 06 | Medium | Commit pinning syntax: `@main` (branch) or `@<sha>` (commit) | Document both patterns for reproducibility |
| 07 | Medium | uvx caches builds automatically after first run | Mention caching behavior in docs |
| 08 | Low | GitHub repo URL: `git+https://github.com/AI-Substrate/flow_squared` | Use consistent URL across all docs |

---

## Implementation (Single Phase)

**Objective**: Add uvx documentation to all target files with consistent patterns and examples.

**Testing Approach**: Manual verification (documentation-only task)
**Mock Usage**: N/A (no code changes)

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [x] | T001 | Restructure README.md MCP section with uvx option | 1 | Docs | -- | /workspaces/flow_squared/README.md | MCP section has Option 1 (Local) + Option 2 (uvx) subsections | Reorganize lines 89-128 into subsections |
| [x] | T002 | ~~Add uvx alternative to CLAUDE.md~~ | -- | -- | -- | -- | SKIPPED: CLAUDE.md is for dogfooding local changes | Use local install, not uvx |
| [x] | T003 | Add Prerequisites + Installation sections to AGENTS.md | 1 | Docs | -- | /workspaces/flow_squared/docs/how/AGENTS.md | Prerequisites (scan step) + Installation with uvx patterns | Insert after line 7 (after Overview section) |
| [x] | T004 | Update mcp.py module docstring with uvx example | 1 | Docs | -- | /workspaces/flow_squared/src/fs2/cli/mcp.py | Usage section includes uvx example | Add after line 10 |
| [x] | T005 | Verify uvx commands work from remote | 1 | Test | T001-T004 | -- | Two-part: (1) `fs2 --help` from anywhere proves install, (2) `fs2 tree` from `/workspaces/flow_squared` proves tools work | Run part 2 from repo root (has .fs2/) |

### Content Templates

**README.md MCP section restructure** (reorganize existing + add uvx):

The MCP section should be restructured into clear subsections:

```markdown
## MCP Server (AI Agent Integration)

Start the MCP server for Claude Code, Claude Desktop, GitHub Copilot, or other MCP-compatible clients:

```bash
fs2 mcp
```

**Prerequisites**: Run `fs2 scan` first to index your codebase.

### Option 1: Local Install (Recommended for Daily Use)

**Claude Code**:
```bash
# Add fs2 MCP server (available across all projects)
claude mcp add fs2 --scope user -- fs2 mcp

# Verify it's configured
claude mcp list
```

**Claude Desktop** (`~/.config/claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "fs2": {
      "command": "fs2",
      "args": ["mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

### Option 2: Zero-Install with uvx

No local installation required. Requires [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
# Run fs2 commands directly from GitHub
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 --help
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 mcp

# Pin to specific commit for reproducibility
uvx --from git+https://github.com/AI-Substrate/flow_squared@main fs2 mcp
```

> First run builds from source (~30-60s). Subsequent runs use cache and are near-instant.

**Claude Desktop with uvx**:
```json
{
  "mcpServers": {
    "fs2": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/AI-Substrate/flow_squared", "fs2", "mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

### Available Tools
...
```

**Note**: T001 now involves restructuring the existing MCP section, not just appending.

**AGENTS.md Prerequisites + Installation section** (new sections after Overview):
```markdown
## Prerequisites

Before using fs2 tools, index your codebase (one-time setup per repo):

```bash
# Using uvx (no local install required)
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 scan

# For semantic search, add embeddings
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 scan --embed
```

This creates a `.fs2/` directory with the code graph. Re-run after significant code changes.

> **Note**: First run builds from source (~30-60s). Subsequent runs use cache and are near-instant.

## Installation

### Option 1: uvx (Zero-Install)

Run fs2 directly from the GitHub repository without local installation:

```bash
# Start MCP server (after running fs2 scan)
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 mcp
```

**Pin to a specific commit** for reproducibility:
```bash
uvx --from git+https://github.com/AI-Substrate/flow_squared@abc1234 fs2 mcp
```

### Option 2: Claude MCP Add

If fs2 is installed locally:
```bash
claude mcp add fs2 --scope user -- fs2 mcp
```

### Option 3: Claude Desktop Configuration

```json
{
  "mcpServers": {
    "fs2": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/AI-Substrate/flow_squared", "fs2", "mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```
```

**mcp.py docstring addition** (in Usage section):
```python
Usage:
    fs2 mcp              # Start MCP server on STDIO (local install)

    # Zero-install with uvx:
    uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 mcp
```

### Acceptance Criteria

- [x] README.md contains uvx CLI usage section
- [x] README.md shows Claude Desktop config with uvx
- [x] ~~CLAUDE.md fs2 MCP section includes uvx alternative~~ SKIPPED (dogfood local)
- [x] docs/how/AGENTS.md has Prerequisites + Installation sections with uvx patterns
- [x] mcp.py docstring includes uvx example
- [x] Commit pinning pattern (`@main`, `@<sha>`) documented
- [x] `uvx --from git+...@main fs2 tree` and `get-node` succeed (verified)

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GitHub rate limiting on uvx builds | Low | Low | uvx caches builds locally |
| Repo URL changes | Low | Medium | Use canonical org/repo URL |

---

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/013-uvx-support/uvx-support-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended for CS-3+ tasks)
- **Optional task expansion**: `/plan-5-phase-tasks-and-brief` (if you want a separate dossier)

---

## Critical Insights Discussion

**Session**: 2026-01-02
**Context**: uvx Support Implementation Plan v1.0
**Analyst**: AI Clarity Agent
**Reviewer**: Development Team
**Format**: Water Cooler Conversation (5 Critical Insights)

### Insight 1: AGENTS.md Template Missing Critical Scan Step

**Did you know**: External repo users following AGENTS.md will hit "Graph not found" errors because the template shows `fs2 tree` without explaining that `fs2 scan` must run first.

**Implications**:
- Every external user hits the same error on first try
- "Zero-install" promise feels broken
- Users think uvx is broken when it's a workflow gap

**Options Considered**:
- Option A: Add Scan Step to Template - inline scan before tree
- Option B: Only Show MCP Setup - remove CLI examples
- Option C: Add Prerequisite Section - separate one-time setup from usage

**AI Recommendation**: Option C - Add Prerequisite Section
- Reasoning: Clear separation of one-time setup vs ongoing usage; honest about workflow.

**Discussion Summary**: User agreed that external users need the full picture.

**Decision**: Add Prerequisites section to AGENTS.md before Installation, showing `fs2 scan` as one-time setup.

**Action Items**:
- [x] Updated T003 description
- [x] Updated AGENTS.md template in plan

**Affects**: T003 (AGENTS.md), spec acceptance criteria

---

### Insight 2: T005 Verification Test Is Underspecified

**Did you know**: The T005 smoke test (`fs2 tree`) will fail unless run from a directory with `.fs2/`, because fs2 uses the current working directory to find the graph.

**Implications**:
- Test could pass locally but fail for real users
- Doesn't verify external user experience
- `get-node` has same problem

**Options Considered**:
- Option A: Specify Test Location Explicitly
- Option B: Test Only Help/Version Commands
- Option C: Full Workflow Test (scan then tree)
- Option D: Two-Part Verification (help anywhere + tree from repo)

**AI Recommendation**: Option D - Two-Part Verification
- Reasoning: Proves both uvx install works and tools function, without complex setup.

**Discussion Summary**: User asked for subagent validation of fs2 tree behavior. Confirmed it uses CWD to find `.fs2/graph.pickle`. User chose Option D.

**Decision**: T005 becomes two-part: (1) `fs2 --help` from anywhere, (2) `fs2 tree` from repo root.

**Action Items**:
- [x] Updated T005 validation criteria
- [x] Updated Commands to Run section

**Affects**: T005 in plan and tasks.md, spec acceptance criteria

---

### Insight 3: First-Run Delay Not Documented

**Did you know**: Users running uvx for the first time experience 30-60 second delay while uvx builds from source, with no indication of what's happening.

**Implications**:
- First-time users might think command is broken
- May Ctrl+C and retry (wasting time)
- "Zero-install" feels slow

**Options Considered**:
- Option A: Add "First Run Note" to Documentation
- Option B: Don't Mention It
- Option C: Show Verbose Command for First Run

**AI Recommendation**: Option A - Brief Note
- Reasoning: One sentence manages expectations without being alarming.

**Discussion Summary**: User agreed a brief note prevents confusion.

**Decision**: Add timing note: "First run builds from source (~30-60s). Subsequent runs use cache and are near-instant."

**Action Items**:
- [x] Updated README template
- [x] Updated AGENTS.md template

**Affects**: T001, T003 content templates

---

### Insight 4: Missing uv/uvx Installation Prerequisite

**Did you know**: Documentation assumes users have `uv` installed, but not all Python developers have adopted it yet.

**Implications**:
- Users without uv hit "command not found" immediately
- "Zero-install" breaks at step zero
- May not know what uv is

**Options Considered**:
- Option A: Add uv Install Link to README Only
- Option B: Add uv Prerequisite to All Docs
- Option C: Don't Mention It

**AI Recommendation**: Option A - README Only
- Reasoning: README is entry point; AGENTS.md/mcp.py readers are technical enough.

**Discussion Summary**: User agreed README is the front door.

**Decision**: Add uv prerequisite with install command to README template only.

**Action Items**:
- [x] Updated README template with uv link and install command

**Affects**: T001 content template

---

### Insight 5: README Will Have Three MCP Setup Methods - Needs Structure

**Did you know**: After this change, README's MCP section will show multiple setup patterns (claude mcp add, Claude Desktop local, uvx CLI, Claude Desktop uvx) which could confuse users.

**Implications**:
- Users won't know which to choose
- Growing section becomes harder to navigate
- uvx looks like addition rather than alternative

**Options Considered**:
- Option A: Add "When to Use Which" Guidance
- Option B: Separate Subsections (Local Install vs Zero-Install)
- Option C: Keep It Flat

**AI Recommendation**: Option B - Separate Subsections
- Reasoning: Clear organization; users can pick their path quickly.

**Discussion Summary**: User agreed subsections make it scannable.

**Decision**: Restructure MCP section into "Option 1: Local Install" and "Option 2: Zero-Install with uvx" subsections.

**Action Items**:
- [x] Updated T001 to "Restructure" instead of "Add"
- [x] Created full README template with subsection structure

**Affects**: T001 description and approach

---

## Session Summary

**Insights Surfaced**: 5 critical insights identified and discussed
**Decisions Made**: 5 decisions reached through collaborative discussion
**Action Items Created**: 0 remaining (all applied immediately)
**Files Updated During Session**:
- `uvx-support-plan.md` (templates, task descriptions, acceptance criteria)
- `tasks/phase-1-implementation/tasks.md` (task descriptions, commands)
- `uvx-support-spec.md` (acceptance criteria)

**Shared Understanding Achieved**: ✓

**Confidence Level**: High - Key gaps identified and addressed before implementation.

**Next Steps**:
Proceed to implementation with `/plan-6-implement-phase`

**Notes**:
- T001 scope increased from "append" to "restructure" - still CS-1 but more editing
- All insights led to plan improvements, no deferred items

---

## Subtasks Registry

Mid-implementation detours requiring structured tracking.

| ID | Created | Phase | Parent Task | Reason | Status | Dossier |
|----|---------|-------|-------------|--------|--------|---------|
| 001-subtask-install-upgrade-cli-commands | 2026-01-02 | Phase 1: Implementation | T001 | Add self-bootstrapping CLI commands so users can permanently install fs2 from a uvx invocation | [x] Complete | [Link](tasks/phase-1-implementation/001-subtask-install-upgrade-cli-commands.md) |
