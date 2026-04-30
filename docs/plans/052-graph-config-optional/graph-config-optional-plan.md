# Config UX Cleanup Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-04-30
**Spec**: [graph-config-optional-spec.md](./graph-config-optional-spec.md)
**Research**: [research-dossier.md](./research-dossier.md)
**Workshops**:
- [001-test-isolation-for-config-service.md](./workshops/001-test-isolation-for-config-service.md) — hermetic test patterns + worked examples for T002-T005
**Issues**: [#14](https://github.com/AI-Substrate/flow_squared/issues/14), [#15](https://github.com/AI-Substrate/flow_squared/issues/15)
**Branch**: `052-graph-config-optional`
**Status**: DRAFT

---

## Summary

Two recently filed issues report config-UX footguns: (#14) MCP `tree`/`search`/`get_node` raise `Missing configuration: GraphConfig` if `.fs2/config.yaml` lacks an optional `graph:` block, and (#15) docs/validator messages mislead Azure users about safe `batch_size` values. Fix is three one-line code swaps (mirroring an existing pattern already used in two sibling services), an addition to the `fs2 init` template, and clarifying edits across two `configuration-guide.md` copies plus `mcp-server-guide.md`.

## Target Domains

No formal domain registry exists in this codebase. Logical areas:

| Logical Area | Status | Relationship | Role |
|---|---|---|---|
| Config models (`src/fs2/config/`) | existing | **modify** | Update validator message + comment text in `EmbeddingConfig` docstring/example; `GraphConfig` itself unchanged |
| Graph-using services (3 files) | existing | **modify** | Swap `config.require(GraphConfig)` → `config.get(GraphConfig) or GraphConfig()` |
| Init template (`src/fs2/cli/init.py`) | existing | **modify** | Emit `graph:` block in `DEFAULT_CONFIG` |
| User documentation | existing | **modify** | New "Graph Configuration" section + 2 troubleshooting rows + clearer `batch_size` comments |

## Domain Manifest

| File | Domain | Classification | Rationale |
|---|---|---|---|
| `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/config/service.py` | config | internal | Add auto-registration of default-constructed `GraphConfig()` in `_create_config_objects` when `graph:` YAML key is absent — single mechanism, rule-compliant |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/services/tree_service.py` | services | internal | No code change needed once auto-registration lands — service already uses `require(GraphConfig)`. *(Validate via test T004.)* |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/services/get_node_service.py` | services | internal | Same — no code change; validate via T005 |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/services/graph_utilities_service.py` | services | internal | Same — no code change; validate via T006 |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/services/graph_service.py` | services | internal | Optional realignment: `config.get(GraphConfig) or GraphConfig()` → `config.require(GraphConfig)` (per finding 08) |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/cli/scan.py` | cli | internal | Optional realignment: same pattern fix (per finding 08) |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/cli/init.py` | cli | internal | Add `graph:` block to `DEFAULT_CONFIG` (uncommented) |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/config/objects.py` | config | internal | Lines 713/720/735: clarify `batch_size` text; lines 800-804: clearer validator message |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/docs/configuration-guide.md` | docs | contract | New "Graph Configuration" section; clarify `batch_size` comment line 449; troubleshooting row |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/docs/mcp-server-guide.md` | docs | contract | Add troubleshooting row for `Missing configuration: GraphConfig` |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/docs/how/user/configuration-guide.md` | docs | contract | Replicate "Graph Configuration" section + `batch_size` comment fix at line 430 |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/config/test_configuration_service.py` | tests | internal | New test: when YAML omits `graph:`, `config.require(GraphConfig)` succeeds and returns `GraphConfig()` defaults |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/services/test_tree_service.py` | tests | internal | New test: `TreeService` works against config loaded from YAML with no `graph:` block (integration-style, validates auto-registration end-to-end) |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/services/test_get_node_service.py` | tests | internal | Same for `GetNodeService` |
| `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/services/test_graph_utilities_service.py` | tests | internal | Same for `GraphUtilitiesService` |

## Complexity (revised after validation)

- **Score**: CS-2 (small) — was CS-1, bumped after validation
- **Breakdown**: S=2, I=0, D=0, N=0, F=0, T=1 → P=3 → CS-2
- **Rationale for bump**: T001 introduces a generalized auto-registration mechanism (`_AUTO_DEFAULT_CONFIGS` list + post-loop registration logic) in `FS2ConfigurationService` — this is a new pattern, not a one-line swap, and surface area touches the central config-loading pipeline.

## Key Findings

| # | Impact | Finding | Action |
|---|---|---|---|
| 01 | High | Three services use `config.require(GraphConfig)` directly while two siblings (`scan.py:145`, `graph_service.py:180`) use `config.get(GraphConfig) or GraphConfig()`. **Rule R3.2 / Constitution P3** says "Components MUST call `config.require(TheirConfigType)` internally" — the permissive fallback in `scan.py` / `graph_service.py` already violates this rule, but replicating it would entrench the violation | Make `GraphConfig` truly optional at the config-loading layer, NOT at each consumer. `FS2ConfigurationService` auto-registers a default-constructed `GraphConfig()` when no `graph:` YAML key is present. Then all 5 services use `config.require(GraphConfig)` cleanly — rule-compliant, no deviation needed |
| 02 | High | `GraphConfig.graph_path` defaults to `.fs2/graph.pickle` (`config/objects.py:198`) — every field has a default | Default-construction is safe — `GraphConfig()` is a valid instance |
| 03 | Medium | Comment "max 2048" appears in 3 doc files; validator at `config/objects.py:800-804` enforces 2048 cap but doesn't mention 300k token-per-request limit | Update all 4 locations with clarified text |
| 04 | Medium | Two `configuration-guide.md` copies have drifted (`src/fs2/docs/` is newer by ~3 weeks, 19 lines); rules declare `src/fs2/docs/` canonical | Master edits in canonical, replicate to drifted copy; do NOT close the broader drift in this plan |
| 05 | Medium | **Rule R4.3** mandates every test docstring include Purpose + Quality Contribution; SHOULD include Contract, Usage Notes, Worked Example | New regression tests T004/T005/T006 MUST include full Test Doc blocks |
| 06 | Low | `--graph-file` CLI flag exists (`cli/scan.py:134-137`) — confirmed during research | Reference it in the new doc section |
| 07 | Low | The `fs2 init` template uses commented-out blocks for `llm:` (Ollama) — keep consistency, but `graph:` has no setup requirement so emit it uncommented with the default value visible | Add `graph:` block as **uncommented** (no setup required) |
| 08 | Low | Existing `scan.py:145` and `graph_service.py:180` violate R3.2 today; this plan can opportunistically realign them when the auto-registration mechanism is in place (zero behavior change, just cleaner code) | Optionally update both to `config.require(GraphConfig)` once auto-registration lands |

## Implementation

**Objective**: Land the smallest correct fix that closes #14 and #15 with regression coverage.

**Testing Approach**: Lightweight — one regression test per fixed service (3 total) confirming fallback to `GraphConfig()` defaults when no `graph:` section is present. No mocks. Mirror existing test patterns in those files. **See [workshop 001](./workshops/001-test-isolation-for-config-service.md) for the canonical hermetic test pattern, decision tree (real loader vs fake), proposed `make_project_config` fixture, and worked examples for each test task.**

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|---|---|---|---|---|---|---|
| [x] | T001 | In `FS2ConfigurationService._create_config_objects()`, after the existing loop, auto-register a default-constructed `GraphConfig()` if none was loaded from YAML. Use a small declarative list `_AUTO_DEFAULT_CONFIGS = [GraphConfig]` so the mechanism is generalizable. **Contract**: iterate `_AUTO_DEFAULT_CONFIGS` in declaration order; explicit YAML registration always wins (because it happens earlier in the loop and `set()` is idempotent by type); duplicates not expected | config | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/config/service.py` | After load, `config.get(GraphConfig)` returns a valid `GraphConfig()` instance even when no `graph:` YAML key exists; existing behavior (when `graph:` IS specified) unchanged | Per finding 01 — rule-compliant fix at the loader, not at consumers |
| [x] | T002 | Add unit test for the auto-registration mechanism: `FS2ConfigurationService` loaded from YAML with no `graph:` block → `config.require(GraphConfig)` returns `GraphConfig(graph_path=".fs2/graph.pickle")` (defaults). Test docstring MUST include Purpose + Quality Contribution per R4.3 | tests | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/config/test_configuration_service.py` | Test passes; existing config-service tests still pass | |
| [x] | T003 | Add regression test: `TreeService` initialized with a `ConfigurationService` whose YAML has no `graph:` block → service initializes successfully via `config.require(GraphConfig)` and uses default `graph_path`. Test docstring MUST include full Test Doc block (Purpose, Quality Contribution, Contract, Worked Example) per R4.3 | tests | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/services/test_tree_service.py` | Test passes; existing tests still pass | Mirror existing patterns in this file; use `FakeConfigurationService` (no mocks per R4.2) |
| [x] | T004 | Same regression test for `GetNodeService` with full Test Doc block. **Discovery during impl: existing negative test in `test_get_node_service.py:106-121` uses `FakeConfigurationService` — no auto-reg there — so it continues to pass and validates a useful R3.2 contract. Kept it; clarified docstring; added new positive integration test alongside.** | tests | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/services/test_get_node_service.py` | New regression test passes; existing negative test passes (different layer) | Per validation finding H1 — finding was overcautious; both tests coexist usefully |
| [x] | T005 | Same regression test for `GraphUtilitiesService` with full Test Doc block. No existing negative test to sweep | tests | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/services/test_graph_utilities_service.py` | New test passes; no orphan negative-path tests remain | |
| [x] | T006 | Optional realignment (per finding 08): change `cli/scan.py:145` and `core/services/graph_service.py:180` from `config.get(GraphConfig) or GraphConfig()` → `config.require(GraphConfig)`. Zero behavior change; just rule-compliant. Skip if any test fails specifically on the existing pattern | services / cli | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/cli/scan.py`, `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/services/graph_service.py` | Both files use `config.require(GraphConfig)`; full test suite passes | Per finding 08 — opportunistic cleanup |
| [x] | T007 | Add `graph:` block to `DEFAULT_CONFIG` in `fs2 init` template. **Placement: directly after the `scan:` block and BEFORE the commented LLM blocks** (`src/fs2/cli/init.py:18-46`). Uncommented, with default value visible | cli | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/cli/init.py` | `DEFAULT_CONFIG` contains `graph:\n  graph_path: ".fs2/graph.pickle"` block immediately after `scan:` and before the `# ─── LLM` separator; running `fs2 init` in a fresh dir produces a config that includes this | Per finding 07 + validation finding M2. **Discovery during impl: `init.py` has TWO templates — `DEFAULT_CONFIG` (global ~/.config/fs2) and `PROJECT_CONFIG` (./.fs2). Added the `graph:` block to `PROJECT_CONFIG` only since `graph_path` is fundamentally project-local.** |
| [x] | T008 | Update `EmbeddingConfig` docstring + YAML example + validator error message to name the **300k tokens-per-request** Azure limit | config | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/config/objects.py` | Lines 713, 720, 735 mention 300k token cap; validator message at 800-804 names both item-count cap and token-per-request cap; existing `validate_batch_size` test still passes (or string-asserting test is updated for new wording) | Per finding 03; sweep file for any other "max 2048" references |
| [x] | T009 | Add new "Graph Configuration" section to canonical `configuration-guide.md` (with YAML schema, env-var form `FS2_GRAPH__GRAPH_PATH`, relationship to `--graph-file` CLI flag); update `batch_size` comment at line 449; add troubleshooting rows for both `Missing configuration: GraphConfig` and the 300k-token 400 error | docs | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/docs/configuration-guide.md` | Section exists; ToC updated; comment at line ~449 names 300k limit and recommends 16-50 for code embeddings; both troubleshooting rows present | Per finding 04 — this is the master edit |
| [x] | T010 | Replicate the same edits in the drifted `configuration-guide.md` copy (do NOT attempt to close the broader 19-line drift) | docs | `/Users/jordanknight/substrate/fs2/048-better-documentation/docs/how/user/configuration-guide.md` | Same "Graph Configuration" section, same `batch_size` comment fix, same troubleshooting rows present | Per finding 04 |
| [x] | T011 | Add troubleshooting row to `mcp-server-guide.md` for `Missing configuration: GraphConfig` error (note: with auto-registration the error becomes far less likely, but document it for older fs2 versions) | docs | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/docs/mcp-server-guide.md` | Row appears in MCP troubleshooting table | |
| [x] | T012 | Run full test suite; verify no regressions | tests | (whole repo) | `pytest` exits 0 with no new failures | **Result: 2066 passed, 14 pre-existing failures (all confirmed pre-existing on main via git stash). Zero regressions from this plan.** |

### Acceptance Criteria

- [ ] AC1: Fresh `fs2 init` → MCP `tree(pattern=".", max_depth=1)` succeeds without `Missing configuration: GraphConfig` error.
- [ ] AC2: Config with every section EXCEPT `graph:` → MCP `tree`, `search`, `get_node` all succeed using the default graph path.
- [ ] AC3: Existing config with `graph:` block continues to work unchanged.
- [ ] AC4: `fs2 init` output contains a visible `graph:` block with default `graph_path`.
- [ ] AC5: `src/fs2/docs/configuration-guide.md` has a "Graph Configuration" section showing YAML schema, env-var form, and `--graph-file` flag relationship.
- [ ] AC6: Both troubleshooting tables (configuration-guide and mcp-server-guide) include rows for `Missing configuration: GraphConfig` and the Azure 300k-token 400 error.
- [ ] AC7: Three locations (config/objects.py x3 + 2 doc files) name the 300k-tokens-per-request Azure limit; recommended `batch_size` range is suggested for code embeddings.
- [ ] AC8: Validator error for out-of-range `batch_size` mentions both caps.
- [ ] AC9: All existing tests pass; 4 new regression tests cover (a) auto-registration mechanism in `FS2ConfigurationService` and (b) the fallback path for the 3 services that need it.
- [ ] AC10: All graph-using services use `config.require(GraphConfig)` per Rule R3.2 / Constitution P3 — no service uses the `config.get(...) or X()` pattern.
- [ ] AC11: All new test docstrings include Purpose + Quality Contribution per R4.3 (and SHOULD include Contract / Worked Example).

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Existing test asserts `Missing configuration: GraphConfig` raises (testing the wrong behavior) | Low | Low | Run full test suite; if such a test exists, update it to assert fallback behavior |
| Other consumer of `config.require(GraphConfig)` exists outside the 3 identified services | Low | Medium | Final grep sweep before merging: `rg "require.*GraphConfig"` |
| `validate_batch_size` test asserts exact wording of validator message | Low | Low | Check test, update string if needed (cosmetic) |
| New "Graph Configuration" doc section formatted inconsistently with surrounding sections in the drifted copy | Low | Low | Match the exact heading style and ToC pattern of the canonical copy |

---

**Next step**: Run `/plan-4-v2-complete-the-plan` to validate readiness, then `/plan-6-v2-implement-phase --plan "<this file>"` to execute.

---

## Validation Record (2026-04-30)

| Agent | Lenses Covered | Issues | Verdict |
|-------|---------------|--------|---------|
| val-coherence | System Behavior, Hidden Assumptions, Edge Cases & Failures, Integration & Ripple | 1 HIGH fixed, 1 MEDIUM (subsumed) | ⚠️ → ✅ |
| val-completeness | User Experience, Technical Constraints, Deployment & Ops, Domain Boundaries, Concept Documentation | 1 MEDIUM fixed (CS bump), 1 MEDIUM fixed (init placement), 1 LOW skipped (stdout msg) | ⚠️ → ✅ |
| val-forward | Forward-Compatibility, Performance & Scale, Security & Privacy | 1 MEDIUM fixed (test path), 1 LOW fixed (extensibility note) | ⚠️ → ✅ |

**Lens coverage**: 12/12 (above the 8-floor). Forward-Compatibility engaged (downstream consumers exist; not STANDALONE).

### Forward-Compatibility Matrix

| Consumer | Requirement | Failure Mode | Verdict | Evidence |
|----------|-------------|--------------|---------|----------|
| `/plan-6` implementer | complete task list with correct paths | shape mismatch | ✅ (post-fix) | T002 path corrected to `test_configuration_service.py` |
| PR review for #14 #15 | ACs map to issue reproductions | contract drift | ✅ | AC1-4 cover #14, AC6-8 cover #15, AC9-11 cover regressions/rule alignment |
| Future agents | rationale captured | encapsulation lockout | ✅ | Findings 01 + 08 explain rule-compliance reasoning; auto-reg mechanism contract documented in T001 |
| `_AUTO_DEFAULT_CONFIGS` extensibility | future configs can join cleanly | shape mismatch | ✅ (post-fix) | T001 now states ordering / override / no-duplicates contract |
| Existing fs2 commands | zero-change for explicit configs | contract drift | ✅ | `set()` is type-keyed and overwrite-safe (`service.py:419-421`); explicit YAML wins |

**Outcome alignment**: The plan advances "Make fs2's configuration UX honest and forgiving for two specific footguns: (1) the `graph:` section becomes truly optional everywhere it's consumed, and (2) the `batch_size` documentation/validator stops misleading Azure users about what value is actually safe."

**Standalone?**: No — five downstream consumers named with concrete needs.

**Fixes applied**:
- HIGH H1: T004 now explicitly updates `test_get_node_service.py:106-121` (the existing `test_given_missing_graph_config_when_created_then_raises` would break after T001); T005 sweeps `test_graph_utilities_service.py` for similar tests.
- MEDIUM M1: CS bumped CS-1 → CS-2 (S=1→2 due to generalized auto-reg mechanism).
- MEDIUM M2: T007 now pins `graph:` block placement (after `scan:`, before LLM blocks).
- MEDIUM M3: T002 path corrected `test_service.py` → `test_configuration_service.py` (also updated in manifest).
- LOW L1: T001 now includes the `_AUTO_DEFAULT_CONFIGS` extensibility contract (ordering / override / duplicates).
- LOW L2 (skipped per "keep it simple"): No new stdout message in `fs2 init` — visible block in generated YAML is sufficient.

**Overall**: ⚠️ VALIDATED WITH FIXES — ready for `/plan-6-v2-implement-phase`.
