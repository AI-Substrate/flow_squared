# Config UX Cleanup — GraphConfig Optional + Batch Size Comments

**Mode**: Simple

📚 This specification incorporates findings from `research-dossier.md` (root-cause analysis of issues #14 and #15).

ℹ️ No domain registry exists; affected components live in `core/services/`, `cli/`, `config/`, and `docs/`.

## Testing Strategy

**Approach**: Lightweight — one regression test per fixed service (3 total) confirming fallback to `GraphConfig()` defaults when the `graph:` section is absent from the config.

**Rationale**: CS-1 trivial change; the fix mirrors a pattern already in use by `scan.py` and `graph_service.py`. Existing service tests cover the happy path. The only behavior gap currently uncovered is the absence-of-section fallback, which is the entire point of this fix — three small tests directly assert it.

**Focus Areas**:
- `tests/unit/services/test_tree_service.py` — assert `TreeService` initializes and operates with no `graph:` config block, falls back to `GraphConfig()`.
- `tests/unit/services/test_get_node_service.py` — same for `GetNodeService`.
- `tests/unit/services/test_graph_utilities_service.py` — same for `GraphUtilitiesService`.

**Mock Usage**: Avoid mocks. Use real `ConfigurationService` instances with no `graph:` section and a real `GraphStore` (or in-memory equivalent already used by sibling tests).

**Excluded**:
- New tests for `cli/init.py` template content (covered by manual verification — running `fs2 init` and inspecting the file).
- New tests for doc-only changes in `configuration-guide.md` / `mcp-server-guide.md`.

## Documentation Strategy

**Location**: `src/fs2/docs/configuration-guide.md` is the **canonical / newer source** (last touched 2026-04-08, shipped with the package, served via MCP `docs_get`, declared canonical in `docs/rules-idioms-architecture/rules.md:251`). `docs/how/user/configuration-guide.md` is stale (last touched 2026-03-16, ~19 lines behind).

For this plan:
- **Master edits land in `src/fs2/docs/configuration-guide.md`** — full new "Graph Configuration" section + `batch_size` comment fix + troubleshooting rows.
- **`docs/how/user/configuration-guide.md` gets the same edits** so users hitting it via `fs2 doctor`'s GitHub URLs (`cli/doctor.py:44-48`) see the fix. We do **not** attempt to close the broader 19-line drift between the two files in this plan.
- **`src/fs2/docs/mcp-server-guide.md`** gets the troubleshooting row for `Missing configuration: GraphConfig`.

**Rationale**: The two configuration-guide copies have drifted; resolving the duplication is out of scope for this small fix. The minimum viable update keeps users on either path informed about #14 and #15. Duplication logged as follow-up cleanup.

**Excluded**: `docs/plans/014-mcp-doco/doc-samples/configuration-guide.md` — frozen plan artifact, not live documentation.

---

## Research Context

Two recently filed issues (`#14`, `#15`) report related config-UX footguns:

- **#14**: MCP `tree`/`search`/`get_node` raise `Missing configuration: GraphConfig` if `.fs2/config.yaml` lacks a `graph:` section, even though every field on `GraphConfig` has a default. `list_graphs()` works fine on the same config. Three services use `config.require(GraphConfig)`; two sibling services already use the correct pattern `config.get(GraphConfig) or GraphConfig()`.
- **#15**: Comments and validator messages tell users `batch_size` can go up to 2048, but Azure OpenAI enforces a 300,000 token-per-request limit that hits much sooner. Setting `batch_size: 2048` causes 400 errors.

Research dossier confirmed scope is small: 3 one-line code swaps, doc edits in 6 locations, and one init-template addition.

## Summary

Make fs2's configuration UX honest and forgiving for two specific footguns: (1) the `graph:` section becomes truly optional everywhere it's consumed, and (2) the `batch_size` documentation/validator stops misleading Azure users about what value is actually safe.

## Goals

- A user who runs `fs2 init` then `fs2 scan` then wires fs2 into an MCP host gets working `tree`/`search`/`get_node` calls **without** having to add a `graph:` block by hand.
- A user reading config docs or the validator error sees a comment that names the **300k tokens-per-request** Azure limit and recommends a safe value range for code embeddings — not just the misleading "max 2048".
- An existing config with a `graph:` block continues to work unchanged.
- An existing config with a high `batch_size` continues to work unchanged (no behavior change — only documentation/error-text changes).
- The MCP server and CLI surfaces remain backward compatible.

## Non-Goals

- **Token-aware batching**: rewriting `_collect_batches()` to auto-split batches by token count is out of scope for this plan. Logged as a follow-up because it's a behavior change with its own design questions.
- **Refactoring `ConfigurationService.require()` semantics globally**: only the three specific call sites are changed. Other configs that genuinely require user input (LLM, embedding) keep using `require()`.
- **Auto-discovering / validating `graph_path` exists at startup**: separate concern; out of scope.
- **Enforcing a stricter `batch_size` upper bound**: the validator message is updated but the cap stays at 2048 (Azure's stated item-count cap).
- **Renaming or restructuring config fields**.

## Target Domains

No formal domain registry exists in this codebase. The change touches three logical areas:

| Logical Area | Status | Relationship | Role in This Feature |
|---|---|---|---|
| Configuration models (`src/fs2/config/`) | existing | **consume** | `GraphConfig` schema unchanged; comment + validator text updated |
| Graph-using services (`tree_service`, `get_node_service`, `graph_utilities_service`) | existing | **modify** | Switch from `config.require(GraphConfig)` → `config.get(GraphConfig) or GraphConfig()` |
| Init template (`src/fs2/cli/init.py`) | existing | **modify** | Emit `graph:` block in `DEFAULT_CONFIG` |
| User documentation (`src/fs2/docs/configuration-guide.md`, `mcp-server-guide.md`) | existing | **modify** | New "Graph Configuration" section + 2 troubleshooting rows + clearer `batch_size` comments |

## Complexity

- **Score**: CS-1 (trivial)
- **Breakdown**: S=1, I=0, D=0, N=0, F=0, T=1 → P=2 → CS-1
- **Confidence**: 0.95
- **Assumptions**:
  - The two-pattern split (`require` vs `get(...) or X()`) is genuinely an inconsistency, not an intentional design — confirmed because `scan.py` and `graph_service.py` already use the permissive pattern with no obvious issue.
  - All existing tests for the three modified services pass with the permissive pattern (no test asserts that absence of `graph:` raises).
- **Dependencies**: none; all changes are local to this repo.
- **Risks**:
  - A test somewhere may *intentionally* assert the `Missing configuration: GraphConfig` error path. If found, it should be updated to assert the fallback behavior.
  - A doc snippet elsewhere may copy-paste the misleading `(max 2048)` comment — sweep for it (already located 3 copies in the dossier).
- **Phases**:
  1. Code change (3 services + init template)
  2. Doc updates (#14 and #15 together)
  3. Regression tests (one per fixed service + sweep test for new init template)

## Acceptance Criteria

1. Given a fresh project where `fs2 init` has just been run and the user has **not** edited the generated `config.yaml`, when an MCP host calls `tree(pattern=".", max_depth=1)` against the fs2 MCP server, then the call returns the expected tree without raising `Missing configuration: GraphConfig`.
2. Given a config file that contains every other section (`scan`, `llm`, `smart_content`, `embedding`) but **no `graph:` block**, when MCP `tree`, `search`, or `get_node` is invoked, then each call succeeds and uses the default graph path `.fs2/graph.pickle`.
3. Given the existing config files in this repo (which **do** contain a `graph:` block), when the affected services run, then their behavior is unchanged from before this plan.
4. Given a fresh `fs2 init`, when the user opens the generated `.fs2/config.yaml`, then they see a `graph:` section with the default `graph_path` clearly shown (and a comment indicating it's optional).
5. Given the user reads `docs/how/user/configuration-guide.md`, when they look up "Graph Configuration", then they find a section showing the YAML schema, the env-var form (`FS2_GRAPH__GRAPH_PATH`), and the relationship to the `--graph-file` CLI flag.
6. Given the user reads `docs/how/user/mcp-server-guide.md`, when they hit the `Missing configuration: GraphConfig` error (in older fs2 versions), then the troubleshooting table tells them how to fix it.
7. Given the user reads any of the three `configuration-guide.md` copies (`src/fs2/docs/`, `docs/how/user/`, `docs/plans/014-mcp-doco/doc-samples/`), when they look at the Azure embedding example, then the `batch_size` comment names the 300k-token-per-request Azure limit (not just "max 2048") and suggests a safe value range for code embeddings.
8. Given a user sets `batch_size` to a value that makes Azure return the 300k-token error, when they search the troubleshooting table, then they find a row matching that error with a recommended fix.
9. Given a user submits an out-of-range `batch_size` (`< 1` or `> 2048`), when validation runs, then the error message clearly states both the item-count cap **and** the token-per-request consideration.
10. All existing tests still pass after the changes; new regression tests cover each of the three services in the absence of a `graph:` config block.

## Risks & Assumptions

- **Risk**: An undiscovered consumer of `GraphConfig` is using `config.require()` outside the three identified services. **Mitigation**: grep sweep before merging.
- **Risk**: A doc copy of the misleading comment lives in a place we haven't found. **Mitigation**: grep `"max 2048"` across the whole repo (already done in the dossier — 3 copies found).
- **Assumption**: The `--graph-file` CLI flag (mentioned in the issue's suggested fixes) does in fact exist. Needs a quick verification while writing the doc.

## Open Questions

- *None blocking.* The dossier surfaced all decisions needed to ship a small fix.

## Clarifications

### Session 2026-04-30

**Q1: Testing strategy?**
A: Lightweight — one regression test per fixed service (3 total) confirming fallback to `GraphConfig()` defaults when the `graph:` section is absent. Mocks avoided; existing test patterns mirrored. *Captured in `## Testing Strategy` above.*

**Q2: Which `configuration-guide.md` copies should the doc updates touch?**
A: Both `src/fs2/docs/configuration-guide.md` (canonical/newer — 2026-04-08, shipped with package) AND `docs/how/user/configuration-guide.md` (stale — 2026-03-16, but linked from `fs2 doctor`). Master edits land in canonical; same edits replicated in stale copy. We do NOT attempt to close the broader 19-line drift in this plan. The `docs/plans/014-mcp-doco/doc-samples/` copy is a frozen plan artifact and is excluded. Duplication noted as follow-up cleanup. *Captured in `## Documentation Strategy` above.*

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|---|---|---|---|

*No workshops required — scope is well-defined and small.*

---

**Next**: `/plan-2-v2-clarify` (likely a no-op given Open Questions is empty) → `/plan-3-v2-architect` for the lean implementation plan.
