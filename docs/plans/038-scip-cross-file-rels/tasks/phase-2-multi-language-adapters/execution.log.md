# Phase 2: Multi-Language Adapters — Execution Log

**Started**: 2026-03-17
**Baseline**: 39 SCIP tests passed (26 base + 13 python adapter)

---

## Task Log

### T000: Refactor SCIPAdapterBase ✅
- Refactored `symbol_to_node_id()` from abstract → concrete template method
- Added `_split_descriptor_segments()` — backtick-safe `/` splitting (fixes Go import paths)
- Extracted `_fuzzy_match_node_id()` as shared lookup logic
- Added `_extract_symbol_names()` virtual hook (default: universal parser)
- Added `LANGUAGE_ALIASES`, `normalise_language()`, `create_scip_adapter()` at module level
- Simplified `SCIPPythonAdapter` from ~68 lines → ~23 lines (just `language_name()`)
- Simplified `SCIPFakeAdapter` — removed redundant `symbol_to_node_id()` override
- Added 22 new tests: descriptor splitting, fuzzy match, language normalisation
- All 61 tests pass (39 existing + 22 new), lint clean

### T001: Generate fixture .scip files + deep inspection ✅
- Generated `scripts/scip/fixtures/typescript/index.scip` (10534 bytes, 3 docs)
- Generated `scripts/scip/fixtures/go/index.scip` (18646 bytes, 3 docs)
- Generated `scripts/scip/fixtures/dotnet/index.scip` (10860 bytes, 6 docs)
- **TS format confirmed**: `scip-typescript npm . . \`file.ts\`/Class#method().` — no slashes in backticks
- **Go format confirmed**: `scip-go gomod mod hash \`import/path\`/Type#Method().` — slashes IN backticks, fixed by T000
- **C# format confirmed**: `scip-dotnet nuget . . Namespace/Class#Method().` — no backticks at all
- **C# generated docs identified**: all 3 under `obj/Debug/net8.0/` (GlobalUsings.g.cs, AssemblyAttributes.cs, AssemblyInfo.cs)
- Cross-file edges verified in all 3 indexes via scip print + Python inspection

### T002: SCIPTypeScriptAdapter ✅
- Created `scip_adapter_typescript.py` — 28 lines (just `language_name()`, inherits template)
- Created `test_scip_adapter_typescript.py` — 8 unit tests + 6 integration tests
- All 14 tests pass including fixture integration (handler→service, service→model edges)

### T003: SCIPGoAdapter ✅
- Created `scip_adapter_go.py` — 30 lines (just `language_name()`, inherits template)
- Created `test_scip_adapter_go.py` — 9 unit tests + 6 integration tests
- All 15 tests pass including fixture integration (main→service, service→model edges)
- Go import paths with slashes in backticks handled correctly by T000's `_split_descriptor_segments()`

### T004: SCIPDotNetAdapter ✅
- Created `scip_adapter_dotnet.py` — 38 lines (language_name + should_skip_document with obj/ prefix filter)
- Created `test_scip_adapter_dotnet.py` — 7 unit tests + 4 doc filter tests + 7 integration tests
- All 18 tests pass including fixture integration (Program→Service, Service→Model edges)
- Generated files under `obj/` confirmed filtered — no spurious edges from them

### T005: Type alias normalisation + factory ✅
- `LANGUAGE_ALIASES` dict: supports 14 aliases/canonical names (ts, js, cs, csharp, py + 9 canonicals)
- `normalise_language()`: case-insensitive, raises ValueError for unknown
- `create_scip_adapter()`: factory with lazy imports, supports python/typescript/go/dotnet
- All tests in T000's test additions; factory verified via manual test

### T006: Integration tests ✅
- Integration tests embedded in each test file (TestSCIP*AdapterWithFixture classes)
- 6 integration tests per adapter × 4 adapters = 24 integration tests
- All verify: edge extraction, edge format, cross-file edges, no self-refs, deduplication
- C# additionally verifies generated docs don't produce edges

### Full Suite
- SCIP tests: 108/108 passed (61 base/python + 14 typescript + 15 go + 18 dotnet)
- Lint: all clean
