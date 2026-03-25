# Workshop: Tree-Sitter Comment & Decorator Extraction by Language

**Type**: Integration Pattern
**Plan**: 037-leading-context-capture
**Spec**: (not yet created)
**Created**: 2026-03-16
**Status**: Draft

**Related Documents**:
- [001-leading-context-design.md](001-leading-context-design.md) — Data model & search integration design
- `src/fs2/core/adapters/ast_parser_impl.py` — Current tree-sitter traversal
- `tests/fixtures/samples/` — Multi-language test corpus

---

## Purpose

Validate exactly how tree-sitter represents comments and decorators across all supported languages, using our **real test fixture files** as ground truth. Determine the extraction strategy per language, identify parent-wrapper edge cases, and catalog fixture gaps that must be fixed before implementation.

## Key Questions Addressed

- Q1: What tree-sitter node types represent comments in each language?
- Q2: Which languages have parent-wrapper edge cases (decorators, `export`)?
- Q3: Do our test fixtures have adequate comment/decorator samples for validation?
- Q4: What's the unified extraction algorithm across all languages?

---

## Methodology

Parsed every file in `tests/fixtures/samples/` with its language's tree-sitter grammar. For each function/class definition, walked `prev_named_sibling` backwards to find comment and decorator siblings. Also checked `node.parent.type` for wrapper patterns (Python `decorated_definition`, TypeScript `export_statement`).

---

## Results: Node Type Mapping

### Definitive Table

| Language | Comment Node Types | Decorator/Attribute Types | Parent Wrapper? |
|----------|-------------------|--------------------------|-----------------|
| **Python** | `comment` | `decorator` (child of `decorated_definition`) | ⚠️ YES |
| **Go** | `comment` | — | No |
| **Rust** | `line_comment` | `attribute_item` | No |
| **Java** | `block_comment`, `line_comment` | (inside declaration — automatic) | No |
| **TypeScript** | `comment` | (inside declaration) | ⚠️ YES |
| **TSX** | `comment` | (inside declaration) | ⚠️ YES |
| **JavaScript** | `comment` | — | Possible with `export` |
| **C** | `comment` | — | No |
| **C++** | `comment` | — | No |
| **Bash** | `comment` | — | No |
| **CUDA** | `comment` | — | No |
| **Ruby** | `comment` | — | Unknown |
| **GDScript** | `comment` | — | Unknown |

---

## Per-Language Findings (from real fixtures)

### Python ✅ — 2 wrapper edge cases

**Fixture**: `auth_handler.py` (21 definitions, 3 with context), `data_parser.py` (22 definitions, 5 with context)

**Observed behavior**:
```
module
  ├─ decorated_definition            ← this is what prev_named_sibling sees
  │   ├─ decorator "@dataclass"      ← child, NOT sibling
  │   └─ class_definition            ← the node we're creating
```

**Real example** — `auth_handler.py` L22:
```
L22 class_definition: class AuthToken:
    ⚠️  wrapper: decorated_definition
    📦 parent decorator: @dataclass
```

**Strategy**: When `node.parent.type == "decorated_definition"`, collect decorators from parent's children, then walk `prev_named_sibling` from the parent to find comments.

**Coverage assessment**: ✅ Good — has `@dataclass`, `@property`, `@abstractmethod`. Missing: `#` comments directly above decorated functions (most have docstrings inside, not comments above).

---

### Go ✅ — Simplest case

**Fixture**: `server.go` (18 definitions, ALL 18 have context)

**Observed behavior**: Comments are clean siblings. No wrappers.
```
source_file
  ├─ comment "// DefaultConfig returns..."    ← direct sibling
  └─ function_declaration
```

**Real example** — `server.go` L29:
```
L29 function_declaration: func DefaultConfig() *Config {
    ↑ comment: // DefaultConfig returns sensible default configuration.
```

**Strategy**: Walk `prev_named_sibling`, collect `comment` nodes.

**Coverage assessment**: ✅ Excellent — every function and type has `//` comments above.

---

### Rust ✅ — Different node types

**Fixture**: `lib.rs` (27 definitions, 16 with context)

**Observed behavior**: Uses `line_comment` (not `comment`) and `attribute_item` (not `decorator`). Both are direct siblings.
```
source_file
  ├─ line_comment "/// Calculate tax..."        ← sibling
  ├─ attribute_item "#[derive(Debug)]"          ← sibling
  └─ function_item
```

**Real example** — `lib.rs` L13:
```
L13 enum_item: pub enum EvictionPolicy {
    ↑ line_comment: /// Eviction policy for the cache.
    ↑ attribute_item: #[derive(Debug, Clone, Copy, PartialEq)]
```

**Strategy**: Walk `prev_named_sibling`, collect `line_comment` and `attribute_item` nodes.

**Coverage assessment**: ✅ Excellent — has `///` doc comments, `//` regular comments, and `#[derive()]` attributes.

---

### Java ✅ — Javadoc is sibling, annotations are in-node

**Fixture**: `UserService.java` (24 definitions, 11 with context)

**Observed behavior**: `/** Javadoc */` appears as `block_comment` sibling. Java annotations (`@Override`, `@Service`) are part of the declaration node's modifier list — already in `content`.
```
program
  ├─ block_comment "/** Calculates tax... */"    ← sibling we need to capture
  └─ class_declaration "@Service public class"   ← annotations already inside
```

**Real example** — `UserService.java` L18:
```
L18 class_declaration: public class UserService {
    ↑ block_comment: /** Service class for user management...
```

**Strategy**: Walk `prev_named_sibling`, collect `block_comment` and `line_comment`. No special handling for annotations (they're automatic).

**Coverage assessment**: ✅ Excellent — has multi-line Javadoc with `@param`/`@return`, class-level docs.

---

### TypeScript ⚠️ — Export statement wrapper

**Fixture**: `app.ts` (16 definitions, 14 with context)

**Observed behavior**: `export function foo()` wraps the function inside an `export_statement`. Comments are siblings of the export wrapper, not the function.
```
program
  ├─ comment "/** Merge partial config... */"     ← sibling of export_statement
  └─ export_statement                              ← NOT the function itself
      └─ function_declaration                      ← this is what we create
```

**Real example** — `app.ts` L60:
```
L60 function_declaration: function mergeConfig(...)
    ⚠️  wrapper: export_statement
    ↑ comment: /** Merge partial configuration with defaults...
```

**Strategy**: When `node.parent.type == "export_statement"`, walk from parent's siblings.

**Coverage assessment**: ✅ Good — has both exported and non-exported functions, JSDoc blocks.

---

### TSX ⚠️ — Same as TypeScript

**Fixture**: `component.tsx` (25 definitions, 7 with context)

**Same `export_statement` wrapper issue** as TypeScript.

**Real example** — `component.tsx` L85:
```
L85 function_declaration: function useTheme(): ThemeContextValue {
    ⚠️  wrapper: export_statement
    ↑ comment: /** Hook to access theme context...
```

**Coverage assessment**: ✅ Good — has section separator comments (`// ====`), JSDoc, and exported hooks/components.

---

### JavaScript ✅ — Clean (no export wrapper in fixture)

**Fixture**: `utils.js` (21 definitions, 7 with context)

**Observed behavior**: JSDoc blocks are single `comment` nodes (both `//` and `/** */` use same type).

**Real example** — `utils.js` L33:
```
L33 function_declaration: function throttle(fn, limit) {
    ↑ comment: /** Throttle function execution...
```

**Strategy**: Walk `prev_named_sibling`, collect `comment` nodes. Check for `export_statement` parent as safety.

**Coverage assessment**: ✅ Good — has JSDoc with `@param`/`@returns`, module-level `@module` comment.

---

### C ✅ — Clean, Doxygen-rich

**Fixture**: `algorithm.c` (8 definitions, ALL 8 have context)

**Real example** — `algorithm.c` L69:
```
L69 function_definition: SearchResult binary_search(
    ↑ comment: /** @brief Binary search in a sorted array...
```

**Coverage assessment**: ✅ Excellent — every function has Doxygen `/** @brief ... @param ... @return */`.

---

### C++ ✅ — Clean, but sparse

**Fixture**: `main.cpp` (17 definitions, 2 with context)

**Real example** — `main.cpp` L42:
```
L42 function_definition: void stopPropagation() { ... }
    ↑ comment: /** @brief Stop the event from propagating...
```

**Coverage assessment**: ⚠️ Sparse — only 2/17 definitions have comments. Most class methods lack leading comments. Usable but not comprehensive.

---

### Bash ✅ — Section headers captured

**Fixture**: `deploy.sh` (11 definitions, 8 with context)

**Real example** — `deploy.sh` L65:
```
L65 function_definition: validate_environment() {
    ↑ comment: # ==============================================================================
    ↑ comment: # Utility Functions
    ↑ comment: # ==============================================================================
    ↑ comment: # Validate the deployment environment
```

**Note**: Section separator comments (`# ====`) get captured as leading context. The **blank line gap rule** from Workshop 001 would correctly stop them from bleeding into unrelated functions — but in this fixture the section headers are directly above with no gap.

**Coverage assessment**: ✅ Good — has function-level and section-level comments.

---

### GDScript ⚠️ FIXTURE GAP

**Fixture**: `player.gd` (2 definitions, 0 with context)

**No comments at all.** Cannot validate extraction.

**Action required**: Add `##` doc-comments above functions and class declaration:
```gdscript
## Player character controller.
## Handles movement, health, and damage.
class_name Player
extends CharacterBody2D

## Process physics movement each frame.
## Uses input vector for 4-directional movement.
func _physics_process(delta: float) -> void:
    ...

## Apply damage to the player.
## @param amount - Damage points to subtract.
func take_damage(amount: int) -> void:
    ...
```

---

### CUDA ⚠️ FIXTURE GAP

**Fixture**: `vector_add.cu` (2 definitions, 0 with context)

**No comments at all.** Cannot validate extraction.

**Action required**: Add Doxygen-style comments above kernel and host functions:
```c
/**
 * @brief Add two vectors element-wise on the GPU.
 * @param a First input vector
 * @param b Second input vector
 * @param c Output vector
 * @param n Number of elements
 */
__global__ void vectorAdd(float *a, float *b, float *c, int n) { ... }

/**
 * @brief Launch vectorAdd kernel from host code.
 * Uses 256 threads per block.
 */
__host__ void launchKernel(float *a, float *b, float *c, int n) { ... }
```

---

### Ruby ⚠️ FIXTURE GAP

**Fixture**: `tasks.rb` (0 definitions detected)

Tree-sitter Ruby grammar did not produce any `function_definition` or `method_definition` nodes at the top level. The file likely uses Rake `task` blocks which aren't function definitions. **Cannot validate extraction.**

**Action required**: Either add a Ruby fixture with actual `def` methods and `class` definitions with `#` comments, or verify that `tasks.rb` uses node types our parser doesn't currently match.

---

## Unified Extraction Constants

Based on the probe results, here are the exact type sets for the extraction algorithm:

```python
# All comment types across supported languages
COMMENT_NODE_TYPES = frozenset({
    "comment",          # Python, Go, JS, TS, TSX, C, C++, Bash, GDScript, CUDA
    "line_comment",     # Rust (/// and //)
    "block_comment",    # Java (/** */)
})

# Decorator/attribute types that appear as SIBLINGS
SIBLING_DECORATOR_TYPES = frozenset({
    "attribute_item",   # Rust #[derive(...)], #[cfg(...)]
})

# Decorator types that appear as CHILDREN of wrapper parent
CHILD_DECORATOR_TYPES = frozenset({
    "decorator",        # Python @dataclass, @property
})

# Parent node types that wrap the definition
WRAPPER_PARENT_TYPES = frozenset({
    "decorated_definition",  # Python: wraps function + decorators
    "export_statement",      # TypeScript/TSX/JS: wraps with export
})

# Combined set for sibling walking
LEADING_CONTEXT_TYPES = COMMENT_NODE_TYPES | SIBLING_DECORATOR_TYPES
```

---

## Fixture Coverage Summary

| Language | File | Definitions | With Context | Gap? |
|----------|------|:-----------:|:------------:|:----:|
| Python | auth_handler.py | 21 | 3 (decorators) | Need `#` comments above |
| Python | data_parser.py | 22 | 5 (decorators) | Need `#` comments above |
| Go | server.go | 18 | **18** (100%) | ✅ Perfect |
| Rust | lib.rs | 27 | 16 | ✅ Good |
| Java | UserService.java | 24 | 11 | ✅ Good |
| TypeScript | app.ts | 16 | 14 | ✅ Good |
| TSX | component.tsx | 25 | 7 | ✅ OK |
| JavaScript | utils.js | 21 | 7 | ✅ OK |
| C | algorithm.c | 8 | **8** (100%) | ✅ Perfect |
| C++ | main.cpp | 17 | 2 | ⚠️ Sparse |
| Bash | deploy.sh | 11 | 8 | ✅ Good |
| GDScript | player.gd | 2 | **0** | ❌ **Must fix** |
| CUDA | vector_add.cu | 2 | **0** | ❌ **Must fix** |
| Ruby | tasks.rb | 0 | **0** | ❌ **Must fix** |

### Pre-Implementation Fixes Required

1. **`gdscript/player.gd`** — Add `##` doc comments above all functions
2. **`cuda/vector_add.cu`** — Add Doxygen `/** */` comments above kernel + host functions
3. **`ruby/tasks.rb`** — Replace or supplement with a file containing `def`/`class` with `#` comments
4. **`python/auth_handler.py`** — Add `#` comments above at least 2 non-decorated functions (currently only decorated functions have leading context; need plain comment → function cases too)

---

## Open Questions

### Q1: Should section separator comments be captured?

**Example** (from `deploy.sh`):
```bash
# ==============================================================================
# Utility Functions
# ==============================================================================
# Validate the deployment environment
validate_environment() {
```

All four comment lines get captured. The separators (`# ====`) add noise.

**OPEN**: Options:
- **A**: Capture everything — user searches for "Utility Functions" and finds it ✅
- **B**: Filter out lines matching `^[#/\*\s]*[=\-\*]{10,}` — cleaner but lossy
- **C**: Let it be — smart_content LLM will ignore separator lines anyway

**Leaning toward A** — capture everything, let search and LLM sort it out.

### Q2: Should Python `expression_statement` (module docstrings above classes) be captured?

```python
"""This module handles authentication."""   ← expression_statement (sibling)

class AuthHandler:                           ← class_definition
```

The module docstring is an `expression_statement` node that's a sibling of the class. Walking backwards from the class would capture it. But it belongs to the *module*, not the class.

**PROPOSED**: Skip `expression_statement` — it's captured in the file-level node's `content` already. Only capture `comment` and `decorator` types.

### Q3: How does the blank line gap rule interact with section headers?

If section headers have blank lines around them:
```python
# Section: Auth

# Handle login
def login():
```

The gap between "Section: Auth" and "Handle login" would stop the walker. Only "Handle login" would be captured. This is correct behavior.

But without a gap:
```python
# Section: Auth
# Handle login
def login():
```

Both lines get captured. Arguably wrong but harmless — the section header adds context.

**PROPOSED**: Accept current behavior. Blank line gap rule handles the common case correctly. Edge cases are harmless.
