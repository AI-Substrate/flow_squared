# Fix Tasks - Phase 1: Core Infrastructure

## CRITICAL
1) **Sync plan/dossier task status + log links**
- Files: `docs/plans/009-embeddings/embeddings-plan.md`
- Issue: Phase 1 task table still pending and missing [📋] log links.
- Fix: Run `plan-6a` to sync status and add log links that target anchors in the execution log.
- Patch hint:
```diff
- | 1.1 | [ ] | Write tests for ChunkConfig and EmbeddingConfig validation | ... | - |
+ | 1.1 | [x] | Write tests for ChunkConfig and EmbeddingConfig validation | ... | [📋](./tasks/phase-1-core-infrastructure/execution.log.md#task-t002-t003-write-failing-tests-for-chunkconfig-and-embeddingconfig) |
```

2) **Populate Change Footnotes Ledger + Phase Footnote Stubs**
- Files: `docs/plans/009-embeddings/embeddings-plan.md`, `docs/plans/009-embeddings/tasks/phase-1-core-infrastructure/tasks.md`
- Issue: Plan ledger has placeholders; dossier stubs empty; no footnote tags in task Notes.
- Fix: Run `plan-6a --sync-footnotes` to create [^N] entries for each modified file, then add matching footnotes to dossier stubs and task Notes.
- Patch hint:
```diff
- [^1]: [To be added during implementation via plan-6a]
+ [^1]: file:src/fs2/config/objects.py:EmbeddingConfig (default dimensions=1024)
```

## HIGH
3) **Add task↔log backlinks in execution log**
- File: `docs/plans/009-embeddings/tasks/phase-1-core-infrastructure/execution.log.md`
- Issue: Task entries lack `**Dossier Task**` and `**Plan Task**` metadata/backlinks.
- Fix: Add metadata blocks under each task heading and ensure anchors match task IDs.
- Patch hint:
```diff
## Task T004-T006: Implement ChunkConfig, EmbeddingConfig, and register in YAML_CONFIG_TYPES
+**Dossier Task**: T004-T006 ([link](./tasks.md#t004))
+**Plan Task**: 1.2 ([link](../../embeddings-plan.md#tasks-full-tdd-approach))
```

4) **Implement EmbeddingConfig dimensions field (default 1024) + tests**
- Files: `src/fs2/config/objects.py`, `tests/unit/config/test_embedding_config.py`
- Issue: Alignment Finding 10 requires default 1024 dimensions; field missing.
- Fix (TDD): Add failing tests first, then implement `dimensions: int = 1024` with validation (>=1).
- Patch hint:
```diff
+    dimensions: int = 1024
+
+    @field_validator("dimensions")
+    @classmethod
+    def validate_dimensions(cls, v: int) -> int:
+        if v <= 0:
+            raise ValueError("dimensions must be > 0")
+        return v
```

5) **Add Arrange/Act/Assert comments to new tests (R4.4)**
- Files: `tests/unit/config/test_embedding_config.py`, `tests/unit/adapters/test_embedding_exceptions.py`, `tests/unit/models/test_code_node_embedding.py`
- Issue: Tests lack AAA phase comments.
- Fix: Add `# Arrange`, `# Act`, `# Assert` comments in each test.
- Patch hint:
```diff
-        config = ChunkConfig(max_tokens=400, overlap_tokens=50)
-
-        assert config.max_tokens == 400
+        # Arrange
+        config = ChunkConfig(max_tokens=400, overlap_tokens=50)
+        # Act
+        # (construction is the act)
+        # Assert
+        assert config.max_tokens == 400
```

6) **Document explicit RED/GREEN/REFACTOR steps in execution log**
- File: `docs/plans/009-embeddings/tasks/phase-1-core-infrastructure/execution.log.md`
- Issue: RED/GREEN evidence exists, but REFACTOR steps are not explicitly recorded.
- Fix: Add short RED/GREEN/REFACTOR entries per task or per task group.

## MEDIUM
7) **Add coverage evidence or adjust artifact list**
- File: `docs/plans/009-embeddings/tasks/phase-1-core-infrastructure/execution.log.md`
- Issue: Coverage report listed as artifact but no evidence shown.
- Fix: Run coverage for Phase 1 tests and record output in the log, or remove the artifact entry with justification.

8) **Make mypy available or document limitation**
- File: `docs/plans/009-embeddings/tasks/phase-1-core-infrastructure/execution.log.md`
- Issue: `uv run python -m mypy` failed (module missing).
- Fix: Add mypy to dev tooling or record the limitation in the execution log and plan rules.
