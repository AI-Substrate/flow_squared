# Execution Log — Phase 4: Server Query API

**Plan**: [../../server-mode-plan.md](../../server-mode-plan.md)
**Phase**: Phase 4: Server Query API
**Started**: 2026-03-06
**Completed**: 2026-03-06

---

## Task Progress

| ID | Task | Status | Evidence |
|----|------|--------|----------|
| T001 | Tree query + filtered nodes | ✅ done | `get_filtered_nodes_async()`, `get_children_count_async()`, `has_embeddings_async()` added to graph_store_pg.py |
| T002 | Text/regex search SQL | ✅ done | `search_text_async()`, `search_regex_async()` with trigram ILIKE/~ and heuristic scoring |
| T003 | PgvectorSemanticMatcher | ✅ done | New `pgvector_matcher.py` in search domain. HNSW cosine via `<=>` operator. Multi-graph `IN(...)`. |
| T004 | Query routes | ✅ done | `routes/query.py`: GET tree (folder hierarchy), search (4 modes), get-node (children_count) |
| T005 | Multi-graph search | ✅ done | `GET /api/v1/search` with `graph=all|name1,name2`. Single SQL `IN(...)`, no fan-out. |
| T006 | Embedding model validation | ✅ done | Auto-mode checks per-graph embedding availability. Falls back to text when no adapter/embeddings. |
| T007 | Response format parity | ✅ done | SearchResult envelope (meta+results), TreeNode shape, CodeNode detail levels match local |
| T008 | Wire query router | ✅ done | `query_router` mounted in app.py. list-graphs enhanced with `?status=` filter. |
| T009 | Tests | ✅ done | 19 new tests: tree (5), get-node (3), search (3), multi-graph (3), list-graphs (1), format parity (4) |

## Decisions Made

1. **No CTE for folders** — tree folder hierarchy uses Python path-splitting (same as TreeService), SQL just fetches filtered nodes (DYK #3)
2. **Single SQL for multi-graph** — `WHERE graph_id IN (...)` not fan-out (DYK #2)
3. **EmbeddingAdapter wiring deferred** — app.state.embedding_adapter = None for now, search falls back to text. Wired when server gets its own config.
4. **FastAPI `pattern` param** instead of deprecated `regex` for Query validation

## Test Results

```
52 server tests passed, 2 deselected (slow) in 2.13s
Full suite: 1590 passed, 25 skipped, 343 deselected in 54.48s
Lint: All checks passed (ruff)
```
