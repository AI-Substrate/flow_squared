# Flight Plan: Phase 1 — GraphStore Edge Infrastructure

**Plan**: [cross-file-rels-plan.md](../../cross-file-rels-plan.md)
**Phase**: Phase 1: GraphStore Edge Infrastructure
**Generated**: 2026-03-13
**Status**: Landed

---

## Departure → Destination

**Where we are**: The fs2 graph stores nodes (CodeNode) with containment edges only (parent → child). Edges carry no attributes — `add_edge(parent_id, child_id)` is the only signature. There is no way to query edges by type or direction. TreeService trusts that all successors are containment children.

**Where we're going**: `add_edge()` accepts optional metadata (`**edge_data`), edges can carry `edge_type="references"` attributes, a new `get_edges(node_id, direction, edge_type)` method queries them, edge attributes survive save/load, and TreeService correctly ignores cross-file edges in tree output. Graph format is version 1.1.

---

## Domain Context

### Domains We're Changing

| Domain | What Changes | Key Files |
|--------|-------------|-----------|
| core/repos | GraphStore ABC gains `get_edges()`; `add_edge()` gains `**edge_data`; both impls updated | `graph_store.py`, `graph_store_impl.py`, `graph_store_fake.py` |
| core/services | TreeService filters cross-file edges from `get_children()` results | `tree_service.py` |

### Domains We Depend On (no changes)

| Domain | What We Consume | Contract |
|--------|----------------|----------|
| core/models | CodeNode (frozen dataclass, node_id format) | `CodeNode.node_id` = `{category}:{file_path}:{qualified_name}` |

---

## Flight Status

<!-- Updated by /plan-6-v2: pending → active → done. Use blocked for problems/input needed. -->

```mermaid
stateDiagram-v2
    classDef pending fill:#9E9E9E,stroke:#757575,color:#fff
    classDef active fill:#FFC107,stroke:#FFA000,color:#000
    classDef done fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef blocked fill:#F44336,stroke:#D32F2F,color:#fff

    state "1: ABC add_edge + get_edges" as S1
    state "2: NetworkX implementation" as S2
    state "3: Fake implementation" as S3
    state "4: Roundtrip + version" as S4
    state "5: TreeService + get_parent filter" as S5

    [*] --> S1
    S1 --> S2
    S1 --> S3
    S2 --> S4
    S3 --> S4
    S4 --> S5
    S5 --> [*]

    class S1,S2,S3,S4,S5 done
```

**Legend**: grey = pending | yellow = active | red = blocked/needs input | green = done

---

## Stages

<!-- Updated by /plan-6-v2 during implementation: [ ] → [~] → [x] -->

- [x] **Stage 1: ABC contract changes** — Add `**edge_data` to `add_edge()` and new `get_edges()` abstract method (`graph_store.py`)
- [x] **Stage 2: NetworkX implementation** — Implement `get_edges()` and pass `**edge_data` to networkx (`graph_store_impl.py`)
- [x] **Stage 3: Fake implementation** — Track edge data dict, implement `get_edges()` (`graph_store_fake.py`)
- [x] **Stage 4: Roundtrip + version** — Save/load test for edge attributes, bump FORMAT_VERSION to 1.1 (`graph_store_impl.py`)
- [ ] **Stage 5: TreeService + get_parent filter** — Filter `get_children()` results to same-file only; fix `get_parent()` to return containment parent only (`tree_service.py`, `graph_store_impl.py`, `graph_store_fake.py`)

---

## Architecture: Before & After

```mermaid
flowchart LR
    classDef existing fill:#E8F5E9,stroke:#4CAF50,color:#000
    classDef changed fill:#FFF3E0,stroke:#FF9800,color:#000
    classDef new fill:#E3F2FD,stroke:#2196F3,color:#000

    subgraph Before["Before Phase 1"]
        B_ABC["GraphStore ABC<br/>add_edge(parent, child)<br/>get_children()"]:::existing
        B_NX["NetworkXGraphStore<br/>nx.DiGraph edges = {}"]:::existing
        B_FK["FakeGraphStore<br/>_edges: dict→set"]:::existing
        B_TS["TreeService<br/>get_children() unfiltered"]:::existing
        B_ABC --> B_NX
        B_ABC --> B_FK
        B_TS --> B_ABC
    end

    subgraph After["After Phase 1"]
        A_ABC["GraphStore ABC<br/>add_edge(parent, child, **edge_data)<br/>get_edges(node_id, dir, type)<br/>get_children()"]:::changed
        A_NX["NetworkXGraphStore<br/>nx.DiGraph edges = {edge_type: ...}<br/>FORMAT_VERSION = 1.1"]:::changed
        A_FK["FakeGraphStore<br/>_edges: dict→dict→dict"]:::changed
        A_TS["TreeService<br/>get_children() → filter same-file"]:::changed
        A_ABC --> A_NX
        A_ABC --> A_FK
        A_TS --> A_ABC
    end
```

**Legend**: existing (green, unchanged) | changed (orange, modified) | new (blue, created)

---

## Acceptance Criteria

- [ ] [AC5] `get_edges()` returns edges filtered by `edge_type` and `direction`
- [ ] [AC10] Graph format version is 1.1; old 1.0 graphs load without error
- [ ] Existing tests pass unchanged (backward compatibility)
- [ ] Tree output unchanged when no cross-file edges present
- [ ] Edge attributes survive pickle save + RestrictedUnpickler load

## Goals & Non-Goals

**Goals**: Typed edge storage, edge query API, tree safety, format version bump
**Non-Goals**: No Serena integration, no config, no CLI, no MCP changes

---

## Checklist

- [x] T001: Modify `GraphStore.add_edge()` to accept `**edge_data`
- [x] T002: Add `GraphStore.get_edges()` abstract method
- [x] T003: Implement `get_edges()` in NetworkXGraphStore
- [x] T004: Update NetworkXGraphStore `add_edge()` to pass `**edge_data`
- [x] T005: Update FakeGraphStore — track edge data + implement `get_edges()`
- [x] T006: Add save/load roundtrip test for edge attributes
- [x] T007: Bump FORMAT_VERSION to "1.1"
- [x] T008: Fix TreeService to filter cross-file edges from `get_children()`
- [x] T009: Fix `get_parent()` in both implementations to filter cross-file edges
