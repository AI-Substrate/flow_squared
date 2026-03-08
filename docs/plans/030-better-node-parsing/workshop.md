# Workshop: Fixing Anonymous TS Node Extraction — Learning from FastCode

**Type**: Integration Pattern / Data Model
**Created**: 2026-03-08
**Status**: Draft

**Related Documents**:
- FastCode vs fs2 dossier (below in this file)
- Anonymous @Node analysis (below in this file)

**Repository Access**:
- **fs2 source**: `/Users/jordanknight/substrate/fs2/028-server-mode/` (this repo)
- **FastCode source**: Available via multi-graph at `~/github/fastcode/` — also configured as an fs2 external graph (see `.fs2/config.yaml` → `other_graphs.graphs[name=fastcode]`)
- **Chainglass graph** (the problematic graph): `/Users/jordanknight/substrate/066-wf-real-agents/.fs2/graph.pickle` (450MB)

---

## Purpose

Guide an implementing agent through fixing fs2's TypeScript/TSX parser to stop producing thousands of useless anonymous `@line.column` nodes. FastCode's parser already solves this problem elegantly — this workshop explains what FastCode does, how fs2 currently fails, and how to bridge the gap.

## Key Questions Addressed

- Why does fs2 produce 13,649 anonymous nodes from a TS/TSX codebase?
- How does FastCode avoid this problem?
- What's the minimal change to fs2's parser to fix it?
- How can you inspect the problematic graph to verify fixes?

---

## Accessing FastCode Source Code

FastCode is registered as an external graph in this project's `.fs2/config.yaml`:

```yaml
other_graphs:
  graphs:
    - name: fastcode
      path: ~/github/fastcode/.fs2/graph.pickle
      description: FastCode repository
```

**Via MCP tools** (if the MCP server has restarted since config change):
```python
# Browse FastCode structure
tree(pattern="fastcode/", graph_name="fastcode")

# Get a specific file
get_node(node_id="file:fastcode/parser.py", graph_name="fastcode")

# Search FastCode code
search(pattern="arrow_function", graph_name="fastcode")
```

**Via CLI**:
```bash
fs2 --graph-name fastcode tree
fs2 --graph-name fastcode search "arrow_function"
```

**Direct file access** (if MCP graph lookup returns null for get_node on external graphs — this was observed during analysis):
```bash
cat ~/github/fastcode/fastcode/parser.py
cat ~/github/fastcode/fastcode/tree_sitter_parser.py
```

The key file is `~/github/fastcode/fastcode/parser.py` — specifically the methods `_extract_ts_classes_and_functions()` (line ~838) and `_extract_js_function()` (line ~660).

---

## Inspecting the Problematic Chainglass Graph

The graph at `/Users/jordanknight/substrate/066-wf-real-agents/.fs2/graph.pickle` is a tuple `(metadata_dict, networkx.DiGraph)`. Here's how to load and inspect it:

```python
import pickle, re
from collections import Counter

GRAPH_PATH = "/Users/jordanknight/substrate/066-wf-real-agents/.fs2/graph.pickle"

with open(GRAPH_PATH, "rb") as f:
    meta, graph = pickle.load(f)

# meta is a dict with 7 keys (scan metadata)
# graph is a networkx.DiGraph with 23,283 nodes

# Each node: graph.nodes[node_id]["data"] is a CodeNode object
# Key CodeNode attributes:
#   .node_id        - e.g., "callable:test/unit/foo.test.ts:@19.29"
#   .name           - e.g., "@19.29" (anonymous) or "myFunction" (named)
#   .category       - "callable" | "type" | "file"
#   .ts_kind        - tree-sitter node type: "arrow_function", "interface_body", etc.
#   .content        - raw source code
#   .smart_content  - LLM-generated summary
#   .embedding      - numpy array or None
#   .start_line / .end_line
#   .parent_node_id - node_id of parent for hierarchy
#   .file_path      - EMPTY in this graph (path is in node_id instead)
#   .language        
#   .qualified_name - e.g., "@19.29.@34.41.@35.55" (deeply nested)

# Find all anonymous nodes
at_pat = re.compile(r'@\d+')
for node_id, data in graph.nodes(data=True):
    obj = data.get("data")
    if obj and at_pat.search(obj.name):
        print(f"[{obj.category}] {obj.ts_kind}: {obj.name} in {node_id}")
```

### Graph Statistics (pre-computed)

| Metric | Value |
|--------|-------|
| Total nodes | 23,283 |
| Anonymous @nodes | 13,649 (58.6%) |
| Named nodes | 9,634 |
| @nodes content | 10.4 MB |
| @nodes smart_content | 3.2 MB (wasted LLM calls) |
| @nodes with embeddings | 13,504 (wasted embedding API calls) |
| **@nodes % of total text** | **67%** |
| Graph file size | 450 MB |

### Breakdown by tree-sitter `ts_kind`

| `ts_kind` | @anonymous count | What it is |
|-----------|-----------------|------------|
| `arrow_function` | **11,456** (84%) | Callbacks: `describe(() => {`, `it(() => {`, handlers |
| `interface_body` | 1,176 | `{ ... }` body of interface declarations |
| `function_type` | 602 | Type annotations: `(x: string) => boolean` |
| `class_body` | 220 | `{ ... }` body of class declarations |
| `class_heritage` | 192 | `extends Foo` / `implements Bar` clauses |
| `enum_body` | 2 | Enum bodies |

### Breakdown by file type

| Extension | @anonymous | Named | % anonymous |
|-----------|-----------|-------|-------------|
| `.ts` | 10,984 | 5,650 | **66%** |
| `.tsx` | 2,659 | 709 | **79%** |

---

## How FastCode Solves This

FastCode's `_extract_js_function()` in `~/github/fastcode/fastcode/parser.py` (line ~660):

```python
def _extract_js_function(self, node, content, code_bytes, class_name=None):
    try:
        # Get function name
        name_node = None
        for child in node.children:
            if child.type == 'identifier':
                name_node = child
                break

        if not name_node:
            return None  # <-- THIS IS THE KEY LINE

        func_name = code_bytes[name_node.start_byte:name_node.end_byte].decode('utf-8')
        # ... extract params, docstring, etc.
```

**The critical behavior**: When an `arrow_function` has no `identifier` child (i.e., it's anonymous — a callback like `() => {`), FastCode returns `None`. The caller discards it:

```python
def _extract_ts_classes_and_functions(self, root_node, content, classes, functions):
    def visit_node(node, current_class=None):
        if node.type in ('function_declaration', 'arrow_function', 'function'):
            func_info = self._extract_js_function(node, content, code_bytes, current_class)
            if func_info:           # <-- None gets filtered out
                functions.append(func_info)
        else:
            for child in node.children:
                visit_node(child, current_class)  # <-- Still recurses!
```

**Crucially, it still recurses into children** of the anonymous node via the `else` branch, so named functions *nested inside* anonymous callbacks are still extracted. Only the anonymous wrapper itself is skipped.

### What FastCode extracts from TS:
- `function_declaration` — only if it has an identifier ✅
- `arrow_function` — only if assigned to a named variable ✅
- `class_declaration` — only if it has an identifier ✅
- `interface_declaration` — only if it has an identifier ✅
- `method_definition` — these always have names ✅
- `method_signature` — these always have names ✅

### What FastCode does NOT extract:
- Anonymous arrow functions (callbacks) ❌
- `interface_body` ❌
- `class_body` ❌
- `class_heritage` ❌
- `function_type` (type annotations) ❌
- `enum_body` ❌

---

## How fs2 Currently Works (The Problem)

### Step 1: `classify_node()` (`src/fs2/core/models/code_node.py:27`)

This is a **language-agnostic pattern matcher** that maps `ts_kind` → category:

```python
def classify_node(ts_kind: str) -> str:
    # ...
    if any(x in ts_kind for x in ("function", "method", "lambda", "procedure")):
        return "callable"
    if any(x in ts_kind for x in ("class", "struct", "interface", "enum", "type_alias", "trait", "impl")):
        return "type"
    # ...
```

This means:
- `arrow_function` → `"callable"` (contains "function") — **ALL arrow fns become callable nodes**
- `interface_body` → `"type"` (contains "interface") — **interface bodies become type nodes**
- `class_body` → `"type"` (contains "class") — **class bodies become type nodes**
- `class_heritage` → `"type"` (contains "class") — **heritage clauses become type nodes**
- `function_type` → `"callable"` (contains "function") — **type annotations become callable nodes**
- `enum_body` → `"type"` (contains "enum") — **enum bodies become type nodes**

### Step 2: `_extract_nodes()` (`src/fs2/core/adapters/ast_parser_impl.py:570`)

For any node with category in `("type", "callable", "section", "block")`, it:
1. Tries `_extract_name()` — returns `None` for anonymous nodes
2. Falls back to `@{line}.{col}` naming
3. Creates a full CodeNode with content, signature, etc.
4. **Then recurses into children** — creating nested anonymous nodes

```python
# Line 658-666
name = self._extract_name(child, language)
if name is None:
    # Anonymous node - use position-based ID per CF11
    line = child.start_point[0] + 1
    col = child.start_point[1]
    name = f"@{line}.{col}"
```

### Step 3: Smart content + embedding

Every node (including all 13,649 anonymous ones) gets:
- LLM smart content generation (~11K API calls wasted)
- Embedding generation (~13.5K embedding API calls wasted)

---

## Recommended Fix Strategy

### Approach: Skip anonymous nodes for specific ts_kinds

The fix should be in `_extract_nodes()` in `ast_parser_impl.py`, AFTER categorization but BEFORE node creation. When `_extract_name()` returns `None`, check whether the `ts_kind` is one that should be skipped when anonymous:

```python
# After line 659 in ast_parser_impl.py
name = self._extract_name(child, language)
if name is None:
    # Skip anonymous nodes for ts_kinds that are never useful unnamed
    # (per FastCode pattern: anonymous arrow functions, body wrappers, type annotations)
    skip_when_anonymous = {
        "arrow_function",       # Callbacks: describe(() => {), it(() => {)
        "function",             # Anonymous function expressions
        "function_expression",  # Same
        "generator_function",   # Anonymous generators
        "interface_body",       # Body of interface (parent has the name)
        "class_body",           # Body of class (parent has the name)  
        "class_heritage",       # extends/implements clause (parent has context)
        "enum_body",            # Body of enum (parent has the name)
        "function_type",        # Type annotation like (x: string) => boolean
        "implements_clause",    # implements Foo
    }
    if ts_kind in skip_when_anonymous:
        # Still recurse to find named children inside (e.g., named function inside a callback)
        self._extract_nodes(
            node=child,
            file_path=file_path,
            language=language,
            content_type=content_type,
            content=content,
            nodes=nodes,
            depth=depth,
            parent_qualified_name=parent_qualified_name,
            parent_node_id=parent_node_id,
            seen_node_ids=seen_node_ids,
        )
        continue
    
    # For other anonymous nodes, keep the @line.col fallback
    line = child.start_point[0] + 1
    col = child.start_point[1]
    name = f"@{line}.{col}"
```

### Why this approach:

1. **Minimal change** — a single `if` block added to existing logic
2. **Still recurses** — named functions nested inside callbacks are still found
3. **Language-agnostic set** — these ts_kinds are specific enough; no language handler needed
4. **Preserves @-naming for legitimate cases** — e.g., unnamed Python decorators or unnamed Go goroutines still get @-names where appropriate

### Alternative: TypeScript Language Handler

A cleaner long-term approach is creating a `TypeScriptHandler` (like `PythonHandler`) in `src/fs2/core/adapters/ast_languages/` that adds these to `container_types`. But the container_types mechanism skips extraction AND name lookup entirely — which might not be right for `arrow_function` since named arrow functions SHOULD be extracted. The `skip_when_anonymous` approach is more precise.

### Testing the Fix

After applying the fix, re-scan the chainglass project and compare:

```bash
cd /Users/jordanknight/substrate/066-wf-real-agents
uv run --project /Users/jordanknight/substrate/fs2/028-server-mode \
    fs2 scan --no-smart-content --no-embeddings

# Then inspect:
uv run --project /Users/jordanknight/substrate/fs2/028-server-mode \
    python -c "
import pickle, re
from collections import Counter
with open('.fs2/graph.pickle', 'rb') as f:
    meta, graph = pickle.load(f)
at_pat = re.compile(r'@\d+')
total = sum(1 for _, d in graph.nodes(data=True) if d.get('data'))
at = sum(1 for _, d in graph.nodes(data=True) if d.get('data') and at_pat.search(d['data'].name))
print(f'Total: {total}, @anonymous: {at} ({at/total*100:.0f}%)')
"
```

**Expected outcome**: @anonymous nodes should drop from ~13,649 to near zero (only legitimate unnamed constructs remaining). Total nodes should drop from 23,283 to ~10,000-12,000.

### Existing Tests to Watch

There's a `skip_entirely` set already in the parser (line 611-617) that tests may cover. Run:
```bash
cd /Users/jordanknight/substrate/fs2/028-server-mode
uv run pytest tests/ -k "parser or ast_parser or tree_sitter" -x -q
```

Also check for any tests that specifically assert @-named nodes exist — those may need updating.

---

## Open Questions

### Q1: Should `arrow_function` ALWAYS be skipped when anonymous?

**LEANING YES**: In practice, anonymous arrow functions are always callbacks or IIFE patterns. The content is already captured by the parent node. FastCode skips them entirely.

**Edge case**: `export default () => { ... }` — an anonymous default export. This is rare and the file-level node captures it.

### Q2: Should this be a language handler or inline logic?

**LEANING INLINE**: The `skip_when_anonymous` set is cross-language (these ts_kinds appear in JS, TS, and TSX grammars). A language handler would need to be registered for all three. The inline approach is simpler.

### Q3: Should we also add a `_body` / `_heritage` suffix filter to `classify_node()`?

**OPEN**: Could add to `classify_node()`:
```python
# Before the substring matches:
if ts_kind.endswith(("_body", "_heritage")):
    return "other"  # Never extract bodies/heritage as standalone nodes
```
This would be more generic but might affect other languages unexpectedly.

---

---

# Anonymous @Node Problem in 066-wf-real-agents Graph

## Problem Summary

The graph at `/Users/jordanknight/substrate/066-wf-real-agents/.fs2/graph.pickle` (450MB) contains **23,283 nodes**, of which **13,649 (58.6%) are anonymous `@line.column` nodes** — unnamed code elements identified only by their source position (e.g., `@19.29`, `@34.41`). These are overwhelming the graph, consuming 67% of total text storage, and making tree/search output nearly unusable.

## Root Cause

The TS/TSX tree-sitter parser is extracting **every anonymous arrow function, interface body, class body, and function type** as a standalone node. The naming falls back to `@line.column` because these constructs have no identifier in the AST.

### Breakdown by tree-sitter node kind

| `ts_kind` | @anonymous count | What it is |
|-----------|-----------------|------------|
| `arrow_function` | **11,456** | Arrow fns: callbacks, `describe(() => {`, `it(() => {`, event handlers |
| `interface_body` | 1,176 | The `{ ... }` body of every interface declaration |
| `function_type` | 602 | Type annotations like `(x: string) => boolean` |
| `class_body` | 220 | The `{ ... }` body of every class declaration |
| `class_heritage` | 192 | `extends Foo` / `implements Bar` clauses |
| `enum_body` | 2 | Enum bodies |
| `implements_clause` | 1 | Implements clause |

**The dominant offender is `arrow_function` at 84% of all @nodes.** These are mostly:
- Test framework callbacks: `describe('...', () => {` and `it('...', () => {`
- `beforeEach(() => {` / `afterEach(() => {` hooks
- Inline callbacks and event handlers
- They nest deeply: `@19.29.@34.41.@35.55` (3 levels of nested arrow fns)

### By file type

| Extension | @anonymous | Named | % anonymous |
|-----------|-----------|-------|-------------|
| `.ts` | 10,984 | 5,650 | **66%** |
| `.tsx` | 2,659 | 709 | **79%** |
| `.mjs` | 6 | 3 | 67% |

TSX is worst at 79% anonymous because React components are built on arrow functions and JSX expressions.

### Storage Impact

| Category | Nodes | Content | Smart Content | Total Text |
|----------|-------|---------|---------------|------------|
| @anonymous | 13,649 | 10.4 MB | 3.2 MB | **13.5 MB** |
| Named | 6,362 | 4.7 MB | 1.9 MB | **6.7 MB** |

Anonymous nodes account for **67% of all text storage** and 13,504 of them have embeddings (each ~4KB for 1024-dim float32), adding ~54MB of embedding data.

### Named TS nodes (what's working correctly)

| `ts_kind` | Count | Examples |
|-----------|-------|---------|
| `method_definition` | 2,129 | Class methods with names |
| `function_declaration` | 1,838 | Named `function foo()` declarations |
| `interface_declaration` | 1,177 | Named interfaces |
| `method_signature` | 399 | Interface method signatures |
| `type_alias_declaration` | 322 | `type Foo = ...` |
| `class_declaration` | 218 | Named classes |

These are fine — they have real names and are useful nodes.

## The Core Issue in the Parser

The TypeScript tree-sitter handler is treating `arrow_function`, `interface_body`, `class_body`, `function_type`, and `class_heritage` as extractable callables/types. For these constructs:

1. **No name is found** (arrow functions are anonymous by nature)
2. The fallback naming scheme generates `@{start_line}.{start_column}`
3. Every nested callback gets its own node, creating chains like `@19.29.@34.41.@35.55`
4. Each gets smart content + embedding, burning LLM and embedding API tokens on content that's already captured by the parent node

## Recommendations

### Option A: Filter at extraction (most impactful)
Don't create nodes for anonymous arrow functions that are arguments to other calls. These are:
- Test callbacks (`describe`, `it`, `beforeEach`, etc.)
- Promise chains (`.then(() => {`)
- Event handlers (`.on('event', () => {`)

The parent node (the `describe()` call or the named variable assignment) already captures this content.

### Option B: Filter by `ts_kind` blocklist
Skip node creation for these tree-sitter kinds in TS/TSX:
- `interface_body` (the body is already part of the `interface_declaration` node)
- `class_body` (already part of `class_declaration`)
- `class_heritage` (already part of `class_declaration`)
- `function_type` (type annotation, not a real callable)
- `arrow_function` **when unnamed** (i.e., not assigned to a variable/const)

### Option C: Smart deduplication
Keep the nodes but skip smart content + embedding for anonymous nodes whose content is a subset of their parent's content.

### Expected Impact
Filtering anonymous arrow functions alone would eliminate ~11,456 nodes (49% of the graph), save ~54MB of embeddings, and avoid ~11K LLM calls for smart content generation. The graph would shrink from 450MB to roughly ~150-200MB.

---
---

# FastCode vs Flowspace2 (fs2) — Detailed Comparative Analysis

## Executive Summary

FastCode and Flowspace2 (fs2) are both **code intelligence systems** that parse, index, and expose codebases for AI-assisted understanding. They share significant conceptual overlap (tree-sitter parsing, embedding-based search, LLM enrichment, MCP server integration) but differ fundamentally in **architecture philosophy, scope, and maturity trajectory**. FastCode is an end-to-end RAG system for code Q&A with an integrated chat agent. fs2 is a structural code intelligence tool focused on scan/search/navigate with Clean Architecture rigor.

---

## 1. Project Identity & Scope

| Dimension | FastCode | fs2 (Flowspace2) |
|-----------|----------|-------------------|
| **Tagline** | Repository-Level Code Understanding System | Code intelligence for your codebase |
| **Version** | 2.0.0 | 0.1.0 |
| **Primary Use Case** | Ask questions about code, get LLM-synthesized answers | Scan, search, and navigate code structure |
| **Audience** | End users querying codebases via chat/API | AI agents (via MCP), developers exploring code |
| **Mono-repo?** | Yes — FastCode core + Nanobot agent in one tree | No — standalone package |

### Scope Differences

**FastCode** is a **full RAG pipeline**: ingest → parse → embed → index → retrieve → generate answer. It includes an LLM-powered iterative agent that refines queries across multiple retrieval rounds, a session/history system for multi-turn dialogue, and both REST API and web interface surfaces. It also bundles **Nanobot**, a complete multi-channel agent framework (Telegram, Discord, Slack, WhatsApp, DingTalk, Feishu, QQ, Email).

**fs2** is a **code graph builder + search tool**: scan → parse → build graph → enrich with smart content → embed → serve via CLI/MCP. It deliberately does **not** include answer generation, chat agents, or session management. Its value proposition is providing structured code intelligence to external AI agents (Claude, Copilot) via MCP.

---

## 2. Architecture & Code Quality

### FastCode Architecture

```
fastcode/                   # Flat module structure
├── main.py                 # God class: FastCode (1436 LOC, 32 methods)
├── parser.py               # CodeParser (1703 LOC)
├── retriever.py            # HybridRetriever (1444 LOC)
├── iterative_agent.py      # IterativeAgent (3336 LOC)
├── answer_generator.py     # AnswerGenerator (890 LOC)
├── graph_builder.py        # CodeGraphBuilder (1014 LOC)
├── vector_store.py         # VectorStore/FAISS (756 LOC)
├── embedder.py             # CodeEmbedder/SentenceTransformers (196 LOC)
├── query_processor.py      # QueryProcessor (829 LOC)
├── ...
├── api.py                  # FastAPI REST endpoints (800 LOC)
├── web_app.py              # Web interface endpoints (832 LOC)
├── mcp_server.py           # MCP server (425 LOC)
└── main.py (CLI)           # Click CLI (946 LOC)

nanobot/                    # Bundled agent framework
├── agent/                  # Agent loop, tools, subagents
├── channels/               # Telegram, Discord, Slack, WhatsApp, etc.
├── providers/              # LLM provider abstraction
├── session/                # Session management
├── cron/                   # Scheduled tasks
└── config/                 # Config schema
```

**Pattern**: Concrete classes with config dicts. No interfaces/ABCs. Direct instantiation. Classes communicate via direct references (constructor injection of concrete instances).

### fs2 Architecture

```
src/fs2/
├── cli/                    # Typer + Rich presentation layer
├── core/
│   ├── models/             # Frozen dataclasses (CodeNode, SearchResult, etc.)
│   ├── services/           # Business logic composition layer
│   │   ├── search/         # SearchService, matchers (text, regex, semantic)
│   │   ├── smart_content/  # LLM-based code summarization
│   │   ├── embedding/      # Chunking + embedding orchestration
│   │   └── stages/         # Pipeline stages (discovery, parsing, etc.)
│   ├── adapters/           # ABC interfaces + implementations
│   │   ├── *_adapter.py    # Interface (ABC)
│   │   ├── *_impl.py       # Production implementation
│   │   └── *_fake.py       # Test double (real implementations)
│   └── repos/              # Data access (GraphStore ABC + impls)
├── mcp/                    # MCP server (FastMCP)
└── config/                 # Pydantic-settings
```

**Pattern**: Clean Architecture with strict layer boundaries. ABC-based interfaces with multiple implementations (production, fake, Azure, OpenAI). Dependency injection via constructor. Fakes over mocks for testing.

### Comparative Assessment

| Metric | FastCode | fs2 |
|--------|----------|-----|
| **Total Python LOC** | ~28,300 | ~24,500 (src) |
| **Test LOC** | 0 (no tests) | ~58,650 |
| **Test files** | 0 | 178 |
| **Source files** | ~77 (.py) | 138 (.py src) |
| **Architecture** | Flat modules, concrete coupling | Clean Architecture, interface-driven |
| **Config** | Dict-based, .env files | Pydantic-settings, YAML, env precedence |
| **Error handling** | Bare exceptions, logging | Typed exception hierarchy with fix instructions |
| **Testability** | Low (no interfaces, global state) | High (ABC + fakes, DI) |

**Key observation**: FastCode has **zero test files**. fs2 has a 2.4:1 test-to-source ratio with comprehensive TDD.

---

## 3. Parsing & Language Support

### FastCode

- **Primary parser**: `libcst` (Python-specific CST parser) for deep Python analysis
- **Secondary**: `tree-sitter` with grammars for Python, JavaScript, TypeScript, Java, Go, C, C++, Rust, C#
- **Data model**: `FunctionInfo`, `ClassInfo`, `ImportInfo`, `FileParseResult` dataclasses
- **Extraction**: Functions, classes, methods, imports, docstrings, complexity metrics, decorators, return types
- **Call extraction**: Dedicated `CallExtractor` class for resolving function call sites
- **Symbol resolution**: `SymbolResolver` + `ModuleResolver` for cross-file reference resolution

### fs2

- **Parser**: `tree-sitter` exclusively, via `TreeSitterParser` adapter (895 LOC)
- **Language handlers**: Pluggable per-language handlers (`PythonHandler`, `DefaultHandler`)
- **Data model**: `CodeNode` frozen dataclass (613 LOC) — unified node representation
- **Extraction**: Files, functions, classes, methods, types (language-specific categorization)
- **Supported languages**: 40+ code languages, plus config/doc/infrastructure file types
- **No call graph**: No call extraction or cross-file symbol resolution

### Cross-File Dependency Resolution (FastCode Deep-Dive)

FastCode has a **genuine cross-file dependency resolution pipeline**, which fs2 entirely lacks:

1. **`ImportExtractor`** — Uses tree-sitter S-expression queries to extract all `import` and `from...import` statements, including relative imports with dot-level counting (`.`, `..`, etc.) and alias handling.

2. **`ModuleResolver`** — Maps import statements to target file IDs. Handles relative imports (navigates up the module hierarchy based on dot level, with special `__init__.py` package-root awareness) and absolute imports (direct lookup in a global module map). Returns `None` for third-party packages, effectively filtering to intra-repo dependencies only.

3. **`SymbolResolver`** — Given a symbol name and the current file's imports, resolves it to a definition ID using two strategies:
   - **Local resolution**: Check if the current file exports the symbol
   - **Imported resolution**: Follow the import chain via `ModuleResolver`, then look up the symbol in the target module's export table
   - Handles aliases (`import x as y`), wildcard imports (`from x import *`), and member access (`Class.method`)

4. **`CodeGraphBuilder`** — Consumes all of the above to build three NetworkX DiGraphs:
   - **Call graph**: Which function/method calls which (via `CallExtractor`)
   - **Dependency graph**: Which file imports which (file-level edges)
   - **Inheritance graph**: Which class extends which (base class resolution)

**Important caveat**: This pipeline is **Python-only**. The tree-sitter S-expression queries in `ImportExtractor` are Python-specific, and `ModuleResolver` assumes Python's module/package system. Other languages parsed by tree-sitter get basic extraction but no cross-file resolution.

### Comparative Assessment

FastCode has **deeper Python-specific analysis** (libcst CST parsing, call extraction, symbol resolution, module resolution, inheritance graph) with genuine cross-file dependency tracking. fs2 has **broader language support** (40+ languages) but shallower per-file extraction — no call graphs, no cross-file symbol resolution, no relationship edges between nodes. FastCode builds call, dependency, and inheritance graphs via NetworkX; fs2 stores a flat node graph with containment hierarchy only (file → class → method).

---

## 4. Embedding & Search

### FastCode

- **Embedder**: `sentence-transformers` (local model, default `all-MiniLM-L6-v2`)
  - Local inference — no API calls needed
  - Auto-detects CUDA/MPS/CPU
  - 512 max sequence length
- **Pre-embedding enrichment**: **None (mechanical concatenation only)**
  - `_prepare_code_text()` concatenates metadata fields as string templates: `Type: function\nName: foo\nSignature: ...\nDocumentation: <docstring>\nCode: <raw source>`
  - No LLM involvement — the embedding input is raw code + structural metadata
  - The only LLM-generated summary is at the **repository level** (`RepositoryOverviewGenerator` — one summary per entire repo, derived from the README file)
  - Individual functions, classes, and methods have **no AI-generated descriptions**
- **Vector store**: FAISS (HNSW index for approximate search, or flat for exact)
  - Cosine similarity via inner product on normalized vectors
  - Persistent to disk with pickle
- **Search**: `HybridRetriever` combining:
  - **Semantic search** (FAISS vector similarity, weight: 0.6)
  - **Keyword search** (BM25Okapi, weight: 0.3)
  - **Graph traversal** (NetworkX relationship following, weight: 0.1)
  - Diversity penalty for result variety
  - Two-stage retrieval: repo selection → element retrieval
  - LLM-based or embedding-based repo selection
  - **Iterative agent** for multi-round refinement with confidence-based stopping

### fs2

- **Embedder**: Cloud API-based (Azure OpenAI or OpenAI-compatible endpoints)
  - `text-embedding-3-small` (1024 dimensions)
  - Async batch processing with rate limiting
  - Content-type aware chunking (400 tokens for code, 800 for docs)
- **Pre-embedding enrichment: Smart Content (LLM-generated per-node summaries)**
  - Every node in the graph (file, class, function, method) is sent through an LLM to generate a natural-language summary of what the code does, its purpose, relationships, and key behaviors
  - Summaries are stored on the `CodeNode.smart_content` field and used as an additional embedding target
  - Uses configurable prompt templates per node type (`TemplateService`)
  - Concurrent processing with configurable `max_workers` (up to 64 parallel LLM calls)
  - **This is a fundamental quality advantage**: semantic search in fs2 matches against LLM-understood intent and purpose, not just raw code tokens and docstrings
  - Example: A function named `_xfr` with no docstring gets a smart content summary like *"Transfers data between source and destination buffers, handling partial reads and backpressure"* — making it discoverable by intent
- **Vector store**: Embeddings stored directly on `CodeNode` objects in the NetworkX graph pickle
  - No separate vector index (FAISS/ChromaDB)
  - Cosine similarity computed at query time
- **Search**: `SearchService` with modal search:
  - **Text search**: Substring matching across content, node_id, smart_content
  - **Regex search**: Pattern matching with field-level match results
  - **Semantic search**: Cosine similarity on embeddings with chunk-level matching
  - **Auto mode**: Heuristic mode selection based on query pattern
  - No hybrid fusion, no BM25, no graph traversal in search

### Comparative Assessment

**Retrieval sophistication**: FastCode wins on retrieval pipeline — hybrid fusion search (semantic + keyword + graph), iterative multi-round retrieval with confidence-based stopping, and two-stage repo selection. fs2 has simpler single-mode search with separate matchers.

**Embedding quality**: fs2 wins decisively on what gets embedded — LLM-generated smart content summaries per node mean semantic search matches on **understood intent**, not just lexical similarity to raw code. FastCode embeds mechanical metadata concatenation with no AI enrichment below the repo level. This is arguably the more important factor for search quality, since even a simple cosine search over high-quality embeddings can outperform sophisticated retrieval over poor embeddings.

**Cost tradeoffs**: FastCode's local embedding model means zero API cost for embeddings; fs2 requires cloud API access for both smart content generation and embedding. However, fs2's enrichment is a one-time scan cost, while FastCode's iterative agent burns LLM tokens on every query.

---

## 5. LLM Integration

### FastCode

- **Providers**: OpenAI, Anthropic (direct SDK usage)
- **Uses**: Answer generation, query processing/rewriting, repo selection, iterative agent reasoning
- **Config**: Environment variables (.env), config dict
- **The LLM is core**: Without LLM access, FastCode can still index but cannot answer questions

### fs2

- **Providers**: Azure OpenAI, OpenAI (via adapters with ABC interfaces)
- **Uses**: Smart content generation (code summaries), embeddings
- **Config**: Pydantic-settings with env var interpolation, YAML files
- **The LLM is optional**: fs2 works fully without LLM (scan --no-smart-content --no-embeddings)

---

## 6. API Surfaces

### FastCode — 4 Separate Surfaces

| Surface | Tech | LOC | Features |
|---------|------|-----|----------|
| **CLI** (`main.py`) | Click | 946 | Interactive REPL, query, index, manage repos/sessions |
| **REST API** (`api.py`) | FastAPI | 800 | Full CRUD: load repos, query, sessions, streaming, upload zips |
| **Web App** (`web_app.py`) | FastAPI + HTML | 832 | Same as REST + web interface, HTML template |
| **MCP Server** (`mcp_server.py`) | FastMCP | 425 | code_qa, list_repos, session management |

Notable: `api.py` and `web_app.py` contain **substantial code duplication** (duplicate Pydantic models, duplicate endpoint logic).

### fs2 — 2 Clean Surfaces

| Surface | Tech | LOC | Features |
|---------|------|-----|----------|
| **CLI** | Typer + Rich | ~1500 | scan, tree, search, get-node, init, doctor, list-graphs |
| **MCP Server** | FastMCP | ~400 | tree, get_node, search, docs_list, docs_get, list_graphs |

Both surfaces are thin layers over shared services. No duplication.

---

## 7. Nanobot (FastCode Exclusive)

FastCode bundles **Nanobot**, a complete multi-channel AI agent framework (~6,700 LOC across 51 Python files):

- **Agent loop**: Tool-calling LLM loop with configurable max iterations
- **Channels**: Telegram, Discord, Slack, WhatsApp, DingTalk, Feishu, QQ, Email
- **Tools**: File system, shell exec, web search/fetch, message, spawn subagents, cron
- **FastCode integration**: Dedicated FastCode tools (load repo, query, list repos, status, sessions) communicating via HTTP
- **Provider abstraction**: LiteLLM-based provider with model registry
- **Session management**: Persistent sessions with history
- **Skills**: Pluggable skill definitions (markdown-based)
- **Cron**: Scheduled task execution

This is essentially a **ChatGPT-style agent runtime** that can be deployed across messaging platforms with FastCode as a backend tool.

---

## 8. Infrastructure & Deployment

| Dimension | FastCode | fs2 |
|-----------|----------|-----|
| **Packaging** | `requirements.txt` (no pyproject.toml for core) | `pyproject.toml` + `uv` |
| **Docker** | Yes — Dockerfile + docker-compose (FastCode + Nanobot) | Yes — Dockerfile + docker-compose |
| **Dependencies** | Heavy: torch, sentence-transformers, faiss, chromadb, numpy, pandas, redis | Light: pydantic, typer, rich, tiktoken, tree-sitter |
| **Install size** | ~2-3 GB (PyTorch, models) | ~50-100 MB |
| **Distribution** | Clone + pip install | `uv tool install` from GitHub, `uvx` zero-install |
| **Python** | 3.x (no pinned version) | 3.12 |

FastCode's dependency on PyTorch and sentence-transformers means **multi-GB install** and GPU-awareness. fs2's cloud-API approach means tiny footprint but requires API credentials.

---

## 9. Multi-Repository Support

### FastCode
- First-class multi-repo: load/unload repositories dynamically
- Two-stage retrieval: select relevant repos first, then search within them
- LLM-based or embedding-based repo selection
- Repository overview generation for repo-level summaries
- Session-aware: queries can filter by repo names

### fs2
- Multi-graph configuration: reference external `.fs2/graph.pickle` files
- Each graph is independently scanned and stored
- Query any graph by name via CLI `--graph-name` or MCP `graph_name` parameter
- No cross-graph search fusion — queries target one graph at a time

---

## 10. Strengths & Weaknesses

### FastCode Strengths
- **Deep retrieval**: Hybrid search with iterative refinement is genuinely sophisticated
- **End-to-end Q&A**: Full RAG pipeline from repo URL to natural language answer
- **Multi-channel agent**: Nanobot provides deployment to any messaging platform
- **Local embeddings**: No API cost for embedding generation
- **Call/dependency graphs**: Rich code relationship analysis (Python-specific) — call graph, dependency graph, inheritance graph via `ImportExtractor` → `ModuleResolver` → `SymbolResolver` → `CodeGraphBuilder`
- **Cross-file resolution**: Can trace `from .utils import helper` to the actual definition and build edges — fs2 cannot do this at all
- **Dynamic repo management**: Load/unload repos at runtime

### FastCode Weaknesses
- **Zero tests**: No test suite at all — high regression risk
- **God class**: `FastCode` main class (1436 LOC), `IterativeAgent` (3336 LOC) — monolithic
- **No interfaces**: Concrete coupling everywhere, untestable without full stack
- **Code duplication**: api.py and web_app.py duplicate models and logic
- **Heavy dependencies**: PyTorch + FAISS + ChromaDB = multi-GB install
- **Flat structure**: No layering or dependency rules — spaghetti risk
- **Config via .env**: No validation, no type safety, easy to misconfigure
- **No per-node AI enrichment**: Embeds raw code + metadata concatenation — no LLM-generated summaries below the repo level, hurting semantic search quality for poorly-documented code
- **Cross-file resolution is Python-only**: Tree-sitter queries and module resolution logic are hardcoded for Python's import system

### fs2 Strengths
- **Clean Architecture**: Strict layering with enforced dependency rules
- **Comprehensive testing**: 178 test files, ~58K LOC, 2.4:1 test-to-source ratio
- **ABC + Fakes**: Every interface testable in isolation without real infrastructure
- **Typed everything**: Pydantic models, frozen dataclasses, typed exceptions
- **Lightweight**: Small install footprint, fast startup
- **Documentation**: Extensive user/dev docs, self-service docs via MCP
- **Multi-graph**: Clean external graph configuration
- **Smart content (LLM per-node summaries)**: Every function, class, method gets an AI-generated natural-language description of its purpose and behavior — dramatically improves semantic search quality, especially for undocumented or cryptically-named code

### fs2 Weaknesses
- **No answer generation**: Deliberately leaves synthesis to the calling agent
- **No call graphs**: Doesn't extract call relationships or cross-file references — no dependency, call, or inheritance graphs at all
- **Simpler search**: No hybrid fusion, no BM25, no iterative refinement
- **Cloud embedding dependency**: Requires API credentials for semantic search (and smart content generation)
- **No dynamic repo loading**: Must re-scan to update; no runtime add/remove
- **Shallow per-language extraction**: Wide language support but less depth than FastCode's Python analysis — no cross-file symbol resolution for any language

---

## 11. Architectural Alignment & Overlap

Both systems share this core pipeline:

```
Source Code → Parsing (tree-sitter) → Node Extraction → Embedding → Storage → Search
```

The divergence is:
- **FastCode** continues the pipeline: → Retrieval → LLM Answer Generation → User
- **fs2** stops at search and hands off to external agents via MCP

### Shared Concepts, Different Implementations

| Concept | FastCode | fs2 |
|---------|----------|-----|
| Code node | `CodeElement` dataclass | `CodeNode` frozen dataclass |
| Parser | `CodeParser` (libcst + tree-sitter) | `TreeSitterParser` (tree-sitter only, behind ABC) |
| Graph storage | NetworkX DiGraph (call, dep, inheritance) | NetworkX Graph (node containment, via `GraphStore` ABC) |
| Embeddings | `sentence-transformers` local | Azure/OpenAI API via `EmbeddingAdapter` ABC |
| Vector search | FAISS HNSW index | Cosine similarity on in-graph numpy arrays |
| Smart content | N/A | LLM-generated code summaries stored on nodes |
| Config | YAML + .env dicts | Pydantic-settings + YAML with env interpolation |
| MCP server | FastMCP (code_qa, repos, sessions) | FastMCP (tree, search, get_node, docs) |

---

## 12. Recommendations

### If merging capabilities:
1. **Port FastCode's hybrid retrieval** (BM25 + semantic fusion + graph traversal) into fs2 as a `HybridSearchService` behind the existing service interface
2. **Port FastCode's call/dependency extraction** as optional pipeline stages in fs2
3. **Keep fs2's architecture** — the ABC/fake/DI patterns are vastly more maintainable
4. **Add tests to FastCode** or abandon it as a reference implementation and rebuild within fs2's architecture

### If keeping separate:
1. **FastCode needs tests urgently** — the zero-test state is a liability
2. **fs2 could benefit from** BM25 keyword search as an additional matcher in `SearchService`
3. **Nanobot** is independently valuable and could be split into its own package

---

*Report generated 2026-03-06 by fs2 multi-graph analysis, comparing `~/github/fastcode` (FastCode 2.0) against `~/substrate/fs2/028-server-mode` (fs2 v0.1.0).*
