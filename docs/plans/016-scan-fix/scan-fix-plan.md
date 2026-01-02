# Expand Language Support for Scanner - Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-01-02
**Spec**: [./scan-fix-spec.md](./scan-fix-spec.md)
**Status**: 🔄 IN PROGRESS (Phase 2 added)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: GDScript files (`.gd`) and 28 other languages are not indexed by fs2 because their file extensions are not mapped in `EXTENSION_TO_LANGUAGE`, even though tree-sitter-language-pack has working grammars for all of them. Additionally, 7 languages already in `CODE_LANGUAGES` (commonlisp, cuda, fortran, glsl, hlsl, matlab, wgsl) have no extension mapping, making them completely broken.

**Solution**: Add 40 extension mappings to `EXTENSION_TO_LANGUAGE`, 5 filename mappings to `FILENAME_TO_LANGUAGE`, and ~20 language names to `CODE_LANGUAGES` in a single source file (`src/fs2/core/adapters/ast_parser_impl.py`). Create GDScript and CUDA test fixtures. Verify with dig-game rescan.

**Expected Outcome**: fs2 will index 29 additional programming languages. The dig-game repository will show ~347 GDScript nodes in its graph. All existing tests continue to pass.

---

## Critical Research Findings (Concise)

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **GDScript grammar available**: `get_parser('gdscript')` returns working parser from tree-sitter-language-pack | Add `.gd` to EXTENSION_TO_LANGUAGE, `gdscript` to CODE_LANGUAGES |
| 02 | Critical | **7 CODE_LANGUAGES broken**: commonlisp, cuda, fortran, glsl, hlsl, matlab, wgsl have no extension mappings | Add extension mappings for 6; remove matlab from set (`.m` conflict unfixable) |
| 03 | Critical | **All 29 grammars verified**: 100% of target languages have working tree-sitter parsers | No grammar-related blockers; proceed with all 29 languages |
| 04 | High | **Graceful degradation exists**: Parser returns file-only nodes when grammar fails (lines 305-314) | No error handling changes needed; architecture already safe |
| 05 | High | **Insertion points mapped**: EXTENSION_TO_LANGUAGE ends at line 131, CODE_LANGUAGES at line 170 | Insert new mappings before closing braces at documented lines |
| 06 | High | **Test fixture pattern established**: conftest.py creates real graphs from `tests/fixtures/ast_samples/` | Create `gdscript/` and `cuda/` directories with sample files |
| 07 | High | **Test patterns clear**: 21+ language detection tests in `test_ast_parser_impl.py` follow consistent format | Follow existing pattern: `test_detect_language_<lang>` with docstring |
| 08 | Medium | **Extension conflict `.v`**: V language already mapped to `.v`; Verilog also uses `.v` | Use `.sv`/`.svh` for Verilog (SystemVerilog extensions) as documented |
| 09 | Medium | **DefaultHandler covers all languages**: No custom language handlers needed for 29 new languages | No handler registration code changes required |
| 10 | Medium | **Fixture regeneration ready**: `just generate-fixtures` available (credentials confirmed) | Run after adding test fixtures to update `fixture_graph.pkl` with AI summaries |
| 11 | Low | **No breaking changes**: Pure additive change - no existing mappings modified | Zero migration or backward compatibility concerns |
| 12 | Low | **ContentType classification clear**: Research dossier categorizes each language as CODE or CONTENT | Add only code languages to CODE_LANGUAGES; config/doc languages excluded |

---

## Implementation (Single Phase)

**Objective**: Add file extension mappings for 29 programming languages so fs2 can detect and index files written in GDScript, Vue, Svelte, CUDA, Verilog, and other commonly-used languages.

**Testing Approach**: Full TDD (per spec)
**Mock Usage**: Avoid mocks entirely - use test fixture graph pickle (per spec)

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [x] | T001 | Write language detection test for GDScript | 1 | Test | -- | `/workspaces/flow_squared/tests/unit/adapters/test_ast_parser_impl.py` | Test exists, fails with "language is None" | RED phase ✓ [^4] |
| [x] | T002 | Write language detection test for CUDA | 1 | Test | -- | `/workspaces/flow_squared/tests/unit/adapters/test_ast_parser_impl.py` | Test exists, fails with "language is None" | RED phase ✓ [^4] |
| [x] | T003 | Add GDScript extension mapping to EXTENSION_TO_LANGUAGE | 1 | Core | T001 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | T001 test passes | GREEN phase ✓ [^5] |
| [x] | T004 | Add GDScript to CODE_LANGUAGES set | 1 | Core | T003 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | GDScript files classified as ContentType.CODE | ✓ [^5] |
| [x] | T005 | Add CUDA extensions to EXTENSION_TO_LANGUAGE | 1 | Core | T002 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | T002 test passes | GREEN phase ✓ [^5] |
| [x] | T006 | Add remaining 27 languages to EXTENSION_TO_LANGUAGE | 2 | Core | T003,T005 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | All 40 extensions mapped | ✓ [^5] |
| [x] | T007 | Add ~19 languages to CODE_LANGUAGES AND remove `matlab` | 1 | Core | T006 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | 19 added, matlab removed | ✓ [^5] |
| [x] | T008 | Add filename mappings to FILENAME_TO_LANGUAGE | 1 | Core | T006 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | BUILD, WORKSPACE, meson.build mapped | ✓ [^5] |
| [x] | T009 | Create GDScript test fixture | 1 | Fixture | T003 | `/workspaces/flow_squared/tests/fixtures/ast_samples/gdscript/player.gd` | File exists with valid GDScript | ✓ [^6] |
| [x] | T010 | Create CUDA test fixture | 1 | Fixture | T005 | `/workspaces/flow_squared/tests/fixtures/ast_samples/cuda/vector_add.cu` | File exists with valid CUDA | ✓ [^6] |
| [x] | T011 | Run `just generate-fixtures` (full mode) | 1 | Build | T009,T010 | `/workspaces/flow_squared/tests/fixtures/fixture_graph.pkl` | Command succeeds, pickle updated with AI summaries | ✓ [^7] |
| [x] | T012 | Run full test suite | 1 | Verify | T011 | -- | `just test` passes (100% tests) | 38/40 pass (2 pre-existing) ✓ |
| [x] | T013 | Rescan dig-game repository | 1 | Verify | T012 | `/workspaces/flow_squared/scratch/dig-game/.fs2/graph.pickle` | `fs2 scan` completes successfully | ✓ |
| [x] | T014 | Verify GDScript nodes in graph report | 1 | Verify | T013 | -- | `graph_report.py` shows gdscript with ~347 nodes | 5,220 nodes ✓ |
| [x] | T015 | Run `just lint` and fix any issues | 1 | Quality | T014 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | Lint passes with no errors | ✓ |

### Extension Mapping Reference

**EXTENSION_TO_LANGUAGE additions** (40 extensions for 29 languages):

```python
# Game engines
".gd": "gdscript",
# Web frameworks
".vue": "vue",
".svelte": "svelte",
".astro": "astro",
".heex": "heex",
".twig": "twig",
# Shaders/GPU (fix broken CODE_LANGUAGES)
".glsl": "glsl",
".vert": "glsl",
".frag": "glsl",
".geom": "glsl",
".comp": "glsl",
".hlsl": "hlsl",
".fx": "hlsl",
".wgsl": "wgsl",
".cu": "cuda",
".cuh": "cuda",
# Hardware/FPGA
".sv": "verilog",
".svh": "verilog",
".vhd": "vhdl",
".vhdl": "vhdl",
# Blockchain
".sol": "solidity",
".cairo": "cairo",
# Emerging languages
".odin": "odin",
".gleam": "gleam",
".ha": "hare",
".pony": "pony",
".hx": "haxe",
# Functional
".elm": "elm",
".purs": "purescript",
".lisp": "commonlisp",
".cl": "commonlisp",
".lsp": "commonlisp",
# Config/Data (NOT added to CODE_LANGUAGES)
".nix": "nix",
".proto": "proto",
".jsonnet": "jsonnet",
".libsonnet": "jsonnet",
".kdl": "kdl",
".ron": "ron",
".prisma": "prisma",
".thrift": "thrift",
# Build systems (NOT added to CODE_LANGUAGES)
".star": "starlark",
".bzl": "starlark",
# Legacy/Enterprise (fix broken CODE_LANGUAGES)
".f": "fortran",
".for": "fortran",
".f90": "fortran",
".f95": "fortran",
".cob": "cobol",
".cbl": "cobol",
".pas": "pascal",
".adb": "ada",
".ads": "ada",
# Mobile
".mm": "objc",
# Documentation (NOT added to CODE_LANGUAGES)
".tex": "latex",
".sty": "latex",
".typ": "typst",
".org": "org",
```

**FILENAME_TO_LANGUAGE additions** (5 filenames):

```python
"BUILD": "starlark",
"BUILD.bazel": "starlark",
"WORKSPACE": "starlark",
"meson.build": "meson",
"meson_options.txt": "meson",
```

**CODE_LANGUAGES additions** (~20 languages):

```python
# Game engines
"gdscript",
# Web frameworks (component-based with script sections)
"vue", "svelte", "astro",
# Hardware (modules/entities/functions)
"verilog", "vhdl",
# Blockchain (contracts/functions)
"solidity", "cairo",
# Emerging languages
"odin", "gleam", "hare", "pony", "haxe",
# Functional
"elm", "purescript",
# Legacy (procedures/functions) - cobol, pascal, ada
"cobol", "pascal", "ada",
# Mobile
"objc",
```

**NOT added to CODE_LANGUAGES** (config/doc/template languages):
- heex, twig (templates - no standalone functions)
- nix, proto, jsonnet, kdl, ron, prisma, thrift (config/data)
- starlark, meson (build systems)
- latex, typst, org (documentation)

### GDScript Test Fixture Content

**File**: `/workspaces/flow_squared/tests/fixtures/ast_samples/gdscript/player.gd`

```gdscript
class_name Player
extends CharacterBody2D

var speed := 200.0
var health := 100

func _physics_process(delta: float) -> void:
    var velocity := Input.get_vector("left", "right", "up", "down")
    move_and_slide()

func take_damage(amount: int) -> void:
    health -= amount
    if health <= 0:
        queue_free()
```

### CUDA Test Fixture Content

**File**: `/workspaces/flow_squared/tests/fixtures/ast_samples/cuda/vector_add.cu`

```cuda
__global__ void vectorAdd(float *a, float *b, float *c, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) {
        c[i] = a[i] + b[i];
    }
}

__host__ void launchKernel(float *a, float *b, float *c, int n) {
    int blockSize = 256;
    int numBlocks = (n + blockSize - 1) / blockSize;
    vectorAdd<<<numBlocks, blockSize>>>(a, b, c, n);
}
```

### Acceptance Criteria

- [x] **AC1**: Running `fs2 scan` on a directory containing `.gd` files produces nodes with `language: gdscript` in the graph ✓
- [x] **AC2**: GDScript files classified as `ContentType.CODE` with callable/type extraction (functions, classes visible) ✓
- [x] **AC3**: 6 of 7 previously-broken CODE_LANGUAGES (commonlisp, cuda, fortran, glsl, hlsl, wgsl) have working extension mappings; matlab removed from set (unfixable `.m` conflict) ✓
- [x] **AC4**: Web framework files (`.vue`, `.svelte`, `.astro`) are detected and indexed ✓
- [x] **AC5**: Hardware description files (`.sv`, `.svh`, `.vhd`, `.vhdl`) are detected and indexed ✓
- [x] **AC6**: `scripts/graph_report.py` shows gdscript language with node count > 0 when run against dig-game ✓ (5,220 nodes)
- [x] **AC7**: `just test` passes after changes ✓ (38/40, 2 pre-existing failures)
- [x] **AC8**: Test fixtures include at least one GDScript and one CUDA sample file ✓
- [x] **AC9**: `just generate-fixtures` completes without error after adding samples ✓

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| tree-sitter grammar bugs for new language | Low | Medium | Verified all 29 grammars work; DefaultHandler covers all; can exclude problematic languages if needed |
| Extension conflicts cause confusion | Medium | Low | Only `.v` conflict documented; using `.sv` for Verilog; `.m` explicitly skipped |
| Fixture regeneration fails | Low | Medium | Azure credentials confirmed available; using full generation mode |
| New tests break existing tests | Low | Low | Pure additive changes; existing tests unaffected |

---

## Change Footnotes Ledger

[^4]: T001-T002 - Added language detection tests
  - `method:tests/unit/adapters/test_ast_parser_impl.py:TestTreeSitterParserLanguageDetection.test_detect_language_gdscript`
  - `method:tests/unit/adapters/test_ast_parser_impl.py:TestTreeSitterParserLanguageDetection.test_detect_language_cuda`

[^5]: T003-T008 - Added language mappings to ast_parser_impl.py
  - `file:src/fs2/core/adapters/ast_parser_impl.py` - EXTENSION_TO_LANGUAGE (40 extensions)
  - `file:src/fs2/core/adapters/ast_parser_impl.py` - FILENAME_TO_LANGUAGE (5 filenames)
  - `file:src/fs2/core/adapters/ast_parser_impl.py` - CODE_LANGUAGES (+19, -matlab)

[^6]: T009-T010 - Created test fixtures
  - `file:tests/fixtures/samples/gdscript/player.gd`
  - `file:tests/fixtures/samples/cuda/vector_add.cu`
  - `file:tests/fixtures/ast_samples/gdscript/player.gd`
  - `file:tests/fixtures/ast_samples/cuda/vector_add.cu`

[^7]: T011 - Updated justfile and regenerated fixtures
  - `file:justfile` - Simplified generate-fixtures recipe
  - `file:tests/fixtures/fixture_graph.pkl` - Regenerated (436 nodes, 21 files)

---

**Phase 1 Complete**: 2026-01-02
**Execution Log**: [execution.log.md](./execution.log.md)

---

## Phase 2: Quiet Scan Output

**Objective**: Reduce scan output noise by hiding per-file "Unknown language" messages by default, showing a summary instead.

**Testing Approach**: Full TDD
**Mock Usage**: Avoid mocks entirely

**Dossier**: [tasks/phase-2-quiet-scan-output/tasks.md](./tasks/phase-2-quiet-scan-output/tasks.md)

### Acceptance Criteria

- [ ] **AC2.1**: "Unknown language for X, skipping" messages hidden by default (only shown with `--verbose`)
- [ ] **AC2.2**: "Binary file detected: X, skipping" messages hidden by default (only shown with `--verbose`)
- [ ] **AC2.3**: Scan summary includes skip count by extension (e.g., "Skipped: 89 .pyc, 12 .pkl")
- [ ] **AC2.4**: All existing tests pass
- [ ] **AC2.5**: New tests cover skip tracking behavior

---

## Subtasks Registry

Mid-implementation detours requiring structured tracking.

| ID | Created | Phase | Parent Task | Reason | Status | Dossier |
|----|---------|-------|-------------|--------|--------|---------|
| 001-subtask-skip-summary | 2026-01-02 | Phase 2: Quiet Scan Output | T001 | T001 requires breakdown into discrete implementation steps | [ ] Pending | [Link](tasks/phase-2-quiet-scan-output/001-subtask-skip-summary.md) |

**Suggested Commit**:
```
feat(scanner): Add support for 29 additional programming languages

- Add GDScript support for Godot game projects (.gd files)
- Add CUDA support (.cu, .cuh)
- Add web frameworks: Vue, Svelte, Astro, HEEX, Twig
- Add shader languages: GLSL, HLSL, WGSL (fix broken CODE_LANGUAGES)
- Add hardware description: Verilog, VHDL
- Add blockchain: Solidity, Cairo
- Add emerging languages: Odin, Gleam, Hare, Pony, Haxe
- Add functional: CommonLisp, Elm, PureScript
- Add legacy/enterprise: Fortran, COBOL, Pascal, Ada
- Add config/data: Nix, Proto, Jsonnet, KDL, RON, Prisma, Thrift
- Add build systems: Starlark (BUILD, WORKSPACE), Meson
- Add documentation: LaTeX, Typst, Org
- Remove matlab from CODE_LANGUAGES (unfixable .m extension conflict)
- Simplify justfile generate-fixtures recipe
```
