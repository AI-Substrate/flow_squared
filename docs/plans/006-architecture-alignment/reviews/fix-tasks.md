# Fix Tasks – CLI Architecture Alignment (Simple Mode)

## Ordering
1) Graph integrity (footnotes) 
2) Task↔Log navigation
3) Re-run targeted tests for evidence (AC5/AC10)

## Tasks

1. **Add footnote for rules.md change (HIGH)**
   - Files: docs/plans/006-architecture-alignment/cli-architecture-alignment-plan.md, docs/rules-idioms-architecture/rules.md
   - Action: Add a new sequential footnote (next number after [^11]) in the plan ledger describing the R3.5 Graph Data Access rule addition and tag the relevant task/Notes column in the tasks table. Ensure numbering stays sequential and unique.
   - Testing (Lightweight): None required; documentation-only change.

2. **Add footnote coverage for FS2Settings config behavior change (HIGH)**
   - Files: docs/plans/006-architecture-alignment/cli-architecture-alignment-plan.md, src/fs2/config/models.py
   - Action: Tag the `extra="ignore"` change with a plan footnote (extend [^1] or add the next number) and add the matching ledger entry. Note in the task Notes column that the config model behavior changed to tolerate extra fields.
   - Testing (Lightweight): None required; documentation-only change.

3. **Restore Task↔Log backlinks (HIGH)**
   - Files: docs/plans/006-architecture-alignment/cli-architecture-alignment-plan.md, docs/plans/006-architecture-alignment/execution.log.md
   - Action: For each task T000–T013, add `log#` anchors in the Tasks table Notes column pointing to execution log anchors. In `execution.log.md`, add Plan Task metadata/backlinks (e.g., `**Plan Task**: T000` with anchor) under each task section so navigation works both ways.
   - Testing (Lightweight): None required; verify links manually after editing.

4. **Reconfirm CLI test evidence (Medium, optional after docs fixed)**
   - Files: tests/unit/cli/test_tree_cli.py, tests/unit/cli/test_get_node_cli.py
   - Action: Re-run the CLI-focused tests to refresh evidence for AC5/AC10 and update execution.log.md with the new run output.
   - Testing (Lightweight): Run `pytest tests/unit/cli/test_tree_cli.py tests/unit/cli/test_get_node_cli.py -v`.
