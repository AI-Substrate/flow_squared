# Smart Content Category Filter

**Mode**: Simple
📚 This specification incorporates findings from `exploration.md`.

## Summary

Allow users to limit smart content generation to specific node categories (e.g., files only) via a config option. This reduces LLM cost and scan time by ~85% when generating summaries only for file-level nodes, while keeping all nodes in the graph with full source code, embeddings, and relationships.

**WHY**: A codebase with 5,700 nodes takes ~2.5 hours for full smart content generation. Most users only need file-level summaries — method/class code is readable directly. Filtering to files reduces this to ~20 minutes with no loss of graph structure, search, or embeddings.

## Goals

- **G1**: Users can configure which node categories get smart content via `enabled_categories` in YAML config
- **G2**: Nodes not in the enabled list still exist in the graph with full content, embeddings, and relationships — only `smart_content` field is skipped
- **G3**: Default behavior is unchanged (`enabled_categories: null` = all categories processed)
- **G4**: Scan progress and summary reflect the filtered count, not total nodes

## Non-Goals

- **NG1**: Filtering which nodes get parsed or stored — all nodes stay in the graph
- **NG2**: Filtering which nodes get embeddings — embedding stage is separate
- **NG3**: Adding a CLI flag (config-only for now; CLI override is future scope)
- **NG4**: Per-file or per-path filtering — this is category-level only

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| config | existing | **modify** | Add `enabled_categories` field to SmartContentConfig |
| stages | existing | **modify** | Add category filter in SmartContentStage.process() |
| cli | existing | **modify** | Update DEFAULT_CONFIG template with commented example |
| docs | existing | **modify** | Document in configuration guide and local-llm guide |

ℹ️ No domain registry exists.

## Complexity

- **Score**: CS-1 (trivial)
- **Breakdown**: S=1, I=0, D=0, N=0, F=0, T=1 → Total P=2
  - **S=1** (Surface Area): Config + stage + docs — multiple files but minimal changes
  - **I=0** (Integration): Pure internal, no external dependencies
  - **D=0** (Data/State): No schema changes — CodeNode unchanged
  - **N=0** (Novelty): Well-specified from exploration, existing per-category pattern
  - **F=0** (Non-Functional): No performance/security concerns
  - **T=1** (Testing): Config validation tests + stage filtering test
- **Confidence**: 0.95
- **Assumptions**: SmartContentConfig and SmartContentStage are stable (confirmed by exploration)
- **Dependencies**: None
- **Risks**: None identified
- **Phases**: Single implementation phase

## Acceptance Criteria

1. **AC01**: Given `enabled_categories: ["file"]` in config, when `fs2 scan` runs, then only file-category nodes get smart content generated; callable/type/block nodes have `smart_content: null`
2. **AC02**: Given `enabled_categories: null` (or field absent) in config, when `fs2 scan` runs, then all categories are processed (backward compatible)
3. **AC03**: Given `enabled_categories: ["file"]`, when scanning a codebase with 5,700 nodes (~850 files), then only ~850 LLM calls are made (not 5,700)
4. **AC04**: Given `enabled_categories: ["invalid_category"]` in config, when config is loaded, then a validation error is raised listing valid categories
5. **AC05**: Given a node filtered out by `enabled_categories`, then it still exists in the graph with full content, embeddings, and relationships — only `smart_content` is null
6. **AC06**: Given `enabled_categories: ["file", "type"]` in config, then both file and type nodes get smart content, but callables do not

## Risks & Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Users confused why some nodes lack summaries | Low | Low | Document in config comments + local-llm guide |

**Assumptions**:
- File-level smart content is the highest-value category for most users
- Existing per-category `token_limits` in SmartContentConfig proves the pattern is accepted

## Open Questions

*None.*

## Testing Strategy

- **Approach**: Lightweight
- **Focus**: Config validation (valid/invalid categories), stage filtering (files only vs all)
- **Excluded**: SmartContentService internals (unchanged), template rendering (unchanged)

## Clarifications

### Session 2026-03-15

| # | Question | Answer | Spec Impact |
|---|----------|--------|-------------|
| Q1 | Workflow Mode | **Simple** | Header updated |
| Q2 | Testing Strategy | **Lightweight** — config test + stage test | Added Testing Strategy section |
| Q3 | Domain Review | **Confirmed** — all existing, no contract changes | No changes needed |
