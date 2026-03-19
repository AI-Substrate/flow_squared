# Flight Plan: Phase 3 — Config & Discovery CLI

**Plan**: [scip-cross-file-rels-plan.md](../../scip-cross-file-rels-plan.md)
**Phase**: Phase 3: Config & Discovery CLI
**Generated**: 2026-03-18
**Updated**: 2026-03-19 (DYK: Serena removal, entries rename, ruamel.yaml)
**Status**: Ready for takeoff

---

## Departure → Destination

**Where we are**: Phases 1-2 delivered SCIP adapter infrastructure with 4 language adapters, a factory, and type alias normalisation. But there's no way for users to declare which projects to index, and `detect_project_roots()` is buried inside `cross_file_rels_stage.py` with Serena-era dedup logic.

**Where we're going**: A user can run `fs2 discover-projects` to see all language projects (numbered list), then `fs2 add-project 1 2 3` to write them to config with comment-preserving YAML. Serena-specific fields removed from `CrossFileRelsConfig`. SCIP is the only provider.

---

## Domain Context

### Domains We're Changing

| Domain | What Changes | Key Files |
|--------|-------------|-----------|
| config | Add `ProjectConfig`, `ProjectsConfig` models; strip Serena fields from `CrossFileRelsConfig`; register in `YAML_CONFIG_TYPES` | `config/objects.py`, `pyproject.toml` |
| core/services | Extract `detect_project_roots()` to shared module; remove child dedup; extend markers | `services/project_discovery.py` (new), `stages/cross_file_rels_stage.py` (modify) |
| cli | Add `discover-projects` and `add-project` commands; register in main.py | `cli/projects.py` (new), `cli/main.py` (modify) |

### Domains We Depend On (no changes)

| Domain | What We Consume | Contract |
|--------|----------------|----------|
| core/adapters | `LANGUAGE_ALIASES` canonical names (for type set) | Module-level dict |

---

## Flight Status

```mermaid
stateDiagram-v2
    classDef pending fill:#9E9E9E,stroke:#757575,color:#fff
    classDef active fill:#FFC107,stroke:#FFA000,color:#000
    classDef done fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef blocked fill:#F44336,stroke:#D32F2F,color:#fff

    state "0: ruamel.yaml dep" as S0
    state "1: Config models" as S1
    state "2: Serena cleanup" as S2
    state "3: Register config" as S3
    state "4: Extract discovery" as S4
    state "5: discover-projects CLI" as S5
    state "6: add-project CLI" as S6
    state "7: Register commands" as S7
    state "8: Tests" as S8

    [*] --> S0
    S0 --> S1
    S1 --> S2
    S2 --> S3
    S3 --> S4
    S4 --> S5
    S5 --> S6
    S6 --> S7
    S7 --> S8
    S8 --> [*]

    class S0,S1,S2,S3,S4,S5,S6,S7,S8 pending
```

**Legend**: grey = pending | yellow = active | red = blocked/needs input | green = done

---

## Stages

- [ ] **Stage 0: Add ruamel.yaml dependency** — `pyproject.toml` modification, `uv sync`
- [ ] **Stage 1: Config models** — `ProjectConfig` + `ProjectsConfig` with `entries` field (not `projects`) and type alias validation (`config/objects.py` — modify)
- [ ] **Stage 2: Serena cleanup** — Remove `parallel_instances`, `serena_base_port`, `timeout_per_node`, `languages` from `CrossFileRelsConfig`; clean ALL Serena references across 14 source files + tests (`config/objects.py`, `paths.py`, `cli/init.py`, `cli/scan.py`, `cli/watch.py`, `pipeline_context.py`, `cross_file_rels_stage.py`, docs, tests — full codebase)
- [ ] **Stage 3: Register config** — Add `ProjectsConfig` to `YAML_CONFIG_TYPES` (`config/objects.py` — modify)
- [ ] **Stage 4: Extract discovery** — Move `detect_project_roots()`, `PROJECT_MARKERS`, `_SKIP_DIRS`, `ProjectRoot` to `project_discovery.py`; remove child dedup; extend markers; update stage import (`services/project_discovery.py` — new, `stages/cross_file_rels_stage.py` — modify)
- [ ] **Stage 5: discover-projects CLI** — Rich table showing type, path, project file, indexer status (`cli/projects.py` — new)
- [ ] **Stage 6: add-project CLI** — Comment-preserving YAML write via `ruamel.yaml` (`cli/projects.py` — modify)
- [ ] **Stage 7: Register commands** — Add to `main.py` without `require_init` guard (`cli/main.py` — modify)
- [ ] **Stage 8: Tests** — Config validation, discovery, CLI output (`tests/unit/` — new files)

---

## Architecture: Before & After

```mermaid
flowchart LR
    classDef existing fill:#E8F5E9,stroke:#4CAF50,color:#000
    classDef changed fill:#FFF3E0,stroke:#FF9800,color:#000
    classDef new fill:#E3F2FD,stroke:#2196F3,color:#000

    subgraph Before["Before Phase 3"]
        B_CFR["CrossFileRelsConfig\n(4 Serena fields)"]:::existing
        B_DPR["detect_project_roots()\n(buried in stage, dedup)"]:::existing
        B_CLI["CLI: scan, tree..."]:::existing
    end

    subgraph After["After Phase 3"]
        A_PC["ProjectConfig\nProjectsConfig (entries)"]:::new
        A_CFR["CrossFileRelsConfig\n(enabled only)"]:::changed
        A_PD["project_discovery.py\n(shared, no dedup)"]:::new
        A_STAGE["cross_file_rels_stage.py\n(imports shared)"]:::changed
        A_CLI["CLI: + discover-projects\n+ add-project"]:::new
        A_MAIN["main.py\n(registers new cmds)"]:::changed
    end
```

---

## Acceptance Criteria

- [ ] AC6: `fs2 discover-projects` lists detected projects with type, path, project file, indexer status
- [ ] AC7: `fs2 add-project 1 2 3` writes selected projects to `.fs2/config.yaml`
- [ ] AC8: `projects` config accepts entries with type, path, project_file, enabled, options
- [ ] AC13: Type aliases (ts, cs, js, csharp) normalised in project type validator

_AC9 (auto_discover wiring into scan) moved to Phase 4 — Phase 3 builds config model, Phase 4 wires it._
_AC10 (provider: serena) dropped — Serena removed entirely._

---

## Checklist

- [ ] T000: Add `ruamel.yaml` to pyproject.toml
- [ ] T001: Add `ProjectConfig` and `ProjectsConfig` to config/objects.py
- [ ] T002: Remove Serena-specific fields from `CrossFileRelsConfig`
- [ ] T003: Register `ProjectsConfig` in `YAML_CONFIG_TYPES`
- [ ] T004: Extract `detect_project_roots()` to shared module
- [ ] T005: Create `fs2 discover-projects` CLI command
- [ ] T006: Create `fs2 add-project` CLI command (ruamel.yaml)
- [ ] T007: Register commands in main.py
- [ ] T008: Tests
