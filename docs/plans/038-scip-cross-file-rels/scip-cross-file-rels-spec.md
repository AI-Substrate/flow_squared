# SCIP Cross-File Relationships

**Mode**: Full

📚 This specification incorporates findings from exploration.md and three authoritative workshops:
- [001-scip-language-boot.md](workshops/001-scip-language-boot.md) — Per-language SCIP boot requirements
- [002-scip-cross-language-standardisation.md](workshops/002-scip-cross-language-standardisation.md) — Adapter hierarchy and symbol standardisation
- [003-scip-project-config.md](workshops/003-scip-project-config.md) — Project configuration and discovery CLI

## Research Context

The current cross-file relationship system uses Serena (LSP/Pyright) running as a pool of 15+ parallel MCP server instances. While functional, it has significant operational complexity: port management, process lifecycle, ~6GB memory for 20 Pyright instances, and limited language support.

**Key research findings (from exploration.md)**:
- SCIP (Source Code Intelligence Protocol) by Sourcegraph produces a universal protobuf index (`index.scip`) via offline batch indexing — no runtime servers needed
- Tested 4 SCIP indexers (Python, TypeScript, Go, C#/.NET) on multi-file fixtures — all successfully extracted cross-file relationships
- SCIP output format is **identical** across all languages: same protobuf schema, same symbol format (`<scheme> <manager> <package> <version> <descriptor>`), same SymbolRoles bitmask, same range format
- Cross-file edges are extracted by matching definitions in file A with references in file B — **one algorithm for all languages**
- Only the symbol-to-node-id mapping varies per language (different module path encoding)

## Summary

Replace Serena's LSP pool with SCIP indexers for cross-file relationship discovery. Add a project discovery system that detects language projects in the codebase, lets users configure them, and runs the appropriate SCIP indexer per project during scan. The adapter architecture uses a shared base for protobuf parsing with per-language subclasses that handle symbol-to-node-id translation.

This gives fs2 cross-file relationships for **10+ languages** (vs 2-3 with Serena), with **zero runtime servers**, **deterministic output**, and **dramatically simpler operations** (no port management, no process pools, no memory pressure from parallel LSP instances).

## Goals

- **Multi-language cross-file relationships**: Support Python, TypeScript/JavaScript, Go, C#/.NET out of the box, with an extensible adapter pattern for Java, Rust, C++, Ruby
- **Zero-config for simple projects**: Auto-discover language projects via marker files (pyproject.toml, tsconfig.json, go.mod, etc.) — users don't need to configure anything for single-language repos
- **Explicit config for complex repos**: Monorepos and multi-project codebases can declare projects in config with type, path, and project file
- **Project discovery CLI**: `fs2 discover-projects` scans and lists detected projects; `fs2 add-project` writes selected projects to config
- **Offline batch indexing**: Run SCIP indexers as CLI commands during `fs2 scan` — no runtime servers, no port management, no process pools
- **Deterministic output**: Same source code always produces same cross-file edges
- **Backward-compatible migration**: Serena remains available via `provider: serena` config; SCIP becomes the new default
- **Debuggable**: `scip print index.scip` shows human-readable output for troubleshooting

## Non-Goals

- **Real-time/live indexing**: SCIP indexes are computed at scan time, not continuously updated
- **Cross-project references**: Edges are within-project only — no references between a Python backend and a TypeScript frontend
- **Auto-installing SCIP indexers**: fs2 will detect and report missing indexers with install instructions, but will not auto-install them (user must install)
- **Call expression classification**: Edges store `references` type only (`{"edge_type": "references"}`) — no attempt to classify as call/import/type. Can be added later if needed
- **Third-party library resolution**: Only project-internal references stored — stdlib/pip/npm imports resolved by SCIP but only edges to nodes in the fs2 graph are kept
- **Docker-based indexers**: v1 supports locally-installed indexers only — Docker support is a future enhancement
- **Removing Serena**: Serena remains as an alternative provider; deprecation is a separate future decision

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| core/adapters | existing | **modify** | Add SCIPAdapterBase ABC + per-language adapter implementations + SCIPFakeAdapter |
| core/services/stages | existing | **modify** | Update CrossFileRelsStage to support SCIP provider alongside Serena |
| core/models | existing | **consume** | CodeNode used as-is; PipelineContext.cross_file_edges unchanged |
| config | existing | **modify** | Add ProjectConfig, ProjectsConfig models; add `provider` field to CrossFileRelsConfig |
| cli | existing | **modify** | Add `discover-projects` and `add-project` commands |
| core/repos | existing | **consume** | GraphStore edge storage unchanged (already supports `edge_type="references"`) |
| mcp | existing | **consume** | MCP `get_node` relationships output unchanged |

No new domains are created. This feature threads through existing domains.

## Complexity

- **Score**: CS-3 (medium)
- **Breakdown**: S=2, I=1, D=1, N=1, F=0, T=1 (Total P=6)
- **Confidence**: 0.85
- **Assumptions**:
  - SCIP indexers produce reliable output for typical project structures (empirically validated for 4 languages)
  - Protobuf parsing in Python is straightforward via generated bindings
  - Symbol-to-node-id mapping can be implemented accurately for each language (prototype confirms feasibility)
  - Users have the relevant language toolchains installed (Node.js for Python/TS, Go, .NET SDK, etc.)
- **Dependencies**:
  - `protobuf` Python package (for reading .scip files)
  - Per-language SCIP indexers (external CLI tools, user-installed)
  - Generated `scip_pb2.py` protobuf bindings (committed to repo)
- **Risks**:
  - Go symbol mapping requires resolving import paths to file paths (more complex than other languages)
  - C# symbol mapping uses namespaces not file paths (requires document-level resolution)
  - Some SCIP indexers less actively maintained than others
  - Edge density varies significantly across languages (4x) — deduplication normalises but worth monitoring
- **Phases**: ~4 natural phases:
  1. SCIPAdapterBase + protobuf parsing + Python adapter
  2. TypeScript/Go/C# adapters
  3. Project config + discovery CLI
  4. CrossFileRelsStage integration + migration from Serena default

## Acceptance Criteria

1. **AC1**: Running `fs2 scan` on a Python project with `scip-python` installed produces cross-file reference edges identical in structure to current Serena-produced edges (`edge_type="references"`)
2. **AC2**: Running `fs2 scan` on a TypeScript project with `scip-typescript` installed produces cross-file reference edges
3. **AC3**: Running `fs2 scan` on a Go project with `scip-go` installed produces cross-file reference edges
4. **AC4**: Running `fs2 scan` on a C# project with `scip-dotnet` installed produces cross-file reference edges
5. **AC5**: Running `fs2 scan` when no SCIP indexer is installed for the detected language logs an info message with install instructions and continues without cross-file edges
6. **AC6**: Running `fs2 discover-projects` in a multi-language repo lists all detected projects with type, path, project file, and indexer installation status
7. **AC7**: Running `fs2 add-project 1 2 3` writes selected projects to `.fs2/config.yaml` under the `projects` section
8. **AC8**: The `.fs2/config.yaml` `projects` section accepts entries with `type`, `path`, `project_file`, `enabled`, and `options` fields
9. **AC9**: When `projects` section is empty and `auto_discover` is true (default), fs2 auto-discovers projects from marker files during scan
10. **AC10**: Running `fs2 scan` with `cross_file_rels.provider: serena` uses the existing Serena path (backward compatibility)
11. **AC11**: Cross-file edges from SCIP are deduplicated — no duplicate source→target pairs in the graph
12. **AC12**: Local symbols (`local N`), stdlib references, and self-references are filtered out of SCIP edges before storage
13. **AC13**: Project type accepts aliases (`ts` for `typescript`, `cs`/`csharp` for `dotnet`, `js` for `javascript`) — normalised internally to canonical names
14. **AC14**: ~~Cross-file edges include `ref_kind`~~ **DROPPED** — edges use `{"edge_type": "references"}` only, matching current Serena format. Lowest effort, can add classification later
15. **AC15**: SCIP index files are cached in `.fs2/scip/{project-slug}/index.scip` for re-use and debugging

## Risks & Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SCIP indexer not installed for user's language | High | Medium | Graceful skip with clear install instructions; auto-discover reports status |
| Symbol-to-node-id mapping produces incorrect matches | Medium | High | Per-language unit tests against fixture indexes; fallback to file-level edges |
| Go import path → file path resolution fails for complex packages | Medium | Medium | Use Go module structure from go.mod; fall back to package-level edges |
| C# namespace → file resolution fails for partial classes | Low | Low | Use SCIP document paths directly; accept some unmapped symbols |
| SCIP indexer produces empty index for valid project | Low | High | Validate index has >0 documents before processing; log warning if empty |
| Protobuf schema changes in future SCIP versions | Low | Medium | Pin to known scip.proto version; regenerate bindings on upgrade |

**Assumptions**:
- Users have the relevant language toolchain installed (Node.js, Go, .NET SDK) — SCIP indexers won't install these
- Project structures follow standard conventions (go.mod at module root, tsconfig.json at project root, etc.)
- `protobuf>=4.25` is acceptable as a new dependency
- The existing graph format (NetworkX DiGraph with `edge_type="references"` edges) is sufficient — no format changes needed

## Open Questions

All open questions have been resolved — see Clarifications below.

## Documentation Strategy

- **Location**: Hybrid (README section + docs/how/ guide)
- **Rationale**: Users need quick-start in README (what SCIP is, how to install an indexer, basic config) plus a detailed guide in docs/how/ covering all languages, project discovery workflow, config options, and troubleshooting. Documentation must be detailed enough for MCP agents to consume and guide users through setup.
- **README.md**: Section on SCIP cross-file relationships — what they are, quick install for Python, basic config example
- **docs/how/**: Comprehensive guide covering all supported languages, project discovery, config format, indexer-specific options, troubleshooting, and workspace configuration

## Workshop Opportunities

All critical workshops have been completed:

| Topic | Type | Status | Document |
|-------|------|--------|----------|
| SCIP Language Boot | Integration Pattern | ✅ Done | [001-scip-language-boot.md](workshops/001-scip-language-boot.md) |
| SCIP Cross-Language Standardisation | Integration Pattern | ✅ Done | [002-scip-cross-language-standardisation.md](workshops/002-scip-cross-language-standardisation.md) |
| SCIP Project Configuration | Storage Design / CLI Flow | ✅ Done | [003-scip-project-config.md](workshops/003-scip-project-config.md) |

No further workshops are needed before architecture.

## Testing Strategy

- **Approach**: Hybrid
- **Rationale**: SCIPAdapterBase protobuf parsing and edge extraction have real algorithmic complexity — TDD for these. Per-language symbol mapping needs per-language unit tests with fixture .scip files. CLI commands and config models are mechanical — lightweight tests.
- **TDD Focus Areas**:
  - SCIPAdapterBase: protobuf loading, edge extraction, deduplication, filtering
  - Per-language symbol_to_node_id(): tested against real .scip fixtures from scripts/scip/fixtures/
  - Project discovery: marker file detection, priority rules, skip patterns
- **Lightweight Areas**:
  - CLI commands (discover-projects, add-project)
  - ProjectConfig/ProjectsConfig pydantic validation
  - CrossFileRelsConfig provider field
- **Integration Tests** (marked slow):
  - End-to-end: run indexer on fixture project → parse index → verify edges match expected
- **Mock Policy**: Allow targeted mocks — mock subprocess calls for indexer invocation; use real .scip fixture files for adapter tests; FakeConfigurationService for config-dependent tests

## Clarifications

### Session 2026-03-16

| # | Question | Answer |
|---|----------|--------|
| Q1 | Workflow Mode | **Full** — Multi-phase plan, required dossiers, all gates |
| Q2 | Documentation Strategy | **Hybrid** — README section + docs/how/ guide. Docs must be detailed enough for MCP agents to consume and guide users |
| Q3 | Domain Review | **Confirmed** — 7 existing domains, all changes respect contracts, no new domains |
| Q4 | Harness | **Continue without** — Unit tests + fixture .scip files + pytest suite sufficient |
| Q5 | Type aliases | **Accept everywhere** — `ts`, `cs`, `csharp`, `js` normalised internally to canonical names |
| Q6 | Index.scip storage | **Cache in `.fs2/scip/`** — enables re-use across incremental scans and debugging with `scip print` |
| Q7 | Edge metadata | **Minimal: `{"edge_type": "references"}` only** — matches current Serena format. Descriptor-based classification (ref_kind) dropped after DYK analysis showed suffix describes target symbol kind, not reference kind. Can add later if needed |
| Q8 | Monorepo workspaces | **Require user specification** in project `options` — docs must be detailed enough for MCP agents to guide users. No auto-detection of workspace manager |
