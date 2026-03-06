# Code Review: Phase 5: Remote CLI + MCP Bridge

**Plan**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md
**Phase**: Phase 5: Remote CLI + MCP Bridge
**Date**: 2026-03-06
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

Phase 5 adds the core remote scaffolding, but the phase is not review-ready yet: remote tree/get-node/MCP parity are incomplete, the remotes config does not honor the promised user+project merge behavior, and the execution artifacts do not provide trustworthy verification evidence.

**Key failure areas**:
- **Implementation**: `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/tree.py`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/get_node.py`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/search.py`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py`, and `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/mcp/server.py` do not yet satisfy AC6-AC8 / AC12-AC13 parity requirements.
- **Domain compliance**: `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/get_node_service.py` is an undeclared scope addition, and the configuration/domain-map/plan artifacts still describe the superseded RemoteGraphStore design.
- **Reinvention**: named remotes repeat the `OtherGraphsConfig` pattern without extending the existing concatenate-on-merge helper in `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/config/service.py`.
- **Testing**: `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/execution.log.md` still says every task is pending and `Test Results` are "Not started"; no Phase 5 test files were added and no concrete command output is captured.
- **Doctrine**: `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/list_remotes.py` still swallows actionable configuration failures instead of surfacing them.

## B) Summary

Phase 5 clearly made real progress: named remotes, a reusable async `RemoteClient`, remote CLI branching, and partial MCP mixed-mode plumbing are all present. However, the current implementation still diverges from the approved Phase 5 dossier and the spec in material, user-visible ways. The biggest gaps are remote tree output parity, remote get-node/MCP contract parity, missing user+project remotes concatenation, and unsupported single-remote multi-graph search. On top of that, the planning/domain artifacts and execution evidence were not updated to match the code, so the phase cannot be approved with confidence (overall coverage confidence: 18%).

## C) Checklist

**Testing Approach: Hybrid**

For Hybrid:
- [ ] Core validation tests exist for RemoteClient/remotes config/MCP routing behavior
- [ ] Lightweight parity checks cover tree/search/get-node/list-graphs remote output
- [ ] Acceptance criteria AC6-AC13 are backed by concrete evidence

Universal (all approaches):
- [ ] Only in-scope files changed
- [ ] Linters/type checks clean (if applicable)
- [ ] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/tree.py:193-214 | correctness | Remote tree prints raw JSON in normal mode because neither the client nor the server implements the planned `format=text` parity path. | Add a true text-format parity path (or equivalent local rendering) and cover AC6 with direct remote-vs-local tests. |
| F002 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/config/service.py:38-41 | correctness | `RemotesConfig` did not extend the existing concatenate-on-merge helper, so user and project remotes shadow each other instead of combining as T001/R6 require. | Add `remotes.servers` to the merge support and regression-test mixed user/project remotes. |
| F003 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/get_node.py:69-88 | correctness | Remote get-node requests min detail and collapses all 404s into “node not found”, so AC8 parity and actionable graph errors are lost. | Request parity detail, distinguish graph vs node 404s, and normalize the remote payload to the local contract. |
| F004 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/mcp/server.py:257-274 | correctness | MCP mixed mode requires undocumented `remote:graph` syntax and skips local save-to-file/post-processing on remote branches, so AC12/AC13 are not met. | Implement the planned local-first remote resolution path and reuse the same save-to-file/response shaping logic for remote results. |
| F005 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/search.py:184-197 | correctness | Single-remote multi-graph search is missing: comma-separated graph names are sent to the single-graph endpoint instead of `/api/v1/search?graph=...`. | Route comma-separated graph names to the multi-graph endpoint and add AC7 coverage for single, multi, and all-graph remote search. |
| F006 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/execution.log.md:10-30 | testing | Phase evidence is stale and contradictory, and no Phase 5 tests or recorded command output back the completion claims. | Add the planned tests, rerun the real commands, and update `tasks.md` / `execution.log.md` with concrete outputs. |
| F007 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md:109-118 | scope | The spec/plan/domain artifacts still describe the superseded `--fs2-remote` / RemoteGraphStore contract, leaving AC11/AC12 unresolved against the implemented `--remote` / RemoteClient design. | Either implement the approved contract or update the governing spec/plan/domain artifacts to the implemented one before re-review. |
| F008 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/list_remotes.py:45-49 | error-handling | `list-remotes` catches any config exception and shows an empty-state message, hiding malformed YAML or validation failures. | Surface actionable config errors and reserve the empty-state message for truly missing config. |
| F009 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/get_node_service.py:81-102 | scope | The phase diff includes an undeclared core-service lazy-load change outside the Phase 5 task table/manifest. | Move the change out of this phase or document why it belongs here and add supporting evidence. |

## E) Detailed Findings

### E.1) Implementation Quality

- **F001 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/tree.py:193-214`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py:177-197`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py:278-323`
  - The Phase 5 dossier explicitly says remote tree should request `format=text` and print pre-rendered text directly, but the current implementation cannot do that. `RemoteClient.tree()` has no format parameter, the Phase 4 server tree route exposes no text-format branch, and `tree.py` falls back to `json.dumps(result)` in non-JSON mode.
  - As implemented, `fs2 tree --remote ...` is visibly different from local `fs2 tree`, so AC6/T004 are not satisfied.
  - **Fix**: add a true text-format remote tree path (or reuse the local tree renderer on parity-shaped JSON) and assert local-vs-remote output equality in tests.

- **F002 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/config/service.py:38-41`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/tasks.md:166-169`
  - Phase 5 says remotes should follow the `OtherGraphsConfig` pattern and concatenate user + project config. The code adds `RemoteServer` / `RemotesConfig`, but the merge helper still only concatenates `other_graphs.graphs`.
  - That means one config layer can silently hide the other, so named remotes disappear depending on merge order.
  - **Fix**: extend list-concatenation to `remotes.servers`, then add regression coverage for user-level + project-level remotes.

- **F003 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/get_node.py:69-88`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py:246-270`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py:329-356`
  - The remote CLI path does not request max detail, so it gets the server route’s default `detail=min`. The server route also returns a remote-specific payload (`children_count`, `graph_name`) rather than the local CLI’s `asdict(node)` shape.
  - `RemoteClient.get_node()` further treats any 404 containing “Not found” as `None`, so an unknown remote graph can be misreported to the user as a missing node.
  - **Fix**: request the parity detail level, distinguish graph-not-found vs node-not-found in the client, and normalize remote get-node output to the local CLI/MCP contract.

- **F004 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/mcp/server.py:257-274`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/mcp/server.py:478-503`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/mcp/server.py:703-717`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/mcp/server.py:934-955`
  - T007 says MCP should check local first, then remote automatically, and stay indistinguishable from local mode. The current code only resolves remotes when `graph_name` already uses `remote:graph` syntax.
  - Once a remote branch is taken, `tree()`, `get_node()`, and `search()` return early before the normal `save_to_file` / output-shaping branches run, so remote tool behavior differs from local mode.
  - **Fix**: implement the promised local-first → remote lookup path and reuse the same save-to-file / response shaping behavior for remote results.

- **F005 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/search.py:184-197`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py:240-244`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md:109-111`
  - The spec still requires remote search to support `--graph name1,name2`, but the CLI passes any non-empty `graph_name` directly to `RemoteClient.search()`. The client treats every non-empty graph string as a single-graph path, so `repo1,repo2` becomes `/api/v1/graphs/repo1,repo2/search` instead of the multi-graph endpoint.
  - This leaves the single-remote multi-graph branch of AC7 unimplemented.
  - **Fix**: detect comma-separated graph names and route them through `/api/v1/search?graph=...`, then add parity tests for single, multi, and all-graph remote search.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | New files (`/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/list_remotes.py`) land under the cli-presentation/configuration paths called out in the Phase 5 dossier. |
| Contract-only imports | ✅ | No new cross-domain import from another domain’s private internals was introduced beyond the intended cli-presentation → configuration/server usage for this phase. |
| Dependency direction | ✅ | No reverse business/infrastructure dependency or business cycle was introduced by the remote branching work. |
| Domain.md updated | ❌ | `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md` still omits `RemoteServer` / `RemotesConfig` from Concepts, Contracts, and History. |
| Registry current | ✅ | `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/registry.md` is still valid because Phase 5 does not introduce a new formal domain. |
| No orphan files | ❌ | `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/get_node_service.py` changed in the phase diff but is not declared in the Phase 5 task table or broader Domain Manifest. |
| Map nodes current | ❌ | `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md:63-66` still describes configuration as having 12 config models and does not acknowledge remotes capability. |
| Map edges current | ❌ | `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md:47,66` still labels the cli → server dependency as `RemoteGraphStore`, not RemoteClient/mixed remote routing. |
| No circular business deps | ✅ | The current domain map does not introduce a circular business dependency. |
| Concepts documented | ⚠️ | `configuration/domain.md` has a Concepts table, but it does not document named remotes or `config.get(RemotesConfig)` even though cli-presentation now depends on that capability. |

- **F007 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md:109-118`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md:248-279`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md:47,63-66`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md:15-23`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md:78-93`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md:137-146`
  - The governing artifacts still define Phase 5 as `--fs2-remote` + `FS2_REMOTE_URL` + RemoteGraphStore/graph-storage changes + explicit MCP remote mode, while the code now implements `--remote` + `FS2_REMOTE`, `RemotesConfig`, `RemoteClient` in cli-presentation, and prefix-based mixed MCP routing.
  - Until the contract is reconciled, AC11/AC12 cannot be signed off because the code and the spec are measuring different behaviors.
  - **Fix**: either bring the code back to the approved contract or update the spec/plan/domain artifacts to the implemented contract before re-review.

- **F009 (MEDIUM)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/get_node_service.py:81-102`
  - The lazy-load short-circuit may be a valid standalone fix, but it is not declared anywhere in the Phase 5 dossier or domain manifest.
  - That makes this diff partially out-of-scope for a phase otherwise centered on cli/config/MCP remote bridging.
  - **Fix**: move it into its own reviewable change or document it explicitly in the phase dossier and evidence.

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| RemotesConfig named remotes pattern | `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/config/service.py` (`OtherGraphsConfig` + `CONCATENATE_LIST_PATHS`) | configuration | ⚠️ Extend existing named-list merge support; the current phase copied the pattern but missed its concatenate-on-merge behavior. |
| MCP mixed local+remote routing | `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/utils.py` (`resolve_remotes()`) | cli-presentation | ⚠️ Extend/centralize shared remote resolution instead of maintaining separate prefix-only logic inside MCP. |
| RemoteClient HTTP bridge | None | cli-presentation | ✅ Proceed — this is a distinct server-query bridge; the review issue is contract parity, not concept duplication. |

### E.4) Testing & Evidence

**Coverage confidence**: 18%

**Evidence violations**:
- **HIGH** — `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/tasks.md` marks T001-T004 complete, and the diff contains T005/T007/T008-level files, but `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/execution.log.md` still says every task is pending and `Test Results` are "Not started".
- **HIGH** — No Phase 5 test files were added under `/Users/jordanknight/substrate/fs2/028-server-mode/tests/`, T009 remains open, and the commit message for `45da170a073e4e1841c33c21cf46ba4c75d19678` claims "1604 tests pass, 0 regressions" without any captured command output in the phase artifacts.
- **HIGH** — The Phase 5 success criterion says `pytest tests/unit/ -m "not slow"` should pass with the new tests, but the review run `uv run pytest tests/unit/cli -m 'not slow' -q` selected 0 tests / deselected 277 because the current CLI suite is marked slow and no Phase 5 not-slow coverage exists.

| AC | Confidence | Evidence |
|----|------------|----------|
| AC6 | 8% | `tree.py` has a remote branch, but normal remote output is `json.dumps(result)` rather than local-style tree output. No parity test or execution-log command proves equivalence. |
| AC7 | 15% | `search.py` and `remote_client.py` wire remote search and search-all, but comma-separated graph names still route to the single-graph endpoint and there is no recorded verification. |
| AC8 | 15% | `get_node.py` has a remote branch, but it requests min detail, collapses all 404s to node-not-found, and does not prove payload parity with local `get-node`. |
| AC9 | 20% | `list_graphs.py` remote mode exists, but the CLI omits embedding model in table output and no recorded command output backs the result shape. |
| AC11 | 10% | `main.py` wires `--remote` / `FS2_REMOTE`, not the spec’s `--fs2-remote` / `FS2_REMOTE_URL`, and the execution log has no transparent-routing proof. |
| AC12 | 10% | `mcp/server.py` adds mixed-mode pieces, but `cli/mcp.py` exposes no explicit remote entrypoint and the implemented routing semantics differ from the governing artifacts. |
| AC13 | 8% | Remote MCP branches skip local `save_to_file` / post-processing behavior and require prefix-based graph selection, so callers can distinguish remote mode from local mode. |

### E.5) Doctrine Compliance

N/A — no `docs/project-rules/*.md` files exist. Against repository conventions, the retained doctrine issue is **F008**: `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/list_remotes.py:45-49` suppresses actionable configuration failures instead of surfacing them. I did **not** retain the broader “RemoteClient must live outside cli” objection as a blocking finding because the authoritative Phase 5 tasks dossier explicitly places `remote_client.py` in the cli-presentation slice.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC6 | `fs2 tree --fs2-remote <url> --graph <name>` returns the same hierarchical structure as the local graph | Remote tree wiring exists, but the current non-JSON path prints raw JSON because the planned `format=text` parity path was never implemented. | 8% |
| AC7 | Remote search supports single, multi, and all-graph modes with local-equivalent behavior | Search-all wiring exists, but comma-separated graph names still go through the single-graph endpoint and there is no parity evidence. | 15% |
| AC8 | `fs2 get-node --fs2-remote <url> --graph <name> <node_id>` returns full node content identical to local get-node | Remote get-node exists, but it requests min detail, masks graph-level 404s, and does not match the local payload shape. | 15% |
| AC9 | `fs2 list-graphs --fs2-remote <url>` shows accessible graphs with name, description, node count, embedding model, and status | Remote list-graphs exists, but the CLI omits embedding model in table output and no recorded verification demonstrates the promised field set. | 20% |
| AC11 | Remote flag / env var transparently route all query commands | The implementation uses `--remote` / `FS2_REMOTE`; the governing spec still defines `--fs2-remote` / `FS2_REMOTE_URL`, so the acceptance contract is unresolved. | 10% |
| AC12 | MCP server started in remote mode exposes the same tree/search/get_node/list_graphs tools backed by server data | Mixed remote plumbing exists in `mcp/server.py`, but the contract differs from the governing artifacts and no concrete end-to-end MCP evidence is recorded. | 10% |
| AC13 | AI agents cannot distinguish between local and remote MCP mode | Remote branches currently skip local save-to-file / response-shaping logic and require prefix-based graph selection, so parity is not yet achieved. | 8% |

**Overall coverage confidence**: 18%

## G) Commands Executed

```bash
git --no-pager status --short
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager log --oneline --decorate -20
git --no-pager log --oneline --decorate --grep='remote\|mcp\|Phase 5' -20
git --no-pager diff --binary 310dabf..45da170 > /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/_computed.diff
git --no-pager diff --name-status 310dabf..45da170 > /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/_manifest.txt
git --no-pager show -s --format='%H%n%B' 45da170
pytest tests/unit/cli -m 'not slow' -q          # ambient environment failed during collection (missing typer)
uv run pytest tests/unit/cli -m 'not slow' -q   # 0 selected, 277 deselected
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md
**Phase**: Phase 5: Remote CLI + MCP Bridge
**Tasks dossier**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/review.phase-5-remote-cli-mcp-bridge.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/tasks.fltplan.md | modified | planning-artifact | Reconcile stage/checklist status after fixes. |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/tasks.md | modified | planning-artifact | Update task statuses / contract text to match the final implementation. |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/get_node.py | modified | cli-presentation | Fix remote detail/error parity. |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/list_graphs.py | modified | cli-presentation | Align remote output and AC9 evidence with the promised field set. |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/list_remotes.py | created | cli-presentation | Surface config failures instead of swallowing them. |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/main.py | modified | cli-presentation | Reconcile the global remote contract with the governing spec/docs. |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py | created | cli-presentation | Add tree format support, graph/error discrimination, and multi-graph routing. |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/search.py | modified | cli-presentation | Route comma-separated graph names to the multi-graph endpoint. |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/tree.py | modified | cli-presentation | Restore local-style remote tree output. |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/utils.py | modified | cli-presentation | Keep remote resolution behavior aligned with final merge/routing tests. |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/config/objects.py | modified | configuration | Pair the new models with config-merge and documentation updates. |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/get_node_service.py | modified | core-service | Remove or explicitly declare this scope addition. |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/mcp/server.py | modified | cli-presentation | Implement planned mixed-mode parity and save-to-file behavior. |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/tree.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py | Restore local-style remote tree output. | AC6/T004 currently fail because remote tree prints JSON instead of tree text. |
| 2 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/config/service.py | Honor user + project remotes concatenation. | T001/R6 explicitly require named remotes to follow the OtherGraphsConfig merge pattern. |
| 3 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/get_node.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py | Restore get-node parity and graph/not-found error discrimination. | AC8 currently fails and users can receive misleading node-not-found errors. |
| 4 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/mcp/server.py | Finish MCP mixed-mode routing/save-to-file parity. | AC12/AC13 currently fail because remote mode is distinguishable and under-routed. |
| 5 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/search.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py | Implement single-remote multi-graph search. | AC7 still misses the `graph=name1,name2` case. |
| 6 | /Users/jordanknight/substrate/fs2/028-server-mode/tests/unit/cli/test_remote_client.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/unit/cli/test_list_remotes.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/unit/cli/test_remote_integration.py; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/execution.log.md | Add the promised tests and record actual command output. | The review found no phase-specific verification evidence. |
| 7 | /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md | Reconcile the approved contract with the implemented one. | AC11/AC12 and the domain story still point at the superseded RemoteGraphStore/`--fs2-remote` design. |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md | AC11-AC13 still define `--fs2-remote` / `FS2_REMOTE_URL` / explicit MCP remote mode instead of the implemented contract. |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md | Phase 5 still describes RemoteGraphStore, graph-storage changes, and `resolve_graph_from_context()` switching rather than RemoteClient + mixed MCP routing. |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md | Concepts / Contracts / History do not mention `RemoteServer` or `RemotesConfig`. |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md | cli → server edge and health summary still refer to `RemoteGraphStore` and omit remotes capability in configuration. |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/execution.log.md | Task progress, decisions, and test results do not reflect the actual code in the diff. |

### Next Step

/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md --phase 'Phase 5: Remote CLI + MCP Bridge'
