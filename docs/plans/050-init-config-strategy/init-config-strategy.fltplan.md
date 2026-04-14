# ✈️ Flight Plan: Init Config Split

**Plan**: 050-init-config-strategy
**Status**: Ready
**Complexity**: CS-1 (trivial)
**Generated**: 2026-04-14

## Mission

Split `fs2 init` config generation: project config gets scan-only (everything else commented out), global config keeps full template with Ollama auto-detection.

## Artifacts

| Artifact | Status | Path |
|----------|--------|------|
| Research Dossier | ✅ Complete | `research-dossier.md` |
| Specification | ✅ Complete | `init-config-strategy-spec.md` |
| Clarification | ✅ Skipped | User direction explicit |
| Plan | ✅ Complete | `init-config-strategy-plan.md` |

## Acceptance Criteria Summary

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Project config scan-only, rest commented | ⬜ |
| AC2 | Global config keeps full template | ⬜ |
| AC3 | Zero-edit first scan works | ⬜ |
| AC4 | Ollama auto-detection targets global only | ⬜ |
| AC5 | --force flag still works | ⬜ |
| AC6 | Existing tests pass | ⬜ |
