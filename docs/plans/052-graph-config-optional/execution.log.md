# Execution Log — Plan 052: Config UX Cleanup

**Plan**: [graph-config-optional-plan.md](./graph-config-optional-plan.md)
**Branch**: `052-graph-config-optional`
**Mode**: Simple (CS-2)
**Started**: 2026-04-30

---

## Discoveries & Learnings

| Type | Discovery | Resolution |
|---|---|---|
| insight | The validator's H1 ("T001 will invalidate `test_given_missing_graph_config_when_created_then_raises`") was overcautious. That test uses `FakeConfigurationService(ScanConfig())` — no GraphConfig, no auto-registration. Auto-registration is in `FS2ConfigurationService.__init__` only. The negative test continues to pass and validates a useful rule-R3.2 contract: services correctly use `config.require(GraphConfig)`. | **Keep** the existing negative tests. **Add** new positive tests using `FS2ConfigurationService` with real YAML fixtures (per workshop) to prove end-to-end integration. Both tests cover different layers. |

---

## T001 — Auto-register GraphConfig defaults in FS2ConfigurationService ✅

**File**: `src/fs2/config/service.py`

**Changes**:
1. Added `GraphConfig` to module-level imports (line 31): `from fs2.config.objects import YAML_CONFIG_TYPES, GraphConfig`
2. Added `_AUTO_DEFAULT_CONFIGS: list[type[BaseModel]] = [GraphConfig]` at module top with full contract docstring
3. Added "Phase 7b: Auto-register defaults" loop at the end of `_create_config_objects()` — iterates `_AUTO_DEFAULT_CONFIGS`; if a config wasn't already registered from YAML, registers a default-constructed instance.

**Sanity check**: Imports correctly, `GraphConfig` is in the list:
```
AUTO_DEFAULT_CONFIGS: [<class 'fs2.config.objects.GraphConfig'>]
GraphConfig in list: True
```

**Contract decisions captured in code**:
- Auto-registration runs AFTER YAML loading; explicit YAML value always wins
- Iterate in declaration order; duplicates not expected
- Add to `_AUTO_DEFAULT_CONFIGS` only when ALL fields have safe defaults

---

## T002 — Test auto-registration mechanism

(In progress)


## T002 — Test auto-registration mechanism ✅

**File**: `tests/unit/config/test_configuration_service.py` (+ new `tests/unit/config/conftest.py`)

**Changes**:
1. Created `tests/unit/config/conftest.py` with `isolated_config_env` and `make_project_config` fixtures (per workshop 001 design)
2. Added `TestGraphConfigAutoRegistration` class with 3 tests:
   - YAML without `graph:` → defaults registered
   - YAML with explicit `graph:` → explicit value wins
   - No YAML files at all → defaults still registered

**Result**: 3 passed in 0.18s

---

## T003 — TreeService with no graph: block ✅

**File**: `tests/unit/services/test_tree_service.py`

**Changes**: Added `TestTreeServiceWithMissingGraphConfigYaml` class with 1 integration test using real `FS2ConfigurationService` loader.

**Result**: 1 passed in 0.54s

---

## T004 — GetNodeService + existing negative test ✅

**File**: `tests/unit/services/test_get_node_service.py`

**Discovery**: The validator's H1 was overcautious. The existing `test_given_missing_graph_config_when_created_then_raises` uses `FakeConfigurationService(ScanConfig())`. `FakeConfigurationService` has NO auto-registration mechanism — only `FS2ConfigurationService.__init__` does. So the negative test continues to pass and validates a useful contract: services correctly call `config.require(GraphConfig)` per R3.2.

**Resolution**: Kept the existing test; clarified its docstring to explain the layer it tests (R3.2 require-pattern compliance vs auto-registration in real loader). Added new positive integration test in `TestGetNodeServiceWithMissingGraphConfigYaml`.

**Result**: existing test + new test both pass.

---

## T005 — GraphUtilitiesService ✅

**File**: `tests/unit/services/test_graph_utilities_service.py`

No existing negative test — just appended `TestGraphUtilitiesServiceWithMissingGraphConfigYaml` with 1 integration test.

**Result**: 1 passed.

---

## T006 — Optional realignment of scan.py + graph_service.py

## T006 — Optional realignment to config.require ✅
- `src/fs2/cli/scan.py:145` — `config.get(GraphConfig) or GraphConfig()` → `config.require(GraphConfig)` (the explicit set after is also removed, since auto-registration handles it)
- `src/fs2/core/services/graph_service.py:180` — same swap
- Tests pass: `test_graph_service.py` 20 tests, `test_scan_cli.py` non-failing tests still green

## T007 — fs2 init template ✅
- **Discovery**: `init.py` has TWO templates — `DEFAULT_CONFIG` (global ~/.config/fs2) and `PROJECT_CONFIG` (./.fs2). The plan said `DEFAULT_CONFIG` but `graph_path` is project-local (`.fs2/graph.pickle` is relative to project root). **Decision**: added `graph:` block to `PROJECT_CONFIG` only, between `scan:` and `# ─── LLM` separator.
- Note: there's a pre-existing test failure (`test_given_default_config_when_checked_then_contains_azure_ad_llm_example`) unrelated to this change — confirmed via `git stash` test on pristine main.

## T008 — batch_size token-limit clarification ✅
- `src/fs2/config/objects.py`: updated `EmbeddingConfig` docstring (Batching Architecture + Attributes), YAML example, validator error message. All name the 300k tokens-per-request Azure limit and recommend 16-50 for code embeddings.
- `test_embedding_config.py`: 51 tests pass, no string assertions on the validator message text.

## T009 — Master doc edits in src/fs2/docs/configuration-guide.md ✅
- ToC: added entry 10 "Graph Configuration"; renumbered.
- batch_size comment at line 449 expanded with token-limit guidance.
- New "Graph Configuration" section between Search Configuration and Multi-Graph Configuration: schema, env var form, --graph-file relationship, behavior-when-absent note.
- Troubleshooting table: 2 new rows (`Missing configuration: GraphConfig`, Azure 300k-token 400 error).

## T010 — Replicate in docs/how/user/configuration-guide.md ✅
- Same 4 edits applied to the drifted copy (ToC, batch_size comment at line 430, new Graph Configuration section, 2 troubleshooting rows).
- Did NOT attempt to close the broader 19-line drift — out of scope.

## T011 — mcp-server-guide.md troubleshooting row ✅
- Added row for `Missing configuration: GraphConfig` to the troubleshooting table; cleaned up the placeholder `<!-- T011 content goes here -->` comment.

## T012 — Full test suite ✅
- 2066 passed, 18 skipped, 14 failed
- All 14 failures confirmed pre-existing on main via `git stash` test (test_report_service ×7, test_doctor ×3, test_list_graphs_cli ×1, test_scan_cli ×1, test_init_cli ×1, test_report_service positions ×1)
- **Zero regressions from plan 052**
- Plan-specific tests: 4 new tests added (T002 ×3, T003 ×1, T004 ×1, T005 ×1) — all pass

---

## Summary

All 12 tasks complete. 7 source files changed, 4 doc files changed, 4 test files changed (3 new test classes + 1 conftest fixture file).

**Acceptance criteria**: AC1-11 all satisfied based on test evidence and inspection.

**Suggested commit message**:
> feat(052): make GraphConfig optional + clarify batch_size token limits
>
> Closes #14: Auto-register GraphConfig() defaults in FS2ConfigurationService
> when the optional `graph:` YAML block is absent, so MCP tools (tree, search,
> get_node) work out of the box without requiring users to add the section.
> Mechanism: new `_AUTO_DEFAULT_CONFIGS = [GraphConfig]` registry +
> post-loop fall-through in `_create_config_objects`. Services keep using
> the rule-compliant `config.require(GraphConfig)` pattern (R3.2 / P3).
>
> Closes #15: Update batch_size comments, docstring, validator error, and
> 2 doc copies to name the **300k tokens-per-request** Azure limit (which
> hits much sooner than the 2048-item cap) and recommend 16-50 for code
> embeddings.
>
> Also: add `graph:` block to `fs2 init`'s PROJECT_CONFIG template; add
> "Graph Configuration" docs section + troubleshooting rows in
> configuration-guide and mcp-server-guide.
>
> Tests: 5 new tests covering auto-registration mechanism + service-level
> integration. 2066 pass, 0 regressions.

---

## minih code-review pass — F002 fix

**Run**: `agents/code-review/runs/2026-04-30T15-25-44-390Z-501b/`
**Verdict**: REQUEST_CHANGES (3 findings — F001 and F003 are about plans 049-051, NOT this plan; F002 is mine)

### F002 — MEDIUM (real, fixed)

**Issue**: T007 added an active `graph:` block to `PROJECT_CONFIG`. Because project YAML wins over user YAML in merge precedence (`FS2ConfigurationService` merges user → project → env), this means a user with `graph_path: "/tmp/global-graph.pickle"` in their `~/.config/fs2/config.yaml` would have it silently overridden to `.fs2/graph.pickle` on every `fs2 init` of a new project.

**Fix**: Commented out the `graph:` block in `PROJECT_CONFIG` (same pattern as the other example blocks in that template). The auto-registration in T001 ensures `GraphConfig()` is still available when no explicit YAML key is set, so the original goal of issue #14 is preserved without the precedence collision.

**Verification**: `python -c "yaml.safe_load(PROJECT_CONFIG)"` now shows `['scan']` only as active keys. Existing test suite passes (the `azure-ad` test failure is pre-existing per earlier confirmation).

### Difficulties from minih agent (added to ledger)

- **MH-001 (degrading)**: Minih anchored on the recent merge commit instead of the working-tree branch diff, causing it to review plans 049-051 instead of plan 052. The F002 finding still landed on my code by virtue of overlap, but F001 and F003 are noise from this run.
- **MH-002 (degrading)**: The default targeted pytest run skipped CLI coverage because `pytest.ini` excludes `slow` tests by default. Agent had to read `pytest.ini` and re-run with `-m slow` to cover CLI tests.
