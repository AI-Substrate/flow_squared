# Exploration: Smart Content Node Category Filter

> **Plan ID**: 035-smart-content-node-filter
> **Date**: 2026-03-15
> **Branch**: 031-cross-file-rels-take-2
> **Feature**: Allow limiting smart content generation to specific node categories (e.g., files only)

---

## Executive Summary

SmartContentConfig **already has per-category token limits** (`token_limits` dict) but lacks an `enabled_categories` filter. Currently ALL 9 node categories (file, callable, type, block, section, statement, expression, definition, other) are processed. Adding a filter is ~30 lines of code:

1. **Add `enabled_categories` field** to SmartContentConfig (default None = all)
2. **Filter in SmartContentStage.process()** before calling process_batch()
3. **Update DEFAULT_CONFIG** and docs

For a codebase with 5,700 nodes where ~800 are files, filtering to "file" reduces LLM calls by **~85%** and scan time from ~2.5 hours to ~20 minutes.

---

## Key Findings

| ID | Finding | Impact |
|----|---------|--------|
| IA-01 | SmartContentStage filters only by `smart_content is None` — no category filter | Where to add filter |
| IA-02 | `_should_skip()` checks hash only, not category | Stage-level filter preferred over service-level |
| IA-03 | SmartContentConfig has `token_limits` per category but no `enabled_categories` | Pattern exists, just add the field |
| IA-04 | 9 categories exist: file, callable, type, block, section, definition, statement, expression, other | "file" is the high-value target |
| IA-06 | TemplateService already selects templates per category | Architecture ready |
| IA-07 | File-level smart_content most valuable for search/MCP/reports | Validates file-only default |
| DC-03 | No `--smart-content-categories` CLI flag exists | Opportunity for quick override |
| DC-06 | SmartContentConfig flows via SmartContentService → `config.require()` | Clean config path |

---

## Node Category Distribution (fs2 codebase: 5,710 nodes)

| Category | Count | % | Value for Smart Content |
|----------|-------|---|------------------------|
| callable | 3,636 | 64% | Medium — code is readable directly |
| type | 1,060 | 19% | Medium — class summaries useful |
| file | 846 | 15% | **High** — file-level overview most valuable |
| block | 168 | 3% | Low |

Filtering to `["file"]` → 846 LLM calls instead of 5,710 (~85% reduction).
Filtering to `["file", "type"]` → 1,906 calls (~67% reduction).
Filtering to `["file", "type", "callable"]` → 5,542 calls (~3% reduction — minimal savings).

---

## What Needs to Change

### 1. SmartContentConfig — add `enabled_categories` field
**File**: `src/fs2/config/objects.py` (~10 lines)
```python
enabled_categories: list[str] | None = Field(
    default=None,  # None = all categories (backward compatible)
)
```

### 2. SmartContentStage — filter before batch
**File**: `src/fs2/core/services/stages/smart_content_stage.py` (~5 lines)
```python
if smart_content_config.enabled_categories is not None:
    needs_generation = [n for n in needs_generation 
                        if n.category in smart_content_config.enabled_categories]
```

### 3. DEFAULT_CONFIG — document the option
**File**: `src/fs2/cli/init.py` (~3 lines)
```yaml
smart_content:
  max_workers: 50
  max_input_tokens: 50000
  # enabled_categories: ["file"]  # Uncomment to generate summaries for files only
```

### 4. Docs — update config guide and local-llm.md

---

## Estimated Scope

**CS-1 (trivial)** — ~30 lines of implementation, well-understood pattern, no architectural changes. Config field + stage filter + docs.

---

## Files Referenced

### To modify
- `src/fs2/config/objects.py` — SmartContentConfig (add field + validator)
- `src/fs2/core/services/stages/smart_content_stage.py` — Add filter (~L114)
- `src/fs2/cli/init.py` — DEFAULT_CONFIG template
- `docs/how/user/local-llm.md` — Mention category filtering
- `docs/how/user/configuration-guide.md` — Document new config option

### Reference (no changes needed)
- `src/fs2/core/services/smart_content/smart_content_service.py` — process_batch unchanged
- `src/fs2/core/services/smart_content/template_service.py` — category-aware, no changes
- `src/fs2/core/models/code_node.py` — category field definition
