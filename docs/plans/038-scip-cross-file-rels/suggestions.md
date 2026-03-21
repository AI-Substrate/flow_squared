# Suggestions — SCIP Cross-File Relationships

Future improvements identified during planning but deferred from the current implementation.

---

## 1. Per-Project Incremental Resolution

**Current**: `get_changed_file_paths()` and `reuse_prior_edges()` operate on the flat `context.nodes` list globally. A change in `frontend/app.ts` triggers re-indexing of *all* projects (including Python), because the changed-files set has no concept of which project a node belongs to.

**Suggested**: Track which project produced which edges and which `index.scip` hash was used. Only re-run the indexer for projects whose source files actually changed. Cache `index.scip` per project slug and compare project-level content hashes.

**Impact**: Significant scan-time reduction for multi-project repos. Currently each indexer runs every scan even if its project is unchanged.

**Complexity**: Medium — requires per-project edge tagging in `context.cross_file_edges` and a project-hash comparison layer on top of T004's cache directory.

---
