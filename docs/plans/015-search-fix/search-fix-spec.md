# Glob Pattern Support for Search Filters

**Mode**: Simple

📚 *This specification incorporates findings from `research-dossier.md`*

## Research Context

| Aspect | Finding |
|--------|---------|
| **Components affected** | `src/fs2/cli/search.py`, new `pattern_utils.py` module |
| **Critical dependencies** | `fnmatch` (Python stdlib), `re` (already used) |
| **Modification risks** | Low - additive behavior, backward compatible |
| **Key discovery** | Node IDs use format `category:path/file.ext:Symbol`, so extensions appear before `:`, not at string end |
| **Architecture** | CLI and MCP share code paths: both use QuerySpec → SearchService → Matchers. Shared utility benefits both. |

See `research-dossier.md` for full analysis including code flow, test gaps, and implementation details.

## Summary

**WHAT**: Enable users to filter search results using familiar glob patterns (like `*.py`, `.gd`) in addition to regex patterns when using `--include` and `--exclude` options.

**WHY**: Users naturally expect glob patterns because they work everywhere else (shell, `.gitignore`, file explorers). Currently, `fs2 search --include "*.py"` crashes with a confusing regex error, and `--include ".gd"` silently matches wrong files. This violates the principle of least surprise and creates friction for the most common filtering use case: filtering by file extension.

## Goals

1. **Eliminate crashes**: `--include "*.py"` should work without requiring regex knowledge
2. **Correct matching**: `.gd` should only match `.gd` files, not files containing "gd" anywhere
3. **Support both file and symbol nodes**: Extension filters must work for both `file:path.py` and `callable:path.py:func`
4. **Preserve regex power**: Users who know regex can still use it (e.g., `.*test.*\.py$`)
5. **Update help text**: Clearly communicate that glob patterns are supported
6. **Zero breaking changes**: Existing regex patterns must continue working identically

## Non-Goals

1. **Full glob syntax**: No need for `**` recursive patterns or `{a,b}` alternation - basic `*`, `?`, `.ext` suffice
2. **Explicit mode flags**: No `--glob` vs `--regex` flags - auto-detection is sufficient
3. **QuerySpec changes**: Keep QuerySpec pure (regex-only); conversion happens in shared utility before QuerySpec construction
4. **Configuration options**: No settings to disable glob conversion
5. **Separate MCP implementation**: CLI and MCP share code paths (QuerySpec → SearchService), so glob conversion applies to both automatically

## Complexity

| Metric | Score | Rationale |
|--------|-------|-----------|
| **Score** | CS-2 (small) | Well-isolated change with clear boundaries |
| **Breakdown** | S=1, I=0, D=0, N=0, F=0, T=1 | |

**Dimension Details**:
- **S (Surface Area) = 1**: Multiple files (CLI, new utility, tests) but contained scope
- **I (Integration) = 0**: Internal only; `fnmatch` is Python stdlib
- **D (Data/State) = 0**: No schema or state changes
- **N (Novelty) = 0**: Well-specified from research; clear requirements
- **F (Non-Functional) = 0**: Standard requirements; no special perf/security needs
- **T (Testing/Rollout) = 1**: Integration tests needed for CLI behavior changes

**Total**: P = 2 → CS-2 (accounting for new module creation)

**Confidence**: 0.90 (high - research was thorough, solution is well-defined)

**Assumptions**:
- `fnmatch.translate()` produces correct regex for all common glob patterns
- Auto-detection heuristics (starts with `*`, matches `^\.\w+$`, contains `*` or `?`) are sufficient
- The `(?:$|:)` anchor handles all node ID formats

**Dependencies**: None external; uses Python stdlib only

**Risks**:
- Edge case patterns that look like glob but user intended as regex (mitigated by preserving regex pass-through)
- Future node ID format changes could break the `:` anchor assumption

**Phases**: Single phase implementation (CS-2 doesn't require staged rollout)

## Acceptance Criteria

### AC1: Glob patterns with `*` work correctly
**Given** a user runs `fs2 search "test" --include "*.py"`
**When** the search executes
**Then** only results with `.py` extension are returned (no crash, no regex error)

### AC2: Extension patterns work correctly
**Given** a user runs `fs2 search "test" --include ".gd"`
**When** the search executes
**Then** only `.gd` files are matched, not files containing "gd" elsewhere (e.g., `gdUnit4`)

### AC3: Symbol nodes are matched correctly
**Given** a search returns node IDs like `type:src/Foo.cs:FooClass`
**When** user filters with `--include ".cs"`
**Then** the node is included (extension appears before `:`, not at end)

### AC4: Regex patterns still work
**Given** a user runs `fs2 search "test" --include ".*test.*\.py$"`
**When** the search executes
**Then** the pattern is treated as regex and matches correctly

### AC5: Multiple patterns work with OR logic
**Given** a user runs `fs2 search "test" --include "*.py" --include "*.js"`
**When** the search executes
**Then** results include both `.py` AND `.js` files

### AC6: Exclude patterns work with glob
**Given** a user runs `fs2 search "test" --exclude "*.test.py"`
**When** the search executes
**Then** test files are excluded from results

### AC7: Help text is updated
**Given** a user runs `fs2 search --help`
**When** viewing the `--include`/`--exclude` options
**Then** the help text indicates glob patterns are supported (e.g., "glob like *.py or regex")

### AC8: Error messages are clear for invalid patterns
**Given** a user provides a pattern that is invalid as both glob and regex
**When** the search executes
**Then** a clear error message explains the issue

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pattern misclassification | Low | Medium | Regex pass-through preserves explicit regex; only obvious globs converted |
| Node ID format changes | Low | High | Document assumption; add integration tests for format |
| Performance overhead | Very Low | Low | Conversion is O(1) per pattern; negligible |

### Assumptions

1. Users primarily filter by file extension (most common use case)
2. Auto-detection heuristics cover 95%+ of real-world patterns
3. Node ID format `category:path:symbol` is stable
4. Backward compatibility is non-negotiable

## Open Questions

1. **Q**: Should the MCP `query` tool also support glob patterns?
   **A**: Yes - CLI and MCP already share code paths (QuerySpec → SearchService). Adding glob conversion before QuerySpec construction means both benefit automatically. No divergent paths allowed.

2. **Q**: Should we log when a pattern is converted from glob to regex (for debugging)?
   **A**: No - conversion is deterministic and transparent. If it works, users don't need to know. Error messages suffice for failures.

## Testing Strategy

**Approach**: Full TDD
**Rationale**: Existing search tests use a special `scanned_project` fixture with pre-processed graph representing online search as closely as possible. Reuse these patterns for glob support.

**Focus Areas**:
- `TestSearchIncludeExcludeOptions` class (test_search_cli.py:596-933) - extend with glob tests
- New `TestSearchGlobPatterns` class for dedicated glob conversion tests
- Integration tests using `scanned_project` fixture with real graph

**Key Test Fixtures**:
- `scanned_project` (conftest.py:266-341) - creates minimal project with scanned graph
- `scanned_fixtures_graph` - session-scoped real ast_samples graph
- Pattern: `monkeypatch.chdir(scanned_project)` + `runner.invoke(app, [...])`

**Test Pattern to Follow**:
```python
def test_given_CONDITION_when_COMMAND_then_RESULT(self, scanned_project, monkeypatch):
    """
    Purpose: [What it validates]
    Quality Contribution: [Why it matters]
    Acceptance Criteria: [What should happen]
    """
    from fs2.cli.main import app
    monkeypatch.chdir(scanned_project)
    monkeypatch.setenv("NO_COLOR", "1")
    result = runner.invoke(app, ["search", "pattern", "--include", "*.py"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    # assertions...
```

**Excluded**: Manual testing, E2E tests beyond CLI integration

**Mock Usage**: Avoid mocks - use fixtures and fakes per codebase convention
- Use `scanned_project` fixture with real pre-processed graphs
- Use `FakeGraphStore` for service-level tests (inherits from ABC)
- Basic redirections (monkeypatch for cwd, env vars) are acceptable
- No mock.patch or MagicMock usage

## Documentation Strategy

**Location**: None (no new documentation)
**Rationale**: The updated `--help` text (AC7) is the documentation. Glob patterns are self-explanatory and intuitive - users expect them to work.
**Target Audience**: CLI users discovering options via `--help`
**Maintenance**: Help text maintained with code

## ADR Seeds (Optional)

**Decision Drivers**:
- User expectation: glob patterns work everywhere else
- Backward compatibility: existing regex users must not break
- Simplicity: no new flags or configuration

**Candidate Alternatives**:
- A: Auto-detect and convert (proposed) - transparent to users
- B: Explicit `--glob`/`--regex` flags - more control but more friction
- C: Always treat as glob - breaks existing regex users

**Stakeholders**: CLI users, MCP tool consumers

## Clarifications

### Session 2026-01-02

| # | Question | Answer | Updated Sections |
|---|----------|--------|------------------|
| Q1 | Testing Strategy | Full TDD - reuse existing `scanned_project` fixture and test patterns | Testing Strategy |
| Q2 | Mock Usage | Avoid mocks - use fixtures and fakes per codebase convention | Testing Strategy |
| Q3 | Documentation Strategy | None - help text update (AC7) is sufficient | Documentation Strategy |
| Q4 | MCP Tool Scope | CLI and MCP share code paths; shared utility benefits both automatically | Open Questions, Non-Goals, Research Context |
| Q5 | Debug Logging | No logging - conversion is transparent | Open Questions |

**Coverage Summary**:
- **Resolved**: Testing Strategy, Mock Usage, Documentation Strategy, MCP Scope, Logging
- **Deferred**: None
- **Outstanding**: None - all critical ambiguities resolved

---

**Spec Created**: 2026-01-02
**Clarified**: 2026-01-02
**Plan Folder**: `docs/plans/015-search-fix/`
**Next Step**: Run `/plan-3-architect` to generate phase-based plan
