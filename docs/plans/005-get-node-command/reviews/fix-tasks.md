# Fix Tasks (ordered by severity)

1) Redirect stderr/stdout correctly for get-node
- File: src/fs2/cli/get_node.py
- Issue: Console is bound to stdout; errors and `--file` success message print to stdout, violating clean piping/AC4-AC6.
- Fix: Instantiate `Console(stderr=True)` (or use `print(..., file=sys.stderr)`) and route all non-JSON output (errors + file success) to stderr. Keep JSON-only stdout for success. Add tests asserting stdout is empty for error/--file cases and still json.loads()-clean for success.
- Patch hint:
  ```python
  console = Console(stderr=True)
  ...
  if file:
      file.write_text(json_str)
      console.print(f"[green]\u2713[/green] Wrote {node_id} to {file}")
  else:
      print(json_str)
  ```

2) Restore graph integrity (footnotes + task↔log links)
- Files: docs/plans/005-get-node-command/get-node-command-plan.md; docs/plans/005-get-node-command/execution.log.md
- Issue: No footnote tags or ledger entries; no log anchors/backlinks. Provenance navigation is broken.
- Fix: Add footnote tags in task Notes, populate ledger entries for each modified path (get_node.py, main.py, conftest.py, unit/integration tests), and ensure numbering is sequential. Add log anchors (`log#t000`, etc.) in plan Notes and matching anchors/Plan Task metadata in execution log headings.

3) Resolve scope drift
- Files: docs/plans/004-tree-command/*, src/fs2/cli/tree.py, tests/unit/cli/test_tree_cli.py
- Issue: Tree-command plan/spec/test/code changes are included in this phase’s diff but not in get-node scope.
- Fix: Move/rebase these changes into the tree-command phase (plan 004) with proper footnotes, or strip them from the get-node phase before review.

4) Strengthen AC9/AC4 coverage
- Files: tests/unit/cli/test_get_node_cli.py (and plan/spec alignment)
- Issue: AC9 only checks 5 fields; AC4 does not assert stderr-only success message.
- Fix: Either align spec/plan to “essential fields” or assert all CodeNode fields in tests. Add a test for `--file` ensuring stdout remains empty and success guidance is on stderr.

## Testing guidance
- After fixes: run `pytest tests/unit/cli/test_get_node_cli.py -v` and, if scope drift is resolved, `pytest tests/integration/test_get_node_cli_integration.py -v`. If tree-command changes remain, rerun its suite separately.
