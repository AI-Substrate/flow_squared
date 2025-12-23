# Fix Tasks — Phase 4: Pipeline Integration

## CRITICAL/HIGH
1) Add Task↔Log backlinks in `/workspaces/flow_squared/docs/plans/009-embeddings/tasks/phase-4-pipeline-integration/execution.log.md`
- For every task T001–T010, add:
  - `**Dossier Task**: T00X` with link to the dossier task row in `tasks.md`
  - `**Plan Task**: 4.X` with link to the plan task row in `embeddings-plan.md`
- Patch hint (per task block):
  ```md
  **Dossier Task**: [T002](./tasks.md#t002-write-failing-tests-for-pipelinecontext-embedding-fields)
  **Plan Task**: [4.1](../../embeddings-plan.md#41-write-tests-for-pipelinecontext-extension)
  ```

2) Document RED/GREEN/REFACTOR for Full TDD tasks
- Update each task entry in `execution.log.md` with explicit RED, GREEN, and REFACTOR evidence (tests run and outcomes) for T003, T005, T006, T008, T010.
- If a task did not require code changes after tests, add a short justification and reference the tests used as evidence.
- Patch hint (per task block):
  ```md
  ### RED
  - Command: `pytest ...`
  - Result: failing assertion ...

  ### GREEN
  - Command: `pytest ...`
  - Result: pass

  ### REFACTOR
  - Notes: refactor performed / not required (why)
  ```

## MEDIUM
3) Add explicit stage-ordering coverage for EmbeddingStage
- Add a test in `tests/unit/services/test_scan_pipeline.py` asserting the default stage order includes SmartContentStage → EmbeddingStage → StorageStage.
- TDD ordering: add the failing test first, then adjust code only if needed.
- Patch hint:
  ```python
  def test_default_stage_order_includes_embedding(self):
      pipeline = ScanPipeline(...)
      stage_names = [stage.name for stage in pipeline._stages]
      assert stage_names.index("smart_content") < stage_names.index("embedding") < stage_names.index("storage")
  ```

## LOW
4) Fix invalid type hint for embedding progress callback
- File: `src/fs2/core/services/scan_pipeline.py:94`
- Replace `EmbeddingService.ProgressCallback` with `Callable[[int, int, int], None]` or add a `ProgressCallback` type alias to `EmbeddingService` and reference it.

5) Footnote ledger scope clarity
- Either document that Change Footnotes Ledger is code-only (explicit note), or add footnote entries for plan/dossier/log artifacts touched in this phase.
