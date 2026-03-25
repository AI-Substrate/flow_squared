# Fix Tasks: Phase 2: Layout + Rendering — Treemap, Sigma.js, Cosmos Theme

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Align AC10 with the shipped edge renderer
- **Severity**: HIGH
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_service.py
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/graph-viewer.js
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-plan.md
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/tasks.md
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md
- **Issue**: Phase artifacts mark curved/glow reference edges as complete, but the committed implementation still emits straight arrow edges only.
- **Fix**: Choose one consistent direction: either implement curved/glow reference rendering and capture proof, or formally defer AC10 and remove all `[x]`/"complete" claims for curved/glow edges in the plan/tasks/log.
- **Patch hint**:
  ```diff
- - [x] AC10: Reference edges render as curved amber lines with glow
+ - [ ] AC10: Deferred — Phase 2 ships straight amber arrows; curves/glow move to Phase 3
  ```

### FT-002: Add browser/manual evidence for visual ACs
- **Severity**: HIGH
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md
- **Issue**: AC2, AC22, and AC23 are marked complete without browser name/version, screenshots, or observed outcomes.
- **Fix**: Open a generated report in the target browsers, verify offline render/theme/fonts, and log the browsers, versions, observations, and artifact paths.
- **Patch hint**:
  ```diff
+ ### Visual verification
+ - Chrome <version>: opened generated report offline; graph rendered without CDN/network requests.
+ - Firefox <version>: Cosmos palette and labels rendered correctly.
+ - Safari <version>: embedded Inter + JetBrains Mono rendered as expected.
+ - Evidence: <absolute screenshot or artifact paths>
  ```

### FT-003: Add 5K/50K performance evidence
- **Severity**: HIGH
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md
- **Issue**: AC19 and AC20 are checked off without any recorded render-time or FPS measurements.
- **Fix**: Run reproducible 5K and 50K-node benchmark scenarios, then log the machine/browser, commands, timings, FPS observations, and any clustered/non-clustered conditions.
- **Patch hint**:
  ```diff
+ ### Performance verification
+ - 5K graph: <command>, <browser>, initial render <time>, interaction ~<fps>
+ - 50K graph: <command>, <browser>, initial render <time>, interaction ~<fps>
+ - Notes: <hardware / clustered mode / caveats>
  ```

## Medium / Low Fixes

### FT-004: Reuse shared folder-hierarchy logic
- **Severity**: MEDIUM
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_layout.py
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/tree_service.py
- **Issue**: `report_layout._build_dir_tree()` reimplements file-path tree construction even though the phase dossier explicitly pointed at `TreeService._compute_folder_hierarchy()` as the reuse point.
- **Fix**: Extract or reuse a pure folder-tree helper so one implementation owns directory-hierarchy construction.
- **Patch hint**:
  ```diff
- def _build_dir_tree(nodes: list[CodeNode]) -> dict:
-     ...
+ # Reuse an extracted shared folder-tree helper rather than maintaining
+ # a second file-path hierarchy implementation inside report_layout.py.
  ```

### FT-005: Remove the duplicate JS category-color map
- **Severity**: MEDIUM
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/graph-viewer.js
- **Issue**: The legend hard-codes a second `catColors` map even though Python already serializes category colors as the source of truth.
- **Fix**: Build the legend color map from serialized node data (or one emitted color contract) instead of hard-coding another JS map.
- **Patch hint**:
  ```diff
- var catColors = {
-   callable: '#67e8f9', type: '#c4b5fd', file: '#94a3b8',
-   section: '#a5b4fc', folder: '#64748b', block: '#6ee7b7',
-   statement: '#fda4af', expression: '#fdba74', definition: '#d9f99d',
-   other: '#9ca3af'
- };
+ var catColors = {};
+ (GRAPH_DATA.nodes || []).forEach(function (n) {
+   if (n.category && n.color && !catColors[n.category]) catColors[n.category] = n.color;
+ });
  ```

### FT-006: Align T009 asset-embedding claims with actual template behavior
- **Severity**: MEDIUM
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_service.py
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/templates/reports/codebase_graph.html.j2
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/tasks.md
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md
- **Issue**: ForceAtlas2 is vendored but not embedded, while the task/log wording says all vendored assets are inlined.
- **Fix**: Either inline `graphology-layout-forceatlas2.min.js` now or update the wording to say it is vendored for later use and not currently embedded.
- **Patch hint**:
  ```diff
+ "force_atlas_js": self._load_static_asset("graphology-layout-forceatlas2.min.js"),
  ```
  ```diff
+ <script>{{ force_atlas_js }}</script>
  ```

### FT-007: Make the execution log traceable
- **Severity**: LOW
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md
- **Issue**: The final summary claims test/lint/report-generation success without exact commands or summarized output.
- **Fix**: Append the exact `pytest`/`ruff`/generation commands plus a short excerpt of their output and any generated artifact paths.
- **Patch hint**:
  ```diff
+ ### Verification commands
+ - `uv run python -m pytest -q tests/unit/services/test_report_layout.py tests/unit/services/test_report_service.py`
+ - `uv run python -m pytest -q --override-ini='addopts=' tests/unit/cli/test_report_cli.py`
+ - `uv run ruff check src/fs2/core/services/report_layout.py src/fs2/core/services/report_service.py tests/unit/services/test_report_layout.py tests/unit/services/test_report_service.py`
+ - Generated artifact: <absolute path to sample report>
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
