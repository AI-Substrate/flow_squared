# Research: Config UX cleanup — Issues #14 and #15

**Generated**: 2026-04-30
**Branch**: `052-graph-config-optional`
**Issues**:
- [#14](https://github.com/AI-Substrate/flow_squared/issues/14) — `graph` config section required by MCP tools but undocumented
- [#15](https://github.com/AI-Substrate/flow_squared/issues/15) — `batch_size` max 2048 comment is misleading (token-per-request limit hits first)

**Mode**: Targeted (kept simple per user request)

---

## Problem

MCP `tree` / `search` / `get_node` fail with `Missing configuration: GraphConfig` if `.fs2/config.yaml` lacks a `graph:` section, even though every field on `GraphConfig` has a default. `list_graphs()` works fine on the same config. `fs2 init` doesn't emit a `graph:` block by default, so every project hits this footgun until the user reads the Python source.

## Root Cause (confirmed)

Inconsistent pattern across services that consume `GraphConfig`:

| File | Line | Pattern | Outcome |
|---|---|---|---|
| `cli/scan.py` | 145 | `config.get(GraphConfig) or GraphConfig()` | ✅ works without `graph:` |
| `core/services/graph_service.py` | 180 | `config.get(GraphConfig) or GraphConfig()` | ✅ works without `graph:` |
| `core/services/graph_utilities_service.py` | 107 | `config.require(GraphConfig)` | ❌ raises if missing |
| `core/services/tree_service.py` | 125 | `config.require(GraphConfig)` | ❌ raises if missing |
| `core/services/get_node_service.py` | 77 | `config.require(GraphConfig)` | ❌ raises if missing |

Two services use the right pattern; three use `require()` and explode. `GraphConfig` itself (`src/fs2/config/objects.py:177-198`) defines `graph_path: str = ".fs2/graph.pickle"` — a complete default — so `require()` is the wrong primitive here.

`fs2 init` template (`src/fs2/cli/init.py:18-32`) emits sections for `scan`, `llm`, `smart_content`, `embedding` — no `graph:` block.

## Scope (kept simple)

**In scope** — just enough to close the issue:
1. Make `GraphConfig` truly optional in the 3 broken services (mirror the working pattern).
2. Add `graph:` block to the `fs2 init` template (so newly-init'd projects show users the schema).
3. Add a "Graph Configuration" section to `configuration-guide.md`.
4. Add the error to the MCP troubleshooting table in `mcp-server-guide.md`.

**Out of scope**:
- Refactoring `ConfigurationService.require()` semantics globally
- Auto-default behavior for other configs (LLM, embedding, etc. — those genuinely require user input)
- Validating `graph_path` exists at startup (separate concern)

## Implementation Sketch

**Code change** — 3 one-line replacements, identical pattern:
```python
# Before
self._config = config.require(GraphConfig)

# After
self._config = config.get(GraphConfig) or GraphConfig()
```

In:
- `src/fs2/core/services/graph_utilities_service.py:107`
- `src/fs2/core/services/tree_service.py:125`
- `src/fs2/core/services/get_node_service.py:77`

Update accompanying docstrings (`config.require(GraphConfig)` mentioned at lines 101, 119, 71) so they match the new behavior.

**Init template** — add to `src/fs2/cli/init.py` `DEFAULT_CONFIG`:
```yaml
# ─── Graph (optional - defaults shown) ────────────────────────────
graph:
  graph_path: ".fs2/graph.pickle"
```

**Docs**:
- `src/fs2/docs/configuration-guide.md`: new "Graph Configuration" section + ToC entry
- `src/fs2/docs/mcp-server-guide.md`: add row to troubleshooting table for `Missing configuration: GraphConfig`

## Tests

Existing tests should still pass (the change is permissive, not restrictive). Add one test per broken service that constructs the service with a `ConfigurationService` containing **no** `graph:` section and asserts it falls back to defaults — mirrors the existing tests for `scan.py` / `graph_service.py`.

Look for existing test patterns in:
- `tests/unit/services/test_tree_service.py`
- `tests/unit/services/test_get_node_service.py`
- `tests/unit/services/test_graph_utilities_service.py`

## Risks

**Very low**:
- Pattern is already used by `scan.py` and `graph_service.py` — no new code paths.
- All `GraphConfig` fields default to safe values (relative path).
- Behavior change is strictly additive: configs that **had** a `graph:` section keep working unchanged; configs that **lacked** it now also work.
- No public API change.

## Files To Touch

| File | Change |
|---|---|
| `src/fs2/core/services/graph_utilities_service.py` | swap `require` → `get(...) or GraphConfig()` (line 107) + docstring |
| `src/fs2/core/services/tree_service.py` | same (line 125) + docstring |
| `src/fs2/core/services/get_node_service.py` | same (line 77) + docstring |
| `src/fs2/cli/init.py` | add `graph:` block to `DEFAULT_CONFIG` |
| `src/fs2/docs/configuration-guide.md` | new "Graph Configuration" section + ToC + troubleshooting row |
| `src/fs2/docs/mcp-server-guide.md` | troubleshooting row |
| `tests/unit/services/test_tree_service.py` | regression test |
| `tests/unit/services/test_get_node_service.py` | regression test |
| `tests/unit/services/test_graph_utilities_service.py` | regression test |

---

---

# Issue #15 — `batch_size` 2048 misleading

## Problem

Comment says `(max 2048)` — implying that's a safe upper bound. Azure OpenAI actually enforces a **300,000 tokens per request** limit which is hit much sooner. With code chunks averaging ~400 tokens each, `batch_size: 2048` × 400 ≈ 819k tokens → Azure rejects with 400.

## Root Cause

Two issues:
1. **Misleading comments/docs/validator messages** that say "max 2048" without flagging the token cap.
2. **Fixed-count batching** — `_collect_batches()` (`src/fs2/core/services/embedding/embedding_service.py:596-603`) splits purely by item count; doesn't consider token totals per batch.

## Locations of misleading text

| File | Line | Current text |
|---|---|---|
| `src/fs2/config/objects.py` | 713 | `(default: 16, max: 2048 for Azure)` |
| `src/fs2/config/objects.py` | 720 | `Azure max is 2048.` |
| `src/fs2/config/objects.py` | 735 | `# Texts per API call (max 2048 for Azure)` |
| `src/fs2/config/objects.py` | 800-804 | Validator: `batch_size must be <= 2048 (Azure API limit)` |
| `src/fs2/docs/configuration-guide.md` | 449 | `# Texts per API call (max 2048)` |
| `docs/how/user/configuration-guide.md` | 430 | (mirror of above) |

## Scope (kept simple — doc fix only)

**In scope**:
1. Update all six locations above with a clearer comment that names the **300k token-per-request limit** and recommends keeping `batch_size` low (16-50) for code chunks.
2. Update validator error message to mention both limits (item count cap *and* token-per-request cap).
3. Add a troubleshooting row to `configuration-guide.md` for the 400 "maximum request size is 300000 tokens" error.

**Out of scope (logged as follow-up)**:
- Token-aware batching in `_collect_batches()` — would auto-split a configured `batch_size` into sub-batches that fit under 300k tokens. `ChunkItem` already carries token counts, so this is feasible but a behavior change worth its own plan.

## Files To Touch (#15)

| File | Change |
|---|---|
| `src/fs2/config/objects.py` | clarify comments at 713/720/735, update validator message at 800-804 |
| `src/fs2/docs/configuration-guide.md` | clarify `batch_size` comment at 449, add troubleshooting row |
| `docs/how/user/configuration-guide.md` | mirror — at 430 |

## Risk (#15)

Zero — pure doc/comment changes. Validator message change is cosmetic.

---

**Next step**: skip straight to implementation since combined scope is still tiny (~9 files, all small edits).
