# Smart Content Category Filter — Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-03-15
**Spec**: [smart-content-node-filter-spec.md](smart-content-node-filter-spec.md)
**Status**: DRAFT

## Summary

Add `enabled_categories` field to SmartContentConfig so users can limit smart content generation to specific node categories (e.g., files only). ~30 lines across 5 files. Default `null` preserves current behavior. Filtering to `["file"]` cuts LLM calls by ~85%.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| config | existing | modify | Add `enabled_categories` field + validator |
| stages | existing | modify | Category filter in SmartContentStage |
| cli | existing | modify | DEFAULT_CONFIG template |
| docs | existing | modify | Config guide + local-llm guide |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/config/objects.py` | config | internal | Add field + validator to SmartContentConfig |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/smart_content_stage.py` | stages | internal | Filter nodes before batch processing |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/init.py` | cli | internal | DEFAULT_CONFIG template |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/configuration-guide.md` | docs | contract | Document new config option |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/local-llm.md` | docs | contract | Mention category filtering |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/config/test_smart_content_config.py` | config | internal | Validation tests |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_smart_content_stage.py` | stages | internal | Filtering tests |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | High | SmartContentConfig already has per-category `token_limits` dict — pattern established | Follow same pattern for `enabled_categories` |
| 02 | Medium | SmartContentStage filters only by `smart_content is None` at line ~114 | Insert category filter after existing filter |
| 03 | Low | 9 valid categories: file, callable, type, block, section, definition, statement, expression, other | Use as validation set |

## Implementation

**Objective**: Add `enabled_categories` config field and apply filter in SmartContentStage
**Testing Approach**: Lightweight — config validation + stage filtering tests

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [ ] | T001 | Add `enabled_categories` field + validator to SmartContentConfig | config | `src/fs2/config/objects.py` | Field accepts list of valid categories or null; invalid categories raise ValidationError | AC01, AC02, AC04 |
| [ ] | T002 | Add category filter in SmartContentStage.process() | stages | `src/fs2/core/services/stages/smart_content_stage.py` | Nodes not in enabled_categories are skipped for smart content but remain in graph | AC01, AC03, AC05 |
| [ ] | T003 | Write config validation tests | config | `tests/unit/config/test_smart_content_config.py` | Tests: null=all, valid list, invalid category rejected | AC02, AC04, AC06 |
| [ ] | T004 | Write stage filtering test | stages | `tests/unit/services/stages/test_smart_content_stage.py` | Test: enabled_categories=["file"] skips callable nodes | AC01, AC05 |
| [ ] | T005 | Update DEFAULT_CONFIG with commented enabled_categories example | cli | `src/fs2/cli/init.py` | Config template shows `# enabled_categories: ["file"]` | G1 |
| [ ] | T006 | Update docs: config guide + local-llm guide | docs | `docs/how/user/configuration-guide.md`, `docs/how/user/local-llm.md` | Category filtering documented with YAML examples | G1 |

### Acceptance Criteria

- [ ] AC01: `enabled_categories: ["file"]` → only files get smart content
- [ ] AC02: `enabled_categories: null` → all categories processed (backward compatible)
- [ ] AC03: ~850 LLM calls instead of ~5,700 when filtering to files
- [ ] AC04: Invalid category → validation error
- [ ] AC05: Filtered nodes still in graph with full content/embeddings
- [ ] AC06: `enabled_categories: ["file", "type"]` → files and types get smart content

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Users confused by missing summaries | Low | Low | Document in config comments |

## Progress

- Tasks: 0/6 complete
- ACs verified: 0/6
