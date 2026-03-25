# SCIP Cross-File Relationships — Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2026-03-16
**Spec**: [scip-cross-file-rels-spec.md](scip-cross-file-rels-spec.md)
**Status**: APPROVED

## Summary

The current cross-file relationship system uses Serena (LSP/Pyright) running as a pool of 15+ parallel MCP server instances — operationally complex, memory-heavy (~6GB for 20 instances), and limited to 2-3 languages. This plan replaces Serena with SCIP (Source Code Intelligence Protocol) indexers that run offline, produce a universal protobuf index, and support 10+ languages with a single adapter architecture. The plan adds project discovery CLI, per-language config, and a clean migration path from Serena.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| core/adapters | existing | **modify** | Add SCIPAdapterBase ABC + per-language implementations + fake |
| core/services/stages | existing | **modify** | Update CrossFileRelsStage for SCIP provider |
| core/models | existing | **consume** | CodeNode, PipelineContext unchanged |
| config | existing | **modify** | Add ProjectConfig, ProjectsConfig; extend CrossFileRelsConfig |
| cli | existing | **modify** | Add discover-projects, add-project commands |
| core/repos | existing | **consume** | GraphStore edge storage unchanged |
| mcp | existing | **consume** | MCP get_node relationships output unchanged |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/core/adapters/scip_adapter.py` | core/adapters | contract | SCIPAdapterBase ABC |
| `src/fs2/core/adapters/scip_adapter_python.py` | core/adapters | internal | Python SCIP adapter |
| `src/fs2/core/adapters/scip_adapter_typescript.py` | core/adapters | internal | TypeScript SCIP adapter |
| `src/fs2/core/adapters/scip_adapter_go.py` | core/adapters | internal | Go SCIP adapter |
| `src/fs2/core/adapters/scip_adapter_dotnet.py` | core/adapters | internal | C# SCIP adapter |
| `src/fs2/core/adapters/scip_adapter_fake.py` | core/adapters | internal | Test double |
| `src/fs2/core/adapters/scip_pb2.py` | core/adapters | internal | Generated protobuf bindings |
| `src/fs2/core/adapters/exceptions.py` | core/adapters | contract | Add SCIPAdapterError hierarchy |
| `src/fs2/config/objects.py` | config | contract | Add ProjectConfig, ProjectsConfig; extend CrossFileRelsConfig |
| `src/fs2/cli/projects.py` | cli | internal | discover-projects, add-project commands |
| `src/fs2/cli/main.py` | cli | cross-domain | Register new commands |
| `src/fs2/core/services/stages/cross_file_rels_stage.py` | core/services/stages | internal | Add SCIP provider path |
| `src/fs2/core/repos/graph_store_impl.py` | core/repos | internal | Bump FORMAT_VERSION to 1.2 |
| `tests/unit/adapters/test_scip_adapter.py` | tests | internal | SCIPAdapterBase tests |
| `tests/unit/adapters/test_scip_adapter_python.py` | tests | internal | Python adapter tests |
| `tests/unit/adapters/test_scip_adapter_typescript.py` | tests | internal | TypeScript adapter tests |
| `tests/unit/adapters/test_scip_adapter_go.py` | tests | internal | Go adapter tests |
| `tests/unit/adapters/test_scip_adapter_dotnet.py` | tests | internal | C# adapter tests |
| `tests/unit/config/test_projects_config.py` | tests | internal | Config model tests |
| `tests/unit/cli/test_projects_cli.py` | tests | internal | CLI command tests |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | `detect_project_roots()` already exists in cross_file_rels_stage.py (lines 136-194) with PROJECT_MARKERS for 6 languages — extract for reuse | Extract to shared module; extend markers for C#, Ruby |
| 02 | Critical | Protobuf is NOT in pyproject.toml dependencies — imports will fail | Add `protobuf>=4.25` to dependencies in Phase 1 |
| 03 | High | Config types must be registered in `YAML_CONFIG_TYPES` list (objects.py:1132) or they silently don't load | Add ProjectsConfig to registry; add registry completeness test |
| 04 | High | Edge data uses `{"edge_type": "references"}` only — no ref_kind (DYK analysis: descriptor suffixes describe target kind, not reference kind; lowest effort matches Serena) | Keep minimal edge format; can add classification later |
| 05 | ~~High~~ | ~~FORMAT_VERSION bump for ref_kind~~ | **DROPPED** — no ref_kind means no format change needed. Existing edges already use `{"edge_type": "references"}` |
| 06 | High | Existing adapter pattern: ABC in `*_adapter.py`, impl in `*_adapter_{provider}.py`, fake in `*_adapter_fake.py`, factory function for creation | Follow exactly for SCIP adapters |

## Harness Strategy

Harness: Not applicable (user override — continue without; unit tests + fixture .scip files + pytest suite sufficient).

## Phases

### Phase Index

| Phase | Title | Primary Domain | Objective (1 line) | Depends On |
|-------|-------|---------------|-------------------|------------|
| 1 | SCIP Adapter Foundation | core/adapters | SCIPAdapterBase + protobuf parsing + Python adapter + fake | None |
| 2 | Multi-Language Adapters | core/adapters | TypeScript, Go, C# adapter implementations | Phase 1 |
| 3 | Config & Discovery CLI | config, cli | ProjectConfig model + discover-projects + add-project commands | Phase 1 |
| 4 | Stage Integration & Migration | core/services/stages | Wire SCIP into CrossFileRelsStage + format version bump | Phases 1-3 |

---

### Phase 1: SCIP Adapter Foundation

**Objective**: Build the SCIPAdapterBase ABC with protobuf parsing, edge extraction, and a working Python adapter
**Domain**: core/adapters
**Delivers**:
- `protobuf` dependency in pyproject.toml
- Generated `scip_pb2.py` protobuf bindings
- `SCIPAdapterBase` ABC with universal protobuf parsing, edge extraction, dedup, filtering
- `SCIPPythonAdapter` implementation with symbol-to-node-id mapping
- `SCIPFakeAdapter` for testing
- `SCIPAdapterError` exception hierarchy in exceptions.py
- Full TDD test suite against fixture .scip files
**Depends on**: None
**Key risks**: Symbol-to-node-id mapping accuracy for Python; protobuf version compatibility

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 1.1 | Add `protobuf>=6.0` to pyproject.toml dependencies | config | `uv run python -c "import google.protobuf"` succeeds | DYK-038-05: pin >=6.0 — generated code requires matching runtime |
| 1.2 | Generate and commit `scip_pb2.py` from SCIP proto schema | core/adapters | `from fs2.core.adapters.scip_pb2 import Index` imports cleanly | Use `/tmp/scip.proto`; DYK-038-05: generate with same version |
| 1.3 | Add `SCIPAdapterError` hierarchy to exceptions.py | core/adapters | `SCIPAdapterError`, `SCIPIndexError`, `SCIPMappingError` defined | Per finding 06 |
| 1.4 | Create `SCIPAdapterBase` ABC in scip_adapter.py | core/adapters | `extract_cross_file_edges()`, `symbol_to_node_id()` abstract, protobuf parsing, dedup, filtering implemented | Per workshop 002 |
| 1.5 | Create `SCIPPythonAdapter` in scip_adapter_python.py | core/adapters | Maps Python SCIP symbols to fs2 node_ids; tested against `tests/fixtures/cross_file_sample/` .scip | DYK-038-04: symbol mapping is fuzzy lookup — try callable/class/type prefixes, fall back to file-level, log unmatched |
| 1.6 | Create `SCIPFakeAdapter` in scip_adapter_fake.py | core/adapters | `set_edges()` for test injection; passes ABC compliance | Per finding 06 |
| 1.7 | ~~Add `ref_kind` inference from SCIP descriptor suffixes~~ | ~~core/adapters~~ | ~~`#` → type, `().` → call, import occurrences → import; default "unknown"~~ | **DROPPED** — DYK: descriptor suffix = target kind, not reference kind; keep `{"edge_type": "references"}` only |
| 1.8 | TDD tests for SCIPAdapterBase + SCIPPythonAdapter | tests | Protobuf loading, edge extraction, dedup, filtering, symbol mapping all tested | Use scripts/scip/fixtures/ |

---

### Phase 2: Multi-Language Adapters

**Objective**: Implement TypeScript, Go, and C# SCIP adapters with per-language symbol-to-node-id mapping
**Domain**: core/adapters
**Delivers**:
- `SCIPTypeScriptAdapter` with file-path-based symbol mapping
- `SCIPGoAdapter` with import-path-to-file-path resolution
- `SCIPDotNetAdapter` with namespace-to-file resolution
- Per-language unit tests against fixture .scip files
**Depends on**: Phase 1
**Key risks**: Go import path resolution complexity; C# namespace resolution

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 2.1 | Create `SCIPTypeScriptAdapter` | core/adapters | Maps TS SCIP symbols to fs2 node_ids; tested against `scripts/scip/fixtures/typescript/` .scip | Backtick-quoted file paths in descriptors |
| 2.2 | Create `SCIPGoAdapter` | core/adapters | Maps Go SCIP symbols to fs2 node_ids; handles import path → file path | Needs module prefix stripping from go.mod |
| 2.3 | Create `SCIPDotNetAdapter` | core/adapters | Maps C# SCIP symbols to fs2 node_ids; resolves namespace → file via document paths | Uses index document relative_paths |
| 2.4 | Add type alias normalisation | core/adapters | `ts`→`typescript`, `cs`/`csharp`→`dotnet`, `js`→`javascript` accepted everywhere | Per spec Q5 clarification |
| 2.5 | TDD tests for all 3 adapters | tests | Each adapter tested against its fixture .scip file | Generate fixture .scip files as test setup |

---

### Phase 3: Config & Discovery CLI

**Objective**: Add project configuration model, CLI commands for project discovery, and remove Serena — SCIP is the only cross-file rels provider
**Domain**: config, cli, core/services
**Delivers**:
- `ProjectConfig` and `ProjectsConfig` pydantic models (YAML field: `entries`)
- Serena removal from `CrossFileRelsConfig` and all codebase references
- `ruamel.yaml` dependency for comment-preserving config writes
- `fs2 discover-projects` command
- `fs2 add-project` command (comment-preserving YAML)
- Extract `detect_project_roots()` to shared module (remove child dedup, add C#/Ruby markers)
**Depends on**: Phase 1
**Key risks**: Config registration silent failure; Serena cleanup scope; CLI UX for edge cases

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 3.0 | Add `ruamel.yaml` to pyproject.toml | config | Import succeeds | DYK #4: comment-preserving YAML writes |
| 3.1 | Add `ProjectConfig` and `ProjectsConfig` to config/objects.py | config | Models validate type, path, project_file, enabled, options; type aliases normalised; YAML field is `entries` | DYK #1: avoids `projects.projects` stutter |
| 3.2 | Remove Serena from CrossFileRelsConfig + all codebase refs | config, stages, cli, tests | 4 Serena fields removed; all 14 source files + tests cleaned | DYK #3: Serena removed entirely |
| 3.3 | Register `ProjectsConfig` in `YAML_CONFIG_TYPES` | config | Config loads from YAML; add registry completeness test | Per finding 03 |
| 3.4 | Extract `detect_project_roots()` to shared module | core/services | Function in shared module; child dedup removed; markers extended; one entry per (path, type) | DYK #2: child dedup wrong for SCIP |
| 3.5 | Create `fs2 discover-projects` CLI command | cli | Lists detected projects with type, path, project file, indexer status (✅/⚠️/❌) | Per workshop 003 |
| 3.6 | Create `fs2 add-project` CLI command | cli | Comment-preserving YAML write via ruamel.yaml; idempotent | DYK #4: must preserve comments |
| 3.7 | Register commands in main.py | cli | `fs2 discover-projects` and `fs2 add-project` appear in `fs2 --help` | No require_init guard |
| 3.8 | Tests for config models + CLI commands + discovery | tests | Pydantic validation, discovery markers, CLI output, Serena removal verified | |

---

### Phase 4: Stage Integration

**Objective**: Wire SCIP adapters into CrossFileRelsStage with subprocess indexer invocation and auto-discovery support
**Domain**: core/services/stages
**Delivers**:
- CrossFileRelsStage uses SCIP adapters (Serena removed in Phase 3)
- SCIP indexer invocation via subprocess
- Auto-discovery from `ProjectsConfig.auto_discover` when no explicit entries
- Edge metadata: `{"edge_type": "references"}`
- `.fs2/scip/` cache directory for index files
- End-to-end integration tests
**Depends on**: Phases 1-3
**Key risks**: Subprocess indexer invocation reliability; edge density variance across languages

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 4.1 | Wire SCIP into CrossFileRelsStage | core/services/stages | Iterate ProjectsConfig entries, run indexer per project, parse edges | Serena path removed in Phase 3 |
| 4.2 | Implement indexer invocation via subprocess | core/services/stages | `scip-python index .` runs, produces index.scip; errors logged gracefully | Per workshop 001 boot specs |
| 4.3 | Wire adapter selection based on project type | core/services/stages | Use `create_scip_adapter()` factory from Phase 2 | Factory + normalise_language() |
| 4.4 | Add `.fs2/scip/` cache directory management | core/services/stages | index.scip cached per project slug; re-used if source unchanged | DYK-038-03: add to .gitignore |
| 4.5 | ~~Bump FORMAT_VERSION 1.1 → 1.2~~ | ~~core/repos~~ | ~~Old graphs load with warning~~ | **DROPPED** — no format change |
| 4.6 | ~~Add backward compat migration logic~~ | ~~core/repos~~ | ~~Migration for old edges~~ | **DROPPED** — no migration needed |
| 4.7 | Wire auto_discover: read ProjectsConfig, fall back to detect_project_roots() | core/services/stages | AC9: empty entries + auto_discover=true → discovers from markers | Moved from Phase 3 — config model built there, wiring here |
| 4.8 | Integration tests: end-to-end SCIP → edges → graph | tests | Run indexer on fixture, parse index, verify edges in graph | Marked @pytest.mark.slow |
| 4.9 | Update documentation (README + docs/how/) | docs | SCIP section in README; detailed guide in docs/how/ | Per spec clarification Q2 |

---

### Acceptance Criteria

- [ ] AC1: `fs2 scan` on Python project with scip-python produces cross-file reference edges
- [ ] AC2: `fs2 scan` on TypeScript project with scip-typescript produces edges
- [ ] AC3: `fs2 scan` on Go project with scip-go produces edges
- [ ] AC4: `fs2 scan` on C# project with scip-dotnet produces edges
- [ ] AC5: Missing SCIP indexer → info message with install instructions, scan continues
- [ ] AC6: `fs2 discover-projects` lists detected projects with indexer status
- [ ] AC7: `fs2 add-project 1 2 3` writes projects to config
- [ ] AC8: `projects` config accepts type, path, project_file, enabled, options
- [ ] AC9: Empty entries + auto_discover=true → auto-discovers from markers
- [x] ~~AC10~~: DROPPED — Serena removed entirely, no backward compat needed
- [ ] AC11: Edges deduplicated — no duplicate source→target pairs
- [ ] AC12: Local symbols, stdlib refs, self-refs filtered out
- [ ] AC13: Type aliases (ts, cs, js, csharp) normalised to canonical names
- [x] ~~AC14~~: DROPPED — edges use `{"edge_type": "references"}` only
- [ ] AC15: index.scip cached in `.fs2/scip/` for re-use

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SCIP indexer not installed | High | Medium | Graceful skip with install instructions |
| Symbol-to-node-id mismatch | Medium | High | Per-language unit tests; fallback to file-level edges |
| Go import path resolution | Medium | Medium | Use go.mod module path; fall back to package-level |
| Config silent load failure | Medium | High | Registry completeness test (finding 03) |
| ~~ref_kind on old graphs~~ | ~~Medium~~ | ~~Medium~~ | **DROPPED** — no ref_kind, no format change |
| Protobuf version conflict | Low | High | Pin `protobuf>=6.0`; test in clean venv |
