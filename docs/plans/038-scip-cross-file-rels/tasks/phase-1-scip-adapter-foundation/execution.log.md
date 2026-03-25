# Phase 1: SCIP Adapter Foundation — Execution Log

**Started**: 2026-03-17
**Baseline**: 1777 passed, 8 failed (pre-existing report_service failures), 25 skipped, 359 deselected

---

## Task Log

### T001: Add protobuf dependency ✅
- Added `protobuf>=6.0` to pyproject.toml (alphabetical order)
- `uv sync` resolved to protobuf 7.34.0
- Verified: `uv run python -c "import google.protobuf"` succeeds
- Note: `uv sync` also upgraded pytest-asyncio which caused pre-existing async tests to fail with "async def functions are not natively supported" — unrelated to our change

### T002: Generate scip_pb2.py ✅
- Downloaded scip.proto from sourcegraph/scip main branch
- Generated with `uv run python -m grpc_tools.protoc --python_out=src/fs2/core/adapters /tmp/scip.proto`
- Verified: `from fs2.core.adapters.scip_pb2 import Index, Document, Occurrence` imports cleanly

### T003: SCIP exception hierarchy ✅
- Added `SCIPAdapterError(AdapterError)`, `SCIPIndexError`, `SCIPMappingError` to exceptions.py
- Follows existing pattern: actionable docstrings with recovery steps

### T004: SCIPAdapterBase ABC ✅
- Created `src/fs2/core/adapters/scip_adapter.py` (~220 lines)
- Universal methods: `_load_index()`, `_extract_raw_edges()`, `_map_to_node_ids()`, `_deduplicate()`
- Abstract methods: `language_name()`, `symbol_to_node_id()`
- Static utilities: `parse_symbol()`, `extract_name_from_descriptor()`
- Edge format: `{"edge_type": "references"}` (matches Serena)

### T005: DROPPED ✅
- ref_kind inference dropped per DYK-038-01

### T006: SCIPPythonAdapter ✅
- Created `src/fs2/core/adapters/scip_adapter_python.py` (~65 lines)
- `symbol_to_node_id()` parses SCIP descriptors and tries callable/class/type categories
- Falls back to file-level node when symbol name doesn't match
- Tested against real `tests/fixtures/cross_file_sample/index.scip`

### T007: SCIPFakeAdapter ✅
- Created `src/fs2/core/adapters/scip_adapter_fake.py` (~85 lines)
- `set_edges()` for direct injection, `set_index()` for protobuf parsing
- Tracks `call_history` for test assertions

### T008: TDD tests ✅
- 39 tests total, all passing
- `test_scip_adapter.py`: 26 tests (exceptions, ABC compliance, protobuf loading, edge extraction, dedup, symbol parsing, fake adapter, edge format)
- `test_scip_adapter_python.py`: 13 tests (symbol mapping, fixture integration: handler→service, service→model, no self-refs, dedup)

### Full Suite
- SCIP tests: 39/39 passed
- Full suite: 1777 passed (same as baseline), 8 pre-existing report_service failures
- Note: `uv sync` introduced pytest-asyncio regression (async tests fail), pre-existing and unrelated