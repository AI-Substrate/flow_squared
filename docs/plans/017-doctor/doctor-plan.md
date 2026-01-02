# fs2 Doctor Command Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-01-02
**Spec**: [./doctor-spec.md](./doctor-spec.md)
**Status**: READY

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: Users setting up fs2 (especially via uvx) lack visibility into which configuration files are loaded, whether providers are configured, and why config issues occur.

**Solution**: Create `fs2 doctor` command that displays configuration health with Rich output, showing all config sources, merge chain with override warnings, provider status, placeholder resolution, and actionable guidance with clickable GitHub URLs. Additionally enhance `fs2 init` to automatically bootstrap both local and global configs in one command.

**Expected Outcome**: Users can quickly diagnose config issues, understand the precedence chain, and get direct links to setup documentation.

---

## Critical Research Findings (Concise)

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **R1-01**: `load_secrets_to_env()` mutates global `os.environ` | Create read-only variant or use `dotenv_values()` directly without side effects |
| 02 | Critical | **R1-06**: Secret detection could expose values in logs | Never print values; only field name and length. Use existing `_is_literal_secret()` |
| 03 | Critical | **R1-03**: Placeholder resolution depends on current env state | Document scope explicitly; load secrets first before checking placeholders |
| 04 | High | **I1-02**: Use raw loaders to avoid singleton pollution (PL-01) | Call `load_yaml_config()` directly, not `FS2ConfigurationService()` |
| 05 | High | **I1-03**: Use `ConsoleAdapter` abstraction for Rich output | Use `RichConsoleAdapter` with `print_success/warning/error/panel` methods |
| 06 | High | **R1-04**: Deep merge doesn't track source attribution | Load configs separately; compare values to detect overrides manually |
| 07 | High | **I1-04**: Provider detection requires checking nested fields | Check `llm.provider`, `embedding.mode` and required sub-fields per provider type |
| 08 | High | **R1-07**: `init` creates both local and global; skip global if exists | Check if global exists before creating; skip silently if present; no --global flag needed |
| 09 | Medium | **I1-01**: Follow CLI pattern from `scan.py` and `init.py` | Create `doctor.py`, register in `main.py` via `app.command()` |
| 10 | Medium | **I1-05**: Placeholder pattern is `${VAR_NAME}` | Use regex `r"\$\{([A-Z_][A-Z0-9_]*)\}"` to find placeholders |
| 11 | Medium | **R1-05**: Rich output adapts to terminal width/TTY | Test with various widths; use graceful degradation for narrow terminals |
| 12 | Medium | **I1-07**: Use `FakeConfigurationService` and `tmp_path` for tests | Create temp directories with real config files; avoid mocks entirely |
| 13 | Medium | **R1-08**: "Configured" status is ambiguous | Show requirements: `[provider=azure, api_key=placeholder]` not just "configured" |
| 14 | Low | **R1-02**: TOCTOU race in file existence checks | Use try-except on open, not `.exists()` check; handle `FileNotFoundError` |
| 15 | Low | **I1-08**: Support `--format json` for CI (deferred) | Focus on Rich text output first; JSON output is deferred per spec Q1 |
| 16 | High | **R1-09**: `scan` creates `.fs2/` via `graph_path.parent.mkdir()` | Add CLI guard that fails fast BEFORE any mkdir; check `.fs2/config.yaml` exists |

---

## Implementation (Single Phase)

**Objective**: Implement `fs2 doctor` command, enhance `fs2 init --global`, and create example config templates.

**Testing Approach**: Full TDD - write comprehensive tests before implementation
**Mock Usage**: Avoid mocks entirely - use real fixtures, temp directories, and `FakeConfigurationService`

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [ ] | T001 | Create example config templates in src/fs2/docs/ and register in registry.yaml | 2 | Setup | -- | /workspaces/flow_squared/src/fs2/docs/config.yaml.example, /workspaces/flow_squared/src/fs2/docs/secrets.env.example, /workspaces/flow_squared/src/fs2/docs/registry.yaml | Files exist with documented LLM/embedding sections; registered with category/tags; AC-29, AC-30, AC-31 | Use importlib.resources to access |
| [ ] | T002 | Write tests for config file discovery (all 5 locations) | 2 | Test | T001 | /workspaces/flow_squared/tests/unit/cli/test_doctor.py | Tests cover: user/project YAML, user/project secrets.env, .env; missing file handling; AC-02 | Use tmp_path fixtures |
| [ ] | T003 | Write tests for merge chain computation and override detection | 2 | Test | T002 | /workspaces/flow_squared/tests/unit/cli/test_doctor.py | Tests cover: multi-layer merge, leaf-level overrides, source attribution; AC-03, AC-04 | Test R1-04 edge cases |
| [ ] | T004 | Write tests for provider status detection (LLM/embedding) | 2 | Test | T002 | /workspaces/flow_squared/tests/unit/cli/test_doctor.py | Tests cover: configured/not configured, required fields per provider; AC-05, AC-06, AC-07 | Include GitHub URL generation |
| [ ] | T005 | Write tests for placeholder validation | 2 | Test | T002 | /workspaces/flow_squared/tests/unit/cli/test_doctor.py | Tests cover: ${VAR} detection, resolved/unresolved status; AC-08 | Test R1-03 scope |
| [ ] | T006 | Write tests for literal secret detection | 2 | Test | T002 | /workspaces/flow_squared/tests/unit/cli/test_doctor.py | Tests cover: sk-* prefix, >64 char strings in secret fields; AC-13 | Never expose actual values (R1-06) |
| [ ] | T007 | Write tests for edge cases (no config, central-only, warnings) | 2 | Test | T002 | /workspaces/flow_squared/tests/unit/cli/test_doctor.py | Tests cover: no configs → suggest init, central exists but no local .fs2; AC-09, AC-10 | Test exit codes 0 vs 1 |
| [ ] | T008 | Implement config inspection helpers (read-only) | 2 | Core | T002-T007 | /workspaces/flow_squared/src/fs2/cli/doctor.py | Helpers read configs without side effects; use dotenv_values() not load_secrets_to_env() | Per R1-01 mitigation |
| [ ] | T009 | Implement merge chain computation with source attribution | 3 | Core | T008 | /workspaces/flow_squared/src/fs2/cli/doctor.py | Can identify which source each value came from; override detection works | Per R1-04 mitigation |
| [ ] | T010 | Implement provider status detection | 2 | Core | T008 | /workspaces/flow_squared/src/fs2/cli/doctor.py | Detects LLM/embedding config with required field status | Per R1-08 - show requirements |
| [ ] | T011 | Implement placeholder validation | 2 | Core | T008 | /workspaces/flow_squared/src/fs2/cli/doctor.py | Finds all ${VAR} placeholders, checks os.environ resolution | Regex pattern from I1-05 |
| [ ] | T012 | Implement literal secret detection | 2 | Core | T008 | /workspaces/flow_squared/src/fs2/cli/doctor.py | Detects sk-* and >64 char strings; never prints values | Per R1-06 - field name only |
| [ ] | T013 | Implement Rich output formatting | 2 | Core | T008-T012 | /workspaces/flow_squared/src/fs2/cli/doctor.py | Uses ConsoleAdapter; panels, tables, colored indicators; AC-11 | Match mockup from spec |
| [ ] | T014 | Implement doctor() command and register in main.py | 2 | Core | T013 | /workspaces/flow_squared/src/fs2/cli/doctor.py, /workspaces/flow_squared/src/fs2/cli/main.py | `fs2 doctor` runs and shows output; exit 0 healthy, 1 issues; AC-01, AC-12 | Follow I1-01 CLI pattern |
| [ ] | T015 | Write tests for enhanced init (local + global) | 2 | Test | T001 | /workspaces/flow_squared/tests/unit/cli/test_init.py | Tests cover: creates both local and global, skips global if exists, shows cwd, warns if no .git, creates .gitignore; AC-14-22 | No --global flag |
| [ ] | T016 | Implement enhanced init (local + global) | 2 | Core | T015, T001 | /workspaces/flow_squared/src/fs2/cli/init.py | Creates both configs; shows cwd; red warning if no .git; creates .fs2/.gitignore; AC-14-22 | .gitignore ignores all except config.yaml |
| [ ] | T017 | Write tests for CLI guard (require init) | 2 | Test | T001 | /workspaces/flow_squared/tests/unit/cli/test_cli_guard.py | Tests: scan/search/tree/mcp fail without .fs2/config.yaml; init/doctor/--help work; error shows PWD and .git warning; AC-23-28 | Fail fast before mkdir |
| [ ] | T018 | Implement CLI guard as @require_init decorator | 2 | Core | T017 | /workspaces/flow_squared/src/fs2/cli/guard.py | @require_init decorator checks .fs2/config.yaml; fails with PWD + red .git warning; AC-23-28 | Decorator (not callback) so --help works |
| [ ] | T019 | Apply CLI guard to scan, search, tree, get-node, mcp | 2 | Core | T018 | /workspaces/flow_squared/src/fs2/cli/scan.py, search.py, tree.py, get_node.py, mcp.py | Guard runs before mkdir; mkdir stays but only executes after guard passes | Reorder, don't remove mkdir |
| [ ] | T020 | Update README.md with doctor command documentation | 1 | Docs | T014 | /workspaces/flow_squared/README.md | README lists `fs2 doctor` with brief description and example output | Per Documentation Strategy |
| [ ] | T021 | Run full test suite and verify all ACs pass | 1 | Test | T001-T020 | -- | All 31 acceptance criteria verified; tests pass; no regressions | Final validation |

### Acceptance Criteria

- [ ] AC-01: `fs2 doctor` displays header with current working directory
- [ ] AC-02: Lists all 5 config file locations with found/not found status
- [ ] AC-03: Displays merge chain showing precedence layers
- [ ] AC-04: Warns when local config overrides central value
- [ ] AC-05: Shows LLM configuration status
- [ ] AC-06: Shows embedding configuration status
- [ ] AC-07: Shows clickable GitHub URLs for unconfigured providers
- [ ] AC-08: Lists placeholders with resolution status
- [ ] AC-09: Suggests `fs2 init` when no configs exist
- [ ] AC-10: Warns when central config exists but no local .fs2/
- [ ] AC-11: Uses Rich formatting (panels, tables, colors)
- [ ] AC-12: Exit code 0 when healthy, 1 when issues
- [ ] AC-13: Warns about literal secrets (sk-*, >64 char)
- [ ] AC-14: `fs2 init` creates both local `./.fs2/` AND global `~/.config/fs2/` in one command
- [ ] AC-15: If global `~/.config/fs2/` already exists, it is skipped (not overwritten, no error)
- [ ] AC-16: If local `./.fs2/` already exists, `--force` is required to overwrite
- [ ] AC-17: Example files sourced from docs/examples/
- [ ] AC-18: Reports what was created: "Created local config", "Created global config", "Skipped global (already exists)"
- [ ] AC-19: No `--global` flag needed - users don't need to understand config hierarchy
- [ ] AC-20: `fs2 init` displays current working directory path before creating configs
- [ ] AC-21: If no `.git` folder exists, shows prominent red warning (but does not fail)
- [ ] AC-22: `fs2 init` creates `.fs2/.gitignore` that ignores everything except `config.yaml`
- [ ] AC-23: Commands like `scan`, `search`, `tree`, `get-node`, `mcp` fail if `.fs2/config.yaml` doesn't exist
- [ ] AC-24: When command fails due to missing init, error message shows current working directory path
- [ ] AC-25: Error message suggests running `fs2 init` when `.fs2/` is missing
- [ ] AC-26: If no `.git` folder exists, error also shows prominent red warning (helps identify wrong directory)
- [ ] AC-27: These commands always work without init: `init`, `doctor`, `--help`, `--version`, and any subcommand `--help`
- [ ] AC-28: No auto-init behavior - commands never create `.fs2/` implicitly
- [ ] AC-29: src/fs2/docs/config.yaml.example exists
- [ ] AC-30: src/fs2/docs/secrets.env.example exists
- [ ] AC-31: Example templates registered in src/fs2/docs/registry.yaml

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Config loader side effects (R1-01) | High | Medium | Use `dotenv_values()` read-only; avoid `load_secrets_to_env()` |
| Secret exposure in logs (R1-06) | Low | High | Never print values; only field names and lengths |
| Merge attribution complexity (R1-04) | High | Medium | Load configs separately; manual comparison for overrides |
| Terminal width issues (R1-05) | Medium | Low | Test with various widths; graceful degradation |
| CLI guard breaks existing workflows (R1-09) | Low | Medium | Clear error message with PWD and `fs2 init` suggestion; `--help` always works |

---

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/017-doctor/doctor-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended for CS-3+ tasks)
- **Optional task expansion**: `/plan-5-phase-tasks-and-brief` (if you want a separate dossier)
