# Flight Plan: Implementation — Courtesy Saves

**Plan**: [courtesy-saves-plan.md](../../courtesy-saves-plan.md)
**Phase**: Single phase (Simple mode)
**Generated**: 2026-03-15
**Status**: Landed

---

## Departure → Destination

**Where we are**: The scan pipeline saves the graph **once** at the very end in StorageStage. A crash, kill, or laptop sleep during a 30-60 minute local LLM scan loses all progress. GraphStore.save() writes directly to graph.pickle — kill during write corrupts the file. First-time scans have zero recovery.

**Where we're going**: Graph is saved atomically (temp+rename) after every pipeline stage and every 10 nodes during SmartContent batch processing. A crash at node 500/900 loses at most ~10 nodes of work. Restart automatically resumes from the last courtesy save via hash-based skip. No user intervention needed.

---

## Flight Status

```mermaid
stateDiagram-v2
    classDef pending fill:#9E9E9E,stroke:#757575,color:#fff
    classDef active fill:#FFC107,stroke:#FFA000,color:#000
    classDef done fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef blocked fill:#F44336,stroke:#D32F2F,color:#fff

    state "1: Atomic save + context field" as S1
    state "2: Save helper + inter-stage" as S2
    state "3: Intra-stage courtesy saves" as S3
    state "4: Tests" as S4

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

- [x] **Stage 1: Foundation** — atomic save in GraphStore + courtesy_save field in PipelineContext (T01, T06)
- [x] **Stage 2: Pipeline saves** — extract save helper, add inter-stage saves after each stage (T02, T03)
- [x] **Stage 3: Intra-stage saves** — SmartContent saves every 10 nodes, Embedding saves every 50 nodes (T04, T05)
- [x] **Stage 4: Tests** — atomic save test + inter-stage save verification (T07)

---

## Architecture: Before & After

```mermaid
flowchart LR
    classDef existing fill:#E8F5E9,stroke:#4CAF50,color:#000
    classDef changed fill:#FFF3E0,stroke:#FF9800,color:#000
    classDef new fill:#E3F2FD,stroke:#2196F3,color:#000

    subgraph Before["Before"]
        B1["Discovery"]:::existing
        B2["Parsing"]:::existing
        B3["CrossFileRels"]:::existing
        B4["SmartContent"]:::existing
        B5["Embedding"]:::existing
        B6["StorageStage (SAVE)"]:::existing
        B1 --> B2 --> B3 --> B4 --> B5 --> B6
    end

    subgraph After["After"]
        A1["Discovery"]:::existing
        A2["Parsing"]:::existing
        A2S["💾 save"]:::new
        A3["CrossFileRels"]:::existing
        A3S["💾 save"]:::new
        A4["SmartContent (save/10)"]:::changed
        A4S["💾 save"]:::new
        A5["Embedding (save/50)"]:::changed
        A5S["💾 save"]:::new
        A6["StorageStage"]:::existing
        A1 --> A2 --> A2S --> A3 --> A3S --> A4 --> A4S --> A5 --> A5S --> A6
    end
```

---

## Acceptance Criteria

- [ ] AC01: Crash at node 50/900 → restart recovers ~40-50 nodes
- [ ] AC02: GraphStore.save() is atomic (temp+rename)
- [ ] AC03: Graph saved after Parsing, CrossFileRels, SmartContent, Embedding
- [ ] AC04: SmartContent saves every ~10 nodes (local)
- [ ] AC05: Embedding saves every ~50 nodes
- [ ] AC06: Overhead <10% of scan time
- [ ] AC07: Partial graph works with tree/search/MCP

## Goals & Non-Goals

**Goals**: Crash-resilient scans, atomic saves, automatic resume, <10% overhead
**Non-Goals**: WAL/journal, multi-process locking, backup versioning, resume UI

---

## Checklist

- [x] T01: Atomic save — temp file + rename
- [x] T02: Extract save helper from StorageStage logic
- [x] T03: Inter-stage saves in pipeline loop
- [x] T04: SmartContent intra-stage save every 10 nodes
- [x] T05: Embedding intra-stage save every 50 nodes
- [x] T06: PipelineContext courtesy_save callback field
- [x] T07: Tests — atomic save + inter-stage verification

---

## PlanPak

Not active for this plan.
