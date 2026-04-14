# Init Config Split — Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-04-14
**Spec**: `docs/plans/050-init-config-strategy/init-config-strategy-spec.md`
**Status**: COMPLETE

## Summary

`fs2 init` writes the same bloated template to both project and global configs, forcing users to edit out active `smart_content:` and `embedding:` sections just to scan. This plan creates a project-specific template variant where only `scan:` is active and everything else is commented out. The global config keeps the full template as-is.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| cli | existing | **modify** | init.py: add PROJECT_CONFIG template, use it for local config |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/cli/init.py` | cli | internal | Add PROJECT_CONFIG, restructure init() for separate local/global paths |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | High | `smart_content:` and `embedding:` are active in DEFAULT_CONFIG (lines 74-91) — they trigger model downloads and confusing "not configured" cascades | Comment them out in PROJECT_CONFIG |
| 02 | High | Ollama auto-detection (lines 248-260) modifies the config written to LOCAL project — a personal tool choice gets committed to git | Apply Ollama auto-detection to GLOBAL config only |
| 03 | Medium | The `scan:` section (lines 22-32) is the only section needed for a working first scan | Keep it as the only active section in PROJECT_CONFIG |

## Implementation

**Objective**: Project config gets scan-only active, global keeps full template.
**Testing Approach**: Lightweight — verify both config outputs.

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [x] | T001 | Create PROJECT_CONFIG template | cli | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/cli/init.py` | New string constant `PROJECT_CONFIG` exists. Same content as DEFAULT_CONFIG but with `smart_content:` block (lines 74-79) and `embedding:` block (lines 85-91) commented out. LLM and cross-file-rels stay as-is (already commented). | Per finding 01 |
| [x] | T002 | Restructure init() for separate local/global write paths | cli | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/cli/init.py` | init() uses two separate config text variables: `global_config_text = DEFAULT_CONFIG` (with Ollama auto-uncomment applied) and `local_config_text = PROJECT_CONFIG` (never modified by Ollama). Global write (line 226) uses `global_config_text`. Local write (line 263) uses `local_config_text`. | Per findings 02, 03 — control flow restructuring |
| [x] | T003 | Update init() success messaging | cli | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/cli/init.py` | Ollama messaging (lines 286-301) updated to reflect that Ollama auto-config goes to global config, not project config. Project config messaging says "scan-ready" without referencing smart content. | Per validation: messaging was missed |
| [x] | T004 | Verify end-to-end | cli | — | In a temp dir: (1) run `fs2 init`, verify project config has only `scan:` active, (2) verify global config has full template, (3) run `fs2 scan` and confirm it completes with "not configured" skips for smart content/embeddings. `--force` regenerates project config only (document this). | AC1-AC6. Note: no existing test file for init — manual verification. |

### Acceptance Criteria

- [ ] AC1 — Project config is scan-only: only `scan:` uncommented
- [ ] AC2 — Global config keeps full template
- [ ] AC3 — Zero-edit first scan: `fs2 init && fs2 scan` works
- [ ] AC4 — Ollama auto-detection targets global only
- [ ] AC5 — --force flag still works
- [ ] AC6 — Existing tests pass

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Two template strings to maintain | Low | Low | PROJECT_CONFIG is a mechanical transformation of DEFAULT_CONFIG — comment out 2 sections |
| `--force` only affects project config, not global | Low | Low | Document this — existing behavior, not a regression |
| Old global configs never get updated template | Low | Low | Init skips existing globals — user can delete and re-run if needed |

### Known Limitations

- `fs2 init --force` only regenerates the project config. Global config is skip-if-exists. Users who want a fresh global config can delete `~/.config/fs2/config.yaml` and re-run init.

---

## Validation Record (2026-04-14)

| Agent | Lenses Covered | Issues | Verdict |
|-------|---------------|--------|---------|
| Coherence | System Behavior, Integration & Ripple, Domain Boundaries, Hidden Assumptions | 2 MEDIUM, 1 LOW — all fixed | ✅ |
| Risk | Edge Cases, User Experience, Deployment & Ops, Hidden Assumptions | 1 HIGH, 4 MEDIUM — all fixed | ✅ |
| Completeness | Technical Constraints, Concept Documentation | 2 MEDIUM, 1 LOW — all fixed | ✅ |

Overall: ⚠️ VALIDATED WITH FIXES — CS bumped to CS-2, T002/T003 merged and clarified with control flow restructuring, messaging task added, test file reference fixed, --force semantics documented.
