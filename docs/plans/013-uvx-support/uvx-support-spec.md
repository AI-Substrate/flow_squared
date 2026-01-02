# uvx Support for fs2

**Mode**: Simple

## Summary

Enable users to run fs2 CLI and MCP commands directly via `uvx` from the GitHub repository without requiring local installation. This provides zero-install access to fs2 for both human users (CLI) and AI agents (MCP server).

**WHY**: Users and AI agent configurations (like Claude Desktop) need a simple, one-liner way to run fs2 without cloning the repo or managing Python environments. `uvx --from git+...` provides this.

## Goals

- Users can run `uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 <command>` without any prior setup
- MCP server can be started via uvx for Claude Desktop and other MCP clients
- Documentation clearly explains uvx usage patterns for both CLI and MCP modes
- README includes copy-pasteable commands for common use cases
- Documentation includes commit pinning patterns for reproducibility

## Non-Goals

- Publishing to PyPI (explicitly out of scope)
- Creating shell aliases or wrapper scripts
- Supporting uvx caching configuration
- Supporting pinned versions beyond branch/commit refs

## Complexity

- **Score**: CS-1 (trivial)
- **Breakdown**: S=1, I=0, D=0, N=0, F=0, T=0 (multiple doc files)
- **Confidence**: 0.95
- **Assumptions**:
  - uvx already works with the current pyproject.toml (verified: ✓)
  - No code changes required, only documentation
- **Dependencies**: None
- **Risks**: None identified
- **Phases**: Single documentation phase

## Acceptance Criteria

1. **README documents uvx CLI usage**: README.md contains a section showing how to run fs2 commands via uvx from git
2. **README documents uvx MCP usage**: README.md shows Claude Desktop configuration using uvx
3. ~~**CLAUDE.md updated**~~: SKIPPED - CLAUDE.md is for dogfooding local changes, not uvx
4. **AGENTS.md updated**: docs/how/AGENTS.md Prerequisites + Installation sections with uvx patterns for external repos
5. **MCP CLI docstring updated**: The `fs2 mcp` command docstring includes uvx example
6. **Verified working**: Two-part test: (1) `fs2 --help` proves uvx install, (2) `fs2 tree` from repo root proves tools work

## Risks & Assumptions

- **Assumption**: GitHub repo remains public (or users have access)
- **Assumption**: Users have `uv`/`uvx` installed (standard for modern Python dev)
- **Risk**: Network latency on first run (uvx builds from source) - mitigated by uvx caching

## Documentation Strategy

- **Location**: README.md + docs/how/AGENTS.md + mcp.py docstring
- **Rationale**: Quick-start in README, agent-specific guidance in AGENTS.md for external repos
- **Content Split**:
  - README.md: uvx CLI usage, Claude Desktop MCP example
  - docs/how/AGENTS.md: Installation section with uvx patterns (for external repos)
  - mcp.py: uvx example in module docstring
  - ~~CLAUDE.md~~: SKIPPED - developers here should dogfood local install
- **Target Audience**: fs2 users, AI agent operators in external repos
- **Maintenance**: Update when uvx patterns change or repo moves

## Open Questions

~~1. Should we document commit pinning for reproducibility?~~ → **Resolved: Yes**
~~2. Should CLAUDE.md also be updated with uvx instructions?~~ → **Resolved: Yes + AGENTS.md**

## ADR Seeds (Optional)

- **Decision Drivers**: Zero-install experience, no PyPI maintenance overhead
- **Candidate Alternatives**:
  - A) uvx from git (chosen) - zero maintenance, always latest
  - B) PyPI publishing - more discoverable but requires release process
  - C) Docker image - heavier, different toolchain
- **Stakeholders**: fs2 users, AI agent operators

## Clarifications

### Session 2026-01-02

| # | Question | Answer |
|---|----------|--------|
| Q1 | Workflow mode? | **Simple** - CS-1 docs-only task |
| Q2 | Documentation location? | **README.md + docs/how/AGENTS.md + mcp.py** |
| Q3 | Update CLAUDE.md? | **No** - CLAUDE.md is for dogfooding local install |
| Q4 | Document commit pinning? | **Yes** - show `@main` and `@<commit>` patterns |

**Coverage Summary**:
- Resolved: Mode, Documentation Strategy, CLAUDE.md scope, commit pinning
- Deferred: None
- Outstanding: None
