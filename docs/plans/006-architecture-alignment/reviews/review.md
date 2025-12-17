# Review – CLI Architecture Alignment (Simple Mode)

## A) Verdict
REQUEST_CHANGES (graph integrity gaps)

## B) Summary
- Lightweight approach acknowledged; new services and CLI refactor match plan intent with no semantic regressions spotted.
- Graph integrity broken: two changed files lack footnote coverage (rules.md, config/models.py) so provenance chain is incomplete.
- Task↔Log links missing: tasks table has no log anchors/backlinks to execution.log.md, breaking navigation for evidence.
- No additional correctness/security/performance/observability issues found in diff review.

## C) Checklist (Testing Approach: Lightweight)
- [x] Core validation tests present for critical paths (service unit tests)
- [x] Critical paths covered per Focus Areas (graph services, CLI composition)
- [x] Mock usage matches spec: Avoid mocks (uses FakeGraphStore only)
- [ ] Key verification points documented (task↔log anchors missing)
- Universal: [x] BridgeContext patterns (N/A codebase), [ ] Only in-scope files changed (rules.md, config/models missing footnotes), [ ] Linters/type checks documented for this review run

## D) Findings Table
| ID | Severity | File:Lines | Summary | Recommendation |
|----|----------|------------|---------|----------------|
| F1 | HIGH | docs/rules-idioms-architecture/rules.md:106 | Changed rule set (R3.5) lacks footnote/tag in plan ledger, breaking Footnote↔File provenance. | Add a new footnote entry (e.g., [^12]) for this rule change in the plan ledger and tag the relevant task/Notes column to restore traceability. |
| F2 | HIGH | src/fs2/config/models.py:200 | Added `extra="ignore"` to `FS2Settings` without a corresponding footnote ledger entry. | Tag this change with a plan footnote and ledger entry (can extend [^1] or add next number) so config behavior change is tracked. |
| F3 | HIGH | docs/plans/006-architecture-alignment/cli-architecture-alignment-plan.md (Tasks table / execution.log.md) | Task↔Log links absent: tasks Notes lack `log#` anchors and execution log entries lack Plan/Dossier backlinks, so evidence navigation is broken. | Add log anchor links in the Tasks table Notes and reciprocal Plan Task metadata/anchors in execution.log.md for each task (T000–T013). |

## E) Detailed Findings
### E.0 Cross-Phase Regression Analysis
Skipped: Simple Mode (single phase).

### E.1 Doctrine & Testing Compliance
- Graph integrity: HIGH – Footnote coverage missing for `docs/rules-idioms-architecture/rules.md` and `src/fs2/config/models.py` (F1, F2).
- Task↔Log linkage: HIGH – Missing anchors/backlinks between tasks table and execution log (F3).
- Footnote authority conflicts: Plan ledger otherwise sequential; no mismatches detected.
- Testing approach (Lightweight) and mock policy (Avoid) respected in new service tests; no doctrine drift observed.

### E.2 Semantic Analysis
- No semantic/business-rule defects found in the reviewed diff.

### E.3 Quality & Safety Analysis
- Correctness/Security/Performance/Observability reviewers found no additional issues beyond graph-integrity items.

## F) Coverage Map (Acceptance Criteria ↔ Evidence)
- AC1/AC1a/AC1b/AC2 (TreeService + TreeNode): Covered by `tests/unit/services/test_tree_service.py` (filtering, root bucket, depth limits, TreeNode type) – confidence 100%.
- AC3/AC4/AC4a (GetNodeService + GraphNotFoundError): Covered by `tests/unit/services/test_get_node_service.py` (lazy load, found/missing, missing graph, corrupted graph) – confidence 100%.
- AC5 (CLI behavior preserved): Existing CLI tests still present (`tests/unit/cli/test_tree_cli.py`, `tests/unit/cli/test_get_node_cli.py`); not re-run in this review – confidence 50% (needs fresh run to confirm).
- AC6 (DI pattern): Verified via code inspection (services use config.require + GraphStore DI) – confidence 60% (no dedicated test).
- AC6a (GraphConfig rename): `tests/unit/config/test_graph_config.py` covers rename and registry – confidence 100%.
- AC7 (No mocks): Service tests use FakeGraphStore only – confidence 90%.
- AC8 (Constitution P9): Change present in `docs/rules-idioms-architecture/constitution.md` – confidence 100%.
- AC9 (No graph data copies): Services hold GraphStore references and avoid storing graph contents; `get_all_nodes()` is used transiently – confidence 80%.
- AC10 (Full suite/lint clean): Claim in execution.log.md; not rerun here – confidence 40%.

Overall coverage confidence: ~86% (strong, with gaps on rerun evidence for AC5/AC10 and DI explicit tests).

## G) Commands Executed
- ls
- sed -n '1,200p' docs/plans/006-architecture-alignment/cli-architecture-alignment-plan.md
- sed -n '1,200p' docs/plans/006-architecture-alignment/execution.log.md
- git status -sb
- git diff --unified=3
- sed -n '1,260p' src/fs2/core/services/tree_service.py
- sed -n '1,200p' src/fs2/core/services/get_node_service.py
- sed -n '1,200p' src/fs2/core/models/tree_node.py
- sed -n '1,240p' tests/unit/services/test_get_node_service.py
- sed -n '1,240p' tests/unit/services/test_tree_service.py
- sed -n '1,200p' src/fs2/config/models.py

## H) Decision & Next Steps
REQUEST_CHANGES due to graph integrity breaks (F1–F3). See `docs/plans/006-architecture-alignment/reviews/fix-tasks.md` for ordered remediation steps. After fixes, rerun this review and rerun the relevant tests (at least CLI targets) to firm up AC5/AC10 evidence.

## I) Footnotes Audit
| File Path | Footnote Tag(s) Found | Notes |
|-----------|-----------------------|-------|
| docs/rules-idioms-architecture/constitution.md | [^11] | OK |
| docs/rules-idioms-architecture/rules.md | — | Missing footnote (F1) |
| src/fs2/cli/get_node.py | [^5] | OK |
| src/fs2/cli/tree.py | [^9] | OK |
| src/fs2/config/objects.py | [^1] | OK |
| src/fs2/config/models.py | — | Missing footnote (F2) |
| src/fs2/core/adapters/exceptions.py | [^2] | OK |
| src/fs2/core/services/get_node_service.py | [^3] | OK |
| src/fs2/core/services/tree_service.py | [^6] | OK |
| src/fs2/core/models/tree_node.py | [^7] | OK |
| src/fs2/core/services/__init__.py | [^10] | OK |
| src/fs2/core/models/__init__.py | [^10] | OK |
| tests/conftest.py | [^1] | OK |
| tests/unit/config/test_graph_config.py | [^1] | OK |
| tests/unit/cli/test_tree_cli.py | [^1] | OK |
| tests/unit/services/test_get_node_service.py | [^4] | OK |
| tests/unit/services/test_tree_service.py | [^8] | OK |
