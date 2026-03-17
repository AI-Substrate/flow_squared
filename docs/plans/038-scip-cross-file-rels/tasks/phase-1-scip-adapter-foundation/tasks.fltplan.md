# Flight Plan: Phase 1 — SCIP Adapter Foundation

**Plan**: [scip-cross-file-rels-plan.md](../../scip-cross-file-rels-plan.md)
**Phase**: Phase 1: SCIP Adapter Foundation
**Generated**: 2026-03-16
**Status**: Landed

---

## Departure → Destination

**Where we are**: fs2 has a working cross-file relationship system powered by Serena (LSP/Pyright) with parallel MCP server instances. There is no SCIP code anywhere in the codebase. Protobuf is not a dependency. The SCIP proto schema has been downloaded and tested externally (`scripts/scip/`), confirming that cross-file edges can be extracted from any SCIP index.

**Where we're going**: A developer can instantiate `SCIPPythonAdapter`, point it at an `index.scip` file and a set of known fs2 node_ids, and get back a deduplicated, filtered list of cross-file edge tuples `(source_id, target_id, {"edge_type": "references"})` — ready for graph storage, identical in format to current Serena edges. The adapter handles protobuf parsing, symbol mapping, and noise filtering. A `SCIPFakeAdapter` enables testing without real SCIP indexers.

---

## Domain Context

### Domains We're Changing

| Domain | What Changes | Key Files |
|--------|-------------|-----------|
| core/adapters | Add SCIPAdapterBase ABC, SCIPPythonAdapter, SCIPFakeAdapter, scip_pb2.py, exception hierarchy | `src/fs2/core/adapters/scip_adapter.py`, `scip_adapter_python.py`, `scip_adapter_fake.py`, `scip_pb2.py`, `exceptions.py` |
| config | Add protobuf dependency | `pyproject.toml` |

### Domains We Depend On (no changes)

| Domain | What We Consume | Contract |
|--------|----------------|----------|
| core/adapters | `AdapterError` base exception | `exceptions.py` |
| core/adapters | ABC adapter pattern (naming, structure) | `sample_adapter.py` |

---

## Flight Status

<!-- Updated by /plan-6-v2: pending → active → done. Use blocked for problems/input needed. -->

```mermaid
stateDiagram-v2
    classDef pending fill:#9E9E9E,stroke:#757575,color:#fff
    classDef active fill:#FFC107,stroke:#FFA000,color:#000
    classDef done fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef blocked fill:#F44336,stroke:#D32F2F,color:#fff

    state "1: Protobuf dep + bindings" as S1
    state "2: Exceptions + ABC" as S2
    state "3: Python adapter" as S3
    state "4: Fake + TDD tests" as S4

    [*] --> S1
    S1 --> S2
    S2 --> S3
    S3 --> S4
    S4 --> [*]

    class S1,S2,S3,S4 done
```

**Legend**: grey = pending | yellow = active | red = blocked/needs input | green = done

---

## Stages

<!-- Updated by /plan-6-v2 during implementation: [ ] → [~] → [x] -->

- [x] **Stage 1: Add protobuf dep + generate bindings** — Added `protobuf>=6.0` to pyproject.toml, generated and committed `scip_pb2.py` (`pyproject.toml`, `scip_pb2.py`)
- [x] **Stage 2: Exception hierarchy + SCIPAdapterBase ABC** — Added SCIP errors to exceptions.py, created base adapter with protobuf parsing + edge extraction + dedup + filtering (`exceptions.py`, `scip_adapter.py` — new file)
- [x] **Stage 3: Python adapter** — Implemented symbol-to-node-id mapping for Python (`scip_adapter_python.py` — new file)
- [x] **Stage 4: Fake adapter + full TDD suite** — Created SCIPFakeAdapter, wrote 39 tests for base + Python adapters (`scip_adapter_fake.py` — new file, `test_scip_adapter.py`, `test_scip_adapter_python.py` — new files)

---

## Architecture: Before & After

```mermaid
flowchart LR
    classDef existing fill:#E8F5E9,stroke:#4CAF50,color:#000
    classDef changed fill:#FFF3E0,stroke:#FF9800,color:#000
    classDef new fill:#E3F2FD,stroke:#2196F3,color:#000

    subgraph Before["Before Phase 1"]
        B1["AdapterError\nhierarchy"]:::existing
        B2["ABC pattern\n(sample, embedding)"]:::existing
        B3["CrossFileRelsStage\n(Serena only)"]:::existing
    end

    subgraph After["After Phase 1"]
        A1["AdapterError\nhierarchy"]:::changed
        A2["ABC pattern"]:::existing
        A3["CrossFileRelsStage\n(Serena only)"]:::existing
        A4["SCIPAdapterBase\nABC"]:::new
        A5["SCIPPythonAdapter"]:::new
        A6["SCIPFakeAdapter"]:::new
        A7["scip_pb2.py"]:::new

        A1 -->|"inherits"| A4
        A7 -->|"parses"| A4
        A4 -->|"extends"| A5
        A4 -->|"extends"| A6
    end
```

**Legend**: existing (green, unchanged) | changed (orange, modified) | new (blue, created)

---

## Acceptance Criteria

- [x] `from fs2.core.adapters.scip_pb2 import Index` imports cleanly
- [x] `SCIPAdapterError` inherits from `AdapterError`
- [x] `SCIPAdapterBase` is abstract — cannot be instantiated directly
- [x] `SCIPPythonAdapter.extract_cross_file_edges()` returns correct edges for `tests/fixtures/cross_file_sample/`
- [x] Edges use `{"edge_type": "references"}` format (no ref_kind — matches Serena)
- [x] Local symbols (`local N`) filtered out
- [x] Stdlib symbols filtered out (not in known_node_ids)
- [x] Self-references (same source and target) filtered out
- [x] Duplicate edges deduplicated
- [x] `SCIPFakeAdapter.set_edges()` returns injected edges
- [x] All tests pass: `uv run python -m pytest tests/unit/adapters/test_scip_adapter*.py`

## Goals & Non-Goals

**Goals**: Protobuf parsing, edge extraction, Python symbol mapping, fake adapter, full tests
**Non-Goals**: ref_kind classification (dropped), other languages (Phase 2), config/CLI (Phase 3), stage wiring (Phase 4)

---

## Checklist

- [x] T001: Add `protobuf>=6.0` to pyproject.toml
- [x] T002: Generate and commit `scip_pb2.py`
- [x] T003: Add SCIPAdapterError hierarchy to exceptions.py
- [x] T004: Create SCIPAdapterBase ABC
- [x] T005: ~~DROPPED~~ ref_kind inference
- [x] T006: Create SCIPPythonAdapter
- [x] T007: Create SCIPFakeAdapter
- [x] T008: TDD tests for base + Python adapters
