# Flight Plan: Phase 3 — Config + CLI + MCP Surface

**Plan**: [../../cross-file-rels-plan.md](../../cross-file-rels-plan.md)
**Phase**: Phase 3: Config + CLI + MCP Surface
**Generated**: 2026-03-13
**Status**: Landed

---

## Departure → Destination

**Where we are**: Phases 1–2 complete. The GraphStore ABC has `add_edge(**edge_data)` and `get_edges(node_id, direction, edge_type)`. CrossFileRelsStage resolves references via a Serena pool and stores edges in PipelineContext. StorageStage writes them to the graph. But the feature has NO user-facing surface — no config, no CLI flags, no relationship output in MCP tools. The stage hardcodes 20 instances, port 8330, and 10s timeout.

**Where we're going**: A user can configure cross-file rels via `.fs2/config.yaml` (enabled, instances, ports, timeout). `fs2 scan --no-cross-refs` skips resolution. An AI agent calling `get_node` sees `relationships: {referenced_by: [...], references: [...]}` showing who calls/imports/references that node. `tree --detail max` shows `(N refs)` per node for quick hotspot identification.

---

## Domain Context

### Domains We're Changing

| Domain | What Changes | Key Files |
|--------|-------------|-----------|
| config | New `CrossFileRelsConfig` pydantic model registered in `YAML_CONFIG_TYPES` | `src/fs2/config/objects.py` |
| cli | Two new scan flags; `.serena/` in init gitignore | `src/fs2/cli/scan.py`, `src/fs2/cli/init.py` |
| mcp | `get_node` returns relationships; tree shows ref count | `src/fs2/mcp/server.py` |

### Domains We Depend On (no changes)

| Domain | What We Consume | Contract |
|--------|----------------|----------|
| core/repos | `GraphStore.get_edges()` | ABC method from Phase 1 |
| core/models | `CodeNode` dataclass | Unchanged |
| core/services | `TreeService` / `TreeNode` | Unchanged |

---

## Flight Status

<!-- Updated by /plan-6-v2: pending → active → done. Use blocked for problems/input needed. -->

```mermaid
stateDiagram-v2
    classDef pending fill:#9E9E9E,stroke:#757575,color:#fff
    classDef active fill:#FFC107,stroke:#FFA000,color:#000
    classDef done fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef blocked fill:#F44336,stroke:#D32F2F,color:#fff

    state "1: Config model" as S1
    state "2: CLI flags" as S2
    state "3: MCP relationships" as S3
    state "4: Tree ref count" as S4
    state "5: Gitignore" as S5

    [*] --> S1
    S1 --> S2
    S2 --> S3
    S3 --> S4
    S4 --> S5
    S5 --> [*]

    class S1,S2,S3,S4,S5 done
```

**Legend**: grey = pending | yellow = active | red = blocked/needs input | green = done

---

## Stages

<!-- Updated by /plan-6-v2 during implementation: [ ] → [~] → [x] -->

- [x] **Stage 1: Config model** — Create `CrossFileRelsConfig` with validated fields and register in YAML_CONFIG_TYPES (`objects.py`)
- [x] **Stage 2: CLI flags** — Add `--no-cross-refs` and `--cross-refs-instances` flags to scan.py (`scan.py`)
- [x] **Stage 3: MCP relationships** — Update `_code_node_to_dict` and `get_node` to include relationships from graph edges (`server.py`)
- [x] **Stage 4: Tree ref count** — Add ref count to `_tree_node_to_dict` at max detail + render in text output (`server.py`, `tree.py`)
- [x] **Stage 5: Gitignore** — Add `.serena/` to init gitignore guidance (`init.py`)

---

## Architecture: Before & After

```mermaid
flowchart LR
    classDef existing fill:#E8F5E9,stroke:#4CAF50,color:#000
    classDef changed fill:#FFF3E0,stroke:#FF9800,color:#000
    classDef new fill:#E3F2FD,stroke:#2196F3,color:#000

    subgraph Before["Before Phase 3"]
        B_GS["GraphStore\nget_edges()"]:::existing
        B_MCP["MCP get_node\n(no relationships)"]:::existing
        B_TREE["MCP tree\n(no ref count)"]:::existing
        B_SCAN["CLI scan\n(no cross-ref flags)"]:::existing
        B_CFG["Config\n(no cross_file_rels)"]:::existing
    end

    subgraph After["After Phase 3"]
        A_GS["GraphStore\nget_edges()"]:::existing
        A_CFG["CrossFileRelsConfig\nenabled, instances, port"]:::new
        A_SCAN["CLI scan\n--no-cross-refs\n--cross-refs-instances"]:::changed
        A_MCP["MCP get_node\n+ relationships field"]:::changed
        A_TREE["MCP tree\n+ ref count"]:::changed
        A_INIT["CLI init\n+ .serena/ gitignore"]:::changed

        A_MCP --> A_GS
        A_TREE --> A_GS
        A_SCAN -.- A_CFG
    end
```

**Legend**: existing (green, unchanged) | changed (orange, modified) | new (blue, created)

---

## Acceptance Criteria

- [ ] [AC2] `get_node` returns `relationships.referenced_by` list when edges exist
- [ ] [AC3] `--no-cross-refs` flag is parsed without error
- [ ] [AC6] MCP `get_node` includes `relationships` in output (both min and max detail)
- [ ] [AC8] Config section `cross_file_rels` parsed from YAML
- [ ] [AC9] `--cross-refs-instances 5` flag is parsed without error
- [ ] [AC11] `tree --detail max` shows ref count per node

---

## Goals & Non-Goals

**Goals**:
- Config object with validation for cross-file rels settings
- CLI flags for opt-out and instance count override
- Relationship data in MCP get_node output
- Ref count in tree max detail output
- Gitignore guidance for .serena/ artifacts

**Non-Goals**:
- Wiring config/flags through ScanPipeline (Phase 4)
- End-to-end integration testing (Phase 4)
- Dedicated `get_edges` MCP tool (future)

---

## Checklist

- [x] T001: Create `CrossFileRelsConfig` pydantic model
- [x] T002: Add `--no-cross-refs` flag to scan.py
- [x] T003: Add `--cross-refs-instances` flag to scan.py
- [x] T004: Update `_code_node_to_dict` with `graph_store` param
- [x] T005: Update `get_node` to pass store to `_code_node_to_dict`
- [x] T006: Add ref count to tree `--detail max`
- [x] T007: Add `.serena/` to gitignore guidance
