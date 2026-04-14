# Research Dossier — 048 Better Documentation

> **Feature**: Rewrite README to explain what fs2 actually does, its value proposition, and differentiating capabilities
> **Branch**: `048-better-documentation`
> **Research Date**: 2026-04-13

---

## Executive Summary

The current README (`README.md:1-456`) opens with a one-liner — *"Code intelligence for your codebase"* — then jumps straight into installation mechanics. **It never explains what fs2 actually does, why it's different, or why someone should care.** The "wow factor" features (node decomposition, smart content, dual-channel semantic search, cross-file relationship graphs, multi-repo querying) are scattered across subsections or buried in separate docs. A newcomer reading the README has no idea what makes fs2 special.

### The Core Gap

| What the README does well | What's missing entirely |
|---------------------------|------------------------|
| Installation (3 methods) | What fs2 does conceptually |
| CLI command reference | Why use fs2 vs grep/ripgrep/ctags |
| MCP setup (3 clients) | The value pipeline story |
| Config examples | "Wow factor" feature highlights |
| Language support table | Real-world use cases (25+ repos) |

---

## Research Findings

### Thread 1: The Pipeline Story (IA-01 → IA-10)

fs2 transforms raw source code through a multi-stage enrichment pipeline:

```
Raw Source Files
    ↓ tree-sitter parsing (40+ languages)
Individual Code Nodes (methods, classes, functions, types)
    ↓ AI-powered summarization (LLM)
Smart Content (1-2 sentence purpose summaries)
    ↓ vector embedding (code + summaries)
Dual Embeddings (raw code chunks + summary chunks)
    ↓ SCIP cross-file analysis
Relationship Graph (imports, calls, type usage)
    ↓ NetworkX persistence
Queryable Code Graph (.fs2/graph.pickle)
    ↓ unified search + MCP
Text / Regex / Semantic Search → AI Agent Tools
```

**Key implementation refs:**
- Scan orchestration: `src/fs2/core/services/scan_pipeline.py:140-315`
- AST decomposition: `src/fs2/core/adapters/ast_parser_impl.py:622-823`
- Smart content: `src/fs2/core/services/smart_content/smart_content_service.py:234-290`
- Embedding (dual): `src/fs2/core/services/embedding/embedding_service.py:220-298`
- Cross-file refs: `src/fs2/core/services/stages/cross_file_rels_stage.py:251-414`
- Search (all modes): `src/fs2/core/services/search/search_service.py:121-239`
- Multi-graph: `src/fs2/core/services/graph_service.py:322-395`

### Thread 2: Differentiating Features (PS-01 → PS-10)

What makes fs2 different from grep, ripgrep, ctags, or other code search tools:

1. **Node Decomposition** (PS-03): Not file-level — breaks code into individual methods, classes, functions, blocks. Each becomes a first-class searchable node with context, signature, and qualified name. Supports 40+ languages via tree-sitter with zero per-language config.

2. **Smart Content** (PS-04): Each node gets an AI-generated 1-2 sentence summary explaining what it does. This means you can search for "authentication middleware" and find the right function even if the code never uses that exact phrase. Templates are category-specific (file/type/callable/section/block).

3. **Dual-Channel Search** (PS-09): Semantic search checks BOTH raw code embeddings AND smart content embeddings, picking the best match. This makes "what does this do?" queries work alongside exact code pattern queries.

4. **Content-Aware Chunking** (PS-05): Code uses 400-token chunks for precision; documentation uses 800-token chunks for narrative context. Not one-size-fits-all.

5. **Real Graph, Not Flat Index** (PS-08): Uses NetworkX DiGraph with both containment edges (parent→child) and reference edges (cross-file). Enables traversal, impact analysis, and relationship queries that flat indexes can't do.

6. **Incremental Scans** (PS-07): Hash-driven — only regenerates smart content, embeddings, and cross-file refs for nodes whose content actually changed. Makes re-scanning large codebases fast.

7. **Multi-Repository** (DB-06): Query across 25+ codebases from one installation. Each repo is a named graph; search and MCP tools accept `graph_name` to target or query all.

8. **Cross-File Relationships** (IA-07): SCIP-derived import/call/type-usage edges mapped back to fs2 nodes. Shows "who calls this" and "what does this depend on" across files.

### Thread 3: Documentation Gaps (DE-01 → DE-10)

| Gap | Severity | Where it should go |
|-----|----------|-------------------|
| No "what fs2 does" explanation | 🔴 Critical | README, top section |
| No value proposition / differentiator | 🔴 Critical | README, after "what" |
| No pipeline visualization | 🟡 High | README, "How It Works" |
| Docs list understated (2 of 11 shown) | 🟡 High | README, Guides section |
| Multi-repo value story weak | 🟡 High | README + multi-graphs.md |
| No end-to-end narrative anywhere | 🟡 High | README, "How It Works" |
| Smart content not explained to users | 🟡 High | README + scanning.md |
| Dual-channel search not highlighted | 🟠 Medium | README, search section |

### Thread 4: Prior Learnings (PL-01 → PL-12)

Key insights from previous plans:
- **PL-04**: Best specs explain user value, not just mechanics → README needs "why this matters" blocks
- **PL-11**: Docs double as onboarding for humans AND agents → order by journey, not implementation
- **PL-02**: READMEs should be guided subsections, not flat option dumps
- **PL-03**: Some features are "docs/how only" — don't force everything into README
- **PL-06**: Bootstrap UX matters — docs should be reachable before MCP is working

### Thread 5: Service Architecture (DC-01 → DC-10)

The service composition map that powers the pipeline:

```
CLI Commands
    ↓
FS2ConfigurationService (config registry)
    ↓
ScanPipeline
    ├── DiscoveryStage → FileScanner adapter
    ├── ParsingStage → ASTParser adapter (tree-sitter)
    ├── CrossFileRelsStage → SCIP adapters (5 languages)
    ├── SmartContentStage → SmartContentService → LLMService → LLMAdapter
    ├── EmbeddingStage → EmbeddingService → EmbeddingAdapter
    └── StorageStage → GraphStore (NetworkX)

SearchService
    ├── TextMatcher (substring)
    ├── RegexMatcher (with timeout)
    └── SemanticMatcher → EmbeddingAdapter (dual-channel)

GraphService → named graph loading (multi-repo)
MCP Server → tree/search/get_node/docs tools
```

### Thread 6: Quality & Maturity (QT-01 → QT-10)

- **1,977 tests** across 170 files
- **Fakes over mocks** pattern (0 mock violations, 8 ABC-based fakes)
- **Graceful degradation** — works without LLM, without embeddings, without SCIP
- **67% embedding coverage** — room to grow but solid orchestration coverage
- No formal benchmark suite, but incremental scanning + subprocess timeouts handle scale

### Thread 7: Public API Surface (IC-01 → IC-10)

**CLI**: 17 commands including `scan`, `tree`, `search`, `get-node`, `mcp`, `watch`, `doctor`, `report`, `init`, `docs`, `list-graphs`, `discover-projects`, `add-project`, `install`, `upgrade`, `setup-mcp`, `agents-start-here`

**MCP**: 6 tools — `tree`, `get_node`, `search`, `docs_list`, `docs_get`, `list_graphs` — all with `graph_name` parameter for multi-repo

**CodeNode**: 28 fields including `smart_content`, `embedding`, `smart_content_embedding`, `leading_context`, `signature`, `qualified_name`

---

## Conceptual Domains for Documentation

Based on DB-01 → DB-08, the natural documentation domains are:

| Domain | What to explain | README depth |
|--------|----------------|-------------|
| **Parsing & Decomposition** | tree-sitter, 40+ languages, node types | Headline feature |
| **Smart Content** | AI summaries, "searchable meaning" | Headline feature |
| **Embeddings** | Dual vectors, content-aware chunking | Mentioned, link to guide |
| **Cross-File Relationships** | SCIP, import graphs, "who calls this" | Headline feature |
| **Search** | Text/regex/semantic, dual-channel | Headline feature |
| **Multi-Repository** | Named graphs, 25+ repos, cross-codebase | Headline feature |
| **MCP Server** | AI agent integration, tool surface | Existing (good) |
| **Configuration** | LLM/embedding providers, YAML/env | Existing (good) |

---

## Recommendations for README Rewrite

1. **Add a "What fs2 Does" section** immediately after the title — explain the pipeline in 3-4 sentences
2. **Add a "How It Works" section** with the pipeline diagram — show the transformation from raw code to searchable graph
3. **Add a "Key Features" section** highlighting the 6-8 differentiators — each with a one-liner + "why it matters"
4. **Keep existing Installation, MCP, Scanning sections** — they're good, just need to come after the value story
5. **Add a "Why fs2?" comparison** — quick table showing what fs2 does that grep/ripgrep/ctags don't
6. **Update the Guides table** — show all 11 bundled docs, not just 2
7. **Tell the multi-repo story** — mention the 25+ repo legacy codebase use case
