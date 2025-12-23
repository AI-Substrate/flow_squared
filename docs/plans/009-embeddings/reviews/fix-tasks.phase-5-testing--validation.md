# Fix Tasks — Phase 5: Testing & Validation

Ordered for Full TDD (test/doc fixes before code/plan sync).

1) **Add Phase 5 footnotes and sync ledgers (CRITICAL graph integrity)**
   - Add [^N] tags in `/workspaces/flow_squared/docs/plans/009-embeddings/tasks/phase-5-testing--validation/tasks.md` Notes column for each changed file.
   - Populate Phase Footnote Stubs in `/workspaces/flow_squared/docs/plans/009-embeddings/tasks/phase-5-testing--validation/tasks.md` with matching entries.
   - Add Phase 5 entries in `/workspaces/flow_squared/docs/plans/009-embeddings/embeddings-plan.md` Change Footnotes Ledger with FlowSpace node IDs for each file/method.
   - Suggested command: `plan-6a --sync-footnotes --phase Phase 5: Testing & Validation`

2) **Restore Task↔Log bidirectional links (HIGH)**
   - In `/workspaces/flow_squared/docs/plans/009-embeddings/tasks/phase-5-testing--validation/tasks.md`, add log anchors in Notes for T001/T002/T004/T005/T006/T007 (e.g., `log#task-t001-review-existing-integration-test-patterns-and-fixture-helpers`).
   - In `/workspaces/flow_squared/docs/plans/009-embeddings/tasks/phase-5-testing--validation/execution.log.md`, add markdown links for **Dossier Task** and **Plan Task** to their table entries.

3) **Align dossier scope with changed files (HIGH)**
   - Add `tests/unit/services/test_embedding_graph_config.py` to the Task-to-Component mapping and Tasks table (T005) or move the change to the phase that owns it.

4) **TDD evidence in execution log (HIGH)**
   - For each task in `/workspaces/flow_squared/docs/plans/009-embeddings/tasks/phase-5-testing--validation/execution.log.md`, record RED → GREEN → REFACTOR evidence (timestamps or command output snippets).

5) **Fix E2E acceptance-criteria mismatch (HIGH)**
   - File: `/workspaces/flow_squared/tests/integration/test_e2e_embedding_validation.py`
   - Update the embedding rate assertion to enforce 100% for nodes with content.
   - Patch hint:
     ```diff
     - assert embedding_rate > 0.5, (
     -     f"Expected >50% embedding rate, got {embedding_rate:.1%} "
     -     f"({len(nodes_with_embeddings)}/{len(nodes_with_content)})"
     - )
     + assert embedding_rate == 1.0, (
     +     f"Expected 100% embedding rate, got {embedding_rate:.1%} "
     +     f"({len(nodes_with_embeddings)}/{len(nodes_with_content)})"
     + )
     ```

6) **Strengthen multi-chunk assertions (MEDIUM)**
   - File: `/workspaces/flow_squared/tests/unit/services/test_embedding_service.py`
   - For tests that claim multi-chunk/overlap/split behavior, assert `len(updated_node.embedding) > 1` and (optionally) verify overlap presence.
   - Patch hint (example):
     ```diff
     - assert len(updated_node.embedding) >= 1
     + assert len(updated_node.embedding) > 1
     ```

7) **Complete test documentation (MEDIUM)**
   - File: `/workspaces/flow_squared/tests/integration/test_e2e_embedding_validation.py`
   - Add an “Acceptance Criteria” line to the docstring of `test_given_samples_when_scanning_then_embedding_format_correct`.

8) **Resolve missing evidence artifact (MEDIUM)**
   - Either create `/workspaces/flow_squared/scratch/e2e_embedding_validation.md` with the manual validation notes, or remove it from Evidence Artifacts in `/workspaces/flow_squared/docs/plans/009-embeddings/tasks/phase-5-testing--validation/tasks.md`.

9) **Complete regression guard for phases 1–3 (MEDIUM)**
   - Rerun key tests listed in phase 1–3 execution logs (e.g., `tests/unit/config/test_embedding_config.py`, `tests/unit/adapters/test_embedding_adapter_*.py`, `tests/unit/services/test_embedding_*`), and record results in the Phase 5 execution log.
