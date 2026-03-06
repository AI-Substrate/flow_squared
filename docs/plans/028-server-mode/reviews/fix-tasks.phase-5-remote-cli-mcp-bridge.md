# Fix Tasks: Phase 5: Remote CLI + MCP Bridge

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Restore remote tree parity
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/tree.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py
- **Issue**: The Phase 5 dossier says remote tree should request `format=text` and print pre-rendered tree text, but the current implementation prints raw JSON in normal mode.
- **Fix**: Add a true text-format remote path (or equivalent local rendering over parity-shaped JSON) so `fs2 tree --remote ...` matches local `fs2 tree`. Add remote-vs-local parity tests.
- **Patch hint**:
  ```diff
  - result = asyncio.run(remote_client.tree(graph_name, pattern=pattern, max_depth=depth))
  - json_str = json.dumps(result, indent=2, default=str)
  - print(json_str)
  + result = asyncio.run(
  +     remote_client.tree(graph_name, pattern=pattern, max_depth=depth, format="text")
  + )
  + print(result["content"])
  ```

### FT-002: Honor named-remotes merge semantics
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/config/service.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/config/objects.py
- **Issue**: `RemotesConfig` follows the `OtherGraphsConfig` shape, but the merge helper still only concatenates `other_graphs.graphs`, so user and project remotes shadow each other.
- **Fix**: Extend the concatenate-on-merge helper to include `remotes.servers` and add regression coverage for user-level + project-level remotes.
- **Patch hint**:
  ```diff
  - CONCATENATE_LIST_PATHS: list[str] = ["other_graphs.graphs"]
  + CONCATENATE_LIST_PATHS: list[str] = [
  +     "other_graphs.graphs",
  +     "remotes.servers",
  + ]
  ```

### FT-003: Restore remote get-node parity and preserve actionable 404s
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/get_node.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py
- **Issue**: The remote CLI path requests min detail, the server returns a different payload shape than local `get-node`, and the client converts any “Not found” 404 into `None`.
- **Fix**: Request the parity detail level, distinguish graph-not-found vs node-not-found in the client, and normalize remote get-node payloads to the local CLI/MCP contract.
- **Patch hint**:
  ```diff
  - result = asyncio.run(remote_client.get_node(graph_name, node_id))
  + result = asyncio.run(remote_client.get_node(graph_name, node_id, detail="max"))
  ```
  ```diff
  - if "Not found" in str(e):
  + if "Node '" in str(e):
        return None
  ```

### FT-004: Implement the planned MCP mixed-mode contract
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/mcp/server.py
- **Issue**: MCP remote mode only works with `remote:graph` names and skips the normal save-to-file / post-processing branches for remote results.
- **Fix**: Implement the Phase 5 local-first → remote lookup behavior, then funnel remote results through the same save-to-file / response-shaping logic used by local mode.
- **Patch hint**:
  ```diff
  - if ":" in graph_name:
  -     remote_name, server_graph = graph_name.split(":", 1)
  -     ...
  + if graph_name in local_names:
  +     return None
  + if graph_name in remote_names:
  +     return remote_client_for(graph_name), graph_name
  ```
  ```diff
  - if remote_info is not None:
  -     return result
  + if remote_info is not None:
  +     result = _apply_remote_post_processing(result, save_to_file=save_to_file, ...)
  +     return result
  ```

### FT-005: Add single-remote multi-graph search support
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/search.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/remote_client.py
- **Issue**: `graph=name1,name2` is still routed to the single-graph endpoint instead of `/api/v1/search?graph=name1,name2`.
- **Fix**: Detect comma-separated graph names and use the multi-graph endpoint; then add AC7 coverage for single, multi, and all-graph remote search.
- **Patch hint**:
  ```diff
  - if graph:
  -     return await self._request("GET", f"/api/v1/graphs/{graph}/search", params=params)
  + if graph and "," not in graph:
  +     return await self._request("GET", f"/api/v1/graphs/{graph}/search", params=params)
  + if graph:
  +     params["graph"] = graph
  +     return await self._request("GET", "/api/v1/search", params=params)
  ```

### FT-006: Add the promised Phase 5 tests and recorded evidence
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/tests/unit/cli/test_remote_client.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/unit/cli/test_list_remotes.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/unit/cli/test_remote_integration.py; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/tasks.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/execution.log.md
- **Issue**: The phase claims progress without any new Phase 5 test files or captured command output, and the default `-m "not slow"` profile currently selects no CLI tests.
- **Fix**: Add the planned RemoteClient/remotes/list-remotes/CLI/MCP tests, record the exact commands/results that pass, and sync `tasks.md` / `execution.log.md` to the real implementation state.
- **Patch hint**:
  ```diff
  + async def test_given_remote_tree_when_requested_then_matches_local_text_output(): ...
  + def test_given_user_and_project_remotes_when_loading_then_both_are_available(): ...
  + def test_given_remote_mcp_graph_when_save_to_file_then_saved_to_is_returned(): ...
  ```

### FT-007: Reconcile the governing contract artifacts
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md
- **Issue**: The spec/plan/domain docs still define the superseded `--fs2-remote` / RemoteGraphStore / graph-storage design instead of the implemented `--remote` / RemoteClient / mixed MCP design.
- **Fix**: Either implement the original approved contract or update every governing artifact to the implemented one before re-review.
- **Patch hint**:
  ```diff
  - **AC11**: If `--fs2-remote` is set (via flag or `FS2_REMOTE_URL` env var), all query commands ...
  + **AC11**: If `--remote` is set (via flag or `FS2_REMOTE` env var), all remote-capable query commands ...
  ```
  ```diff
  - cli -.->|RemoteGraphStore HTTP| server
  + cli -.->|RemoteClient / remote REST queries| server
  ```

## Medium / Low Fixes

### FT-008: Surface remotes configuration failures instead of swallowing them
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/list_remotes.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/mcp/server.py
- **Issue**: `list-remotes()` treats any config error as “no remotes configured”, and MCP helper paths silently drop remote configuration/enumeration problems.
- **Fix**: Only show the empty-state message when remotes are genuinely absent; otherwise print/log actionable config errors with remediation guidance.
- **Patch hint**:
  ```diff
  - except Exception:
  -     remotes_config = None
  + except MissingConfigurationError:
  +     remotes_config = None
  + except Exception as e:
  +     stderr_console.print(f"[red]Error:[/red] Failed to load remotes config: {e}")
  +     raise typer.Exit(code=1)
  ```

### FT-009: Remove or declare the unrelated GetNodeService change
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/get_node_service.py; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-5-remote-cli-mcp-bridge/tasks.md
- **Issue**: The phase diff includes a core-service lazy-load change that is not declared anywhere in the Phase 5 task table or manifest.
- **Fix**: Either move this change into its own reviewable unit of work or add it to the Phase 5 dossier with explicit rationale and evidence.
- **Patch hint**:
  ```diff
  + | [x] | T00X | Guard GetNodeService against reloading preloaded stores | core-service | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/get_node_service.py | Existing preloaded graphs are not overwritten by default config graph_path. | Carry only if this change truly belongs to Phase 5. |
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
