# Fix Tasks – Phase 1: Core Tree Command with Path Filtering

Testing approach: Full TDD (write/adjust tests first, then code), mock policy: Avoid mocks.

1) Scope alignment for rules.md change (HIGH)
- Action: Remove the CLI rules addition from this phase or create a scoped task + footnote entry justifying it. Update plan/tasks if retained.
- Tests-first: Add/adjust a planning doc test or checklist entry only after scope decision; no code tests required.

2) Footnote synchronization (HIGH)
- Action: Add footnote stubs [^4] and [^5] to tasks.md; sync plan §12 ledger to include tests/unit/repos/test_graph_store.py and docs/rules-idioms-architecture/rules.md with FlowSpace node IDs. Ensure tasks referencing those files include the correct footnote numbers.
- Tests-first: Update documentation artifacts first; no code changes. Validate by cross-checking ledger vs diff paths.

3) Task↔Log backlinks (HIGH)
- Action: In tasks.md Notes column, add log anchors (e.g., log#t001-tree-config). In execution.log.md, add **Dossier Task**/**Plan Task** metadata and backlinks for each log section with matching anchors.
- Tests-first: Add anchors/links before modifying narrative; verify navigation manually.

4) Full TDD evidence (HIGH)
- Action: Enrich execution.log.md with RED/GREEN/REFACTOR entries per task showing tests written first, failing, then passing, then refactor. Include timestamps or sequence and test names used.
- Tests-first: None (documentation). Ensure narrative clearly orders test-before-code.

5) Tree summary/depth scope and counts (MEDIUM)
- Action: Either defer summary/depth output to Phase 2 (remove summary line and depth handling) or compute totals across displayed subtrees (not just root nodes) per AC9 expectations. Add unit tests that assert accurate node/file counts and depth-hidden messaging.
- Tests-first: Write/adjust tests in tests/unit/cli/test_tree_cli.py to capture expected counts/depth behavior, then update src/fs2/cli/tree.py accordingly.

6) Verbose flag behavior (LOW)
- Action: Connect --verbose to logging (e.g., configure Rich logging handler when verbose is true). Add a test asserting debug output appears when verbose is set.
- Tests-first: Add/adjust test in tests/unit/cli/test_tree_cli.py to invoke tree with --verbose and assert diagnostic output, then wire up logging in src/fs2/cli/tree.py.
