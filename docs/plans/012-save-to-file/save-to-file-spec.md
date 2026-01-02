# Save Output to File for CLI and MCP Commands

**Mode**: Simple

📚 *This specification incorporates findings from `research-dossier.md`*

---

## Research Context

Based on deep codebase research conducted 2026-01-02:

- **Components affected**: `src/fs2/cli/search.py`, `src/fs2/cli/tree.py`, `src/fs2/mcp/server.py`
- **Critical dependencies**: Existing `_validate_save_path()` security function, `get_node` patterns
- **Modification risks**: Low for search, Medium for tree (output format mismatch)
- **Key insight**: Pattern fully implemented in `get_node` - high reuse opportunity

See `research-dossier.md` for full analysis (55+ findings, 15 prior learnings).

---

## Summary

**WHAT**: Add file output capability to CLI `search` and `tree` commands, and MCP `search()` and `tree()` tools, enabling users and AI agents to save JSON results directly to files.

**WHY**: AI agents and scripts working with fs2 need to save complex search results for post-processing with tools like `jq`. Currently only `get-node` supports file output. This gap forces agents to rely on shell redirection, which is error-prone and doesn't provide confirmation. Native file output enables query-once-process-many workflows essential for agent automation.

---

## Goals

1. **Enable direct file saving for search results**: Users can save search JSON envelopes to files for later processing with `jq` or other tools
2. **Enable direct file saving for tree output**: Users can save tree structure as JSON to files
3. **Maintain consistency with existing patterns**: Follow the established `--file` (CLI) and `save_to_file` (MCP) patterns from `get-node`
4. **Provide security parity**: Apply the same path validation security to all file output operations
5. **Support agent workflows**: MCP tools return `saved_to` field for programmatic confirmation
6. **Preserve stdout for piping**: When `--file` is used, stdout remains clean (no JSON output)

---

## Non-Goals

1. **Not adding output format options**: Only JSON output supported for search (no CSV, YAML, etc.)
2. **Not modifying existing get-node behavior**: The reference implementation remains unchanged
3. **Not adding compression**: No gzip or other compression for output files
4. **Not adding append mode**: Each save overwrites existing file (standard behavior)
5. **Not changing Rich display for tree**: CLI tree continues to display Rich formatted output unless `--json` flag is used

---

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=1, I=0, D=0, N=0, F=1, T=1 (Total: 3)
- **Confidence**: 0.90

### Dimension Details

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | 3-4 source files + test files, all in same domain |
| Integration (I) | 0 | No new external dependencies; reuses existing libs |
| Data/State (D) | 0 | No schema changes; output format unchanged |
| Novelty (N) | 0 | Well-specified; copying proven get_node pattern |
| Non-Functional (F) | 1 | Security: must validate paths to prevent traversal |
| Testing/Rollout (T) | 1 | Integration tests needed; no feature flags |

### Assumptions

1. Existing `_validate_save_path()` function works correctly and doesn't need modification
2. CLI tree can add `--json` flag without breaking existing users
3. MCP tree return type change (when saving) is acceptable

### Dependencies

1. `get_node` implementation remains stable as reference
2. `_validate_save_path()` security function available for reuse

### Risks

1. **Tree output format**: CLI tree outputs Rich text, not JSON - requires `--json` flag
2. **MCP tree return type**: Always return `{"tree": [...]}` wrapper for consistency (design decision from Insight #5)

### Phases

1. **Phase 1**: CLI `search --file` and MCP `search(save_to_file=...)`
2. **Phase 2**: CLI `tree --json --file` and MCP `tree(save_to_file=...)`

---

## Acceptance Criteria

### AC1: CLI Search File Output
**Given** a valid code graph exists
**When** a user runs `fs2 search "pattern" --file results.json`
**Then** the search envelope JSON is written to `results.json` and stdout is empty

### AC2: CLI Search File Output Confirmation
**Given** a user runs search with `--file` flag
**When** the file is successfully written
**Then** stderr shows a confirmation message like "✓ Wrote search results to results.json"

### AC3: MCP Search save_to_file Parameter
**Given** an indexed codebase and valid search pattern
**When** an agent calls `search(pattern="...", save_to_file="results.json")`
**Then** the envelope JSON is written to `results.json` and response includes `saved_to` field with absolute path

### AC4: MCP Search Path Validation
**Given** an agent calls search with `save_to_file="../escape.json"`
**When** the path escapes the working directory
**Then** a ToolError is raised with message about path escaping

### AC4b: CLI Path Validation
**Given** a user runs any CLI command with `--file ../escape.json`
**When** the path escapes the working directory
**Then** an error is shown and exit code is 1

### AC5: CLI Tree JSON Output Mode
**Given** a valid code graph exists
**When** a user runs `fs2 tree --json`
**Then** stdout contains JSON array of tree nodes instead of Rich formatted text

### AC6: CLI Tree File Output
**Given** a valid code graph exists
**When** a user runs `fs2 tree --file tree.txt` (without --json)
**Then** the Rich formatted text is written to `tree.txt` and stdout is empty

### AC6b: CLI Tree JSON File Output
**Given** a valid code graph exists
**When** a user runs `fs2 tree --json --file tree.json`
**Then** the tree JSON is written to `tree.json` and stdout is empty

### AC7: MCP Tree save_to_file Parameter
**Given** an indexed codebase
**When** an agent calls `tree(pattern=".", save_to_file="tree.json")`
**Then** the tree JSON is written to `tree.json` and response includes `saved_to` field

**Note**: MCP tree always returns `{"tree": [...]}` wrapper for consistency with search pattern. The `saved_to` field is only added when `save_to_file` is used.

### AC8: MCP Annotation Updates
**Given** save_to_file is added to search and tree MCP tools
**When** tools can write files
**Then** `readOnlyHint` annotation is set to `False` for both tools

### AC9: Empty Results Still Save
**Given** a search returns zero results
**When** user specifies `--file` option
**Then** the empty envelope `{"meta": {...}, "results": []}` is still written to the file

### AC10: Subdirectory Auto-Creation
**Given** a user runs `fs2 search "test" --file subdir/results.json`
**When** `subdir/` does not exist
**Then** the directory is created and the file is written successfully

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tree `--json` changes existing behavior | Low | Medium | Flag is additive; default behavior unchanged |
| MCP tree return type confusion | Medium | Low | Document behavior clearly; type change only when saving |
| Path validation bypass | Low | High | Reuse proven `_validate_save_path()` function |

### Assumptions

1. Users may want either Rich text or JSON tree output saved to file
2. AI agents parsing MCP responses can handle conditional return types
3. Existing test fixtures are sufficient for new tests

---

## Open Questions

*All questions resolved - see Clarifications section.*

---

## ADR Seeds (Optional)

### Decision Drivers
- Consistency with existing `get_node` patterns
- Security for MCP file writes (agent sandbox)
- JSON-first philosophy for programmatic access

### Candidate Alternatives
- **A**: Add `--file` to all commands (chosen approach)
- **B**: Add generic `--output` flag at app level
- **C**: Only add to MCP, rely on shell redirection for CLI

### Stakeholders
- AI agent developers (primary - MCP file output)
- Script authors (secondary - CLI file output)
- Interactive users (tertiary - may prefer stdout/pipe)

---

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Pattern replication from well-tested `get_node` - TDD ensures parity and catches edge cases
- **Focus Areas**:
  - File creation and JSON validity
  - `saved_to` field presence in MCP responses
  - Path validation security (escape attempts, absolute paths)
  - Empty stdout when `--file` used
  - Empty results still save correctly
- **Excluded**: None - all acceptance criteria require test coverage
- **Mock Usage**: Targeted mocks - following established patterns:
  - **Faked**: `FakeGraphStore` (in-memory), `FakeConfigurationService` (pre-loaded configs)
  - **Real**: File I/O with `tmp_path`, path validation, JSON serialization
  - **Pattern**: Inject fakes via `dependencies.set_config/set_graph_store()`, use `os.chdir(tmp_path)` for save_to_file tests
  - **Cleanup**: `reset_mcp_dependencies` autouse fixture ensures isolation

---

## Documentation Strategy

- **Location**: Hybrid (README + docs/how/)
- **Rationale**: Flags are self-documenting via `--help`; MCP needs guide updates for agent developers
- **Content Split**:
  - **README.md**: Add `--file` examples to existing CLI command sections (1-2 lines each)
  - **docs/how/mcp-server-guide.md**: Document `save_to_file` parameter for all MCP tools
- **Target Audience**:
  - CLI users (README examples)
  - AI agent developers (MCP guide)
- **Maintenance**: Update when new file output options added

---

## External Research

*No external research was required for this feature - all patterns exist in codebase.*

---

---

## Clarifications

### Session 2026-01-02

**Q1: Testing approach?**
- **Answer**: A - Full TDD
- **Rationale**: Pattern replication from well-tested `get_node` - TDD ensures parity

**Q2: Mock usage policy?**
- **Answer**: B - Allow targeted mocks
- **Rationale**: Follow existing patterns - fake graph/config, real file I/O

**Q3: Documentation location?**
- **Answer**: C - Hybrid (README + docs/how/)
- **Split**: README for CLI examples, docs/how/mcp-server-guide.md for MCP tools

**Q4: Tree `--file` without `--json`?**
- **Answer**: Allow it - save Rich text as plain text
- **Rationale**: Simpler, flexible; MCP tool description will suggest using `--json` for programmatic processing

**Q5: CLI path validation?**
- **Answer**: B - Same validation as MCP
- **Rationale**: Security consistency; prevent writes outside project directory

**Q6: Subdirectory creation?**
- **Answer**: B - Auto-create subdirectories
- **Rationale**: Convenience; common CLI pattern

---

**Specification Complete**: 2026-01-02
**Location**: `docs/plans/012-save-to-file/save-to-file-spec.md`
