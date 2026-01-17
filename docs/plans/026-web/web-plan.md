# fs2 Web UI Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2026-01-15
**Spec**: [./web-spec.md](./web-spec.md)
**Status**: DRAFT

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 1: Foundation](#phase-1-foundation)
   - [Phase 2: Diagnostics Integration](#phase-2-diagnostics-integration)
   - [Phase 3: Configuration Editor](#phase-3-configuration-editor)
   - [Phase 4: Setup Wizards](#phase-4-setup-wizards)
   - [Phase 5: Graph Management](#phase-5-graph-management)
   - [Phase 6: Exploration](#phase-6-exploration)
   - [Phase 7: Polish & Documentation](#phase-7-polish--documentation)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

### Problem Statement

First-time fs2 users struggle with multi-source YAML configuration (LLM providers, embeddings, multi-graph setup). The 7-phase configuration loading pipeline with placeholder syntax (`${VAR}`), file precedence rules, and provider-specific validation creates significant onboarding friction.

### Solution Approach

- **fs2 Hub**: Streamlit-based portal for configuring and browsing fs2
- **Guided Wizards**: Step-by-step setup for Azure LLM, OpenAI, and fake providers
- **Live Diagnostics**: Doctor output after every configuration change
- **Safe Editing**: Automatic backups before any config modification
- **Global Graph Selector**: Reusable dropdown persisting across all pages
- **Integrated Browse + Search**: Fluid workflow between tree navigation and search

### Expected Outcomes

- Reduce first-time setup from ~30 minutes of YAML editing to ~5 minutes of wizard completion
- Eliminate configuration errors from incorrect placeholder syntax or missing fields
- Enable users to verify "my setup works" before integrating with AI tools

### Success Metrics

- All 22 acceptance criteria passing
- Full TDD test coverage (>80% for new code)
- Zero secret exposure in UI, logs, or session state

---

## Technical Context

### Current System State

fs2 provides CLI (`fs2 scan`, `fs2 search`, etc.) and MCP server interfaces for code intelligence. Configuration is managed via:
- `~/.config/fs2/config.yaml` (user global)
- `.fs2/config.yaml` (project-specific)
- `secrets.env` files and environment variables

### Integration Requirements

| Existing Component | Integration Approach |
|-------------------|---------------------|
| FS2ConfigurationService | **DO NOT USE** for config display - creates side effects |
| GraphService | INJECT for exploration features |
| TreeService, SearchService | INJECT for browse/search |
| Doctor validation | PORT logic, do not import module |

### Constraints and Limitations

1. **PL-01**: `load_secrets_to_env()` mutates global `os.environ` - web UI must use read-only inspection
2. **PL-02**: Deep merge loses source attribution - must track value origins separately
3. **PL-06**: Streamlit sessions should reload config each time (stateless per request)
4. **AC-16**: Never call `load_secrets_to_env()` or mutate `os.environ`

### Assumptions

1. Streamlit provides sufficient components for YAML editing and form validation
2. Existing doctor validation logic can be extracted and reused
3. Users accept localhost-only access (no remote hosting requirement)
4. Python 3.12 compatibility required

---

## Critical Research Findings

### Critical Discoveries

#### Discovery 01: ConfigInspectorService is Critical Path
**Impact**: Critical
**Sources**: [I1-03, I1-05, R1-01]

ConfigInspectorService must be implemented first - it blocks all config display, source attribution, placeholder analysis, and wizard validation. Must use `dotenv_values()` (read-only) instead of `load_dotenv()` (mutates).

```python
# WRONG - Mutates os.environ
from dotenv import load_dotenv
load_dotenv(secrets_path)

# CORRECT - Returns dict without modification
from dotenv import dotenv_values
secrets = dotenv_values(secrets_path)
```

**Affects Phases**: 1, 2, 3, 4

---

#### Discovery 02: Secret Exposure Prevention Required
**Impact**: Critical
**Sources**: [R1-03]

API keys could be exposed in logs, UI, session state, or browser history. Must implement defense-in-depth:
- Never store raw secrets in `st.session_state`
- Use `type="password"` for all secret inputs
- Implement `mask_secret()` utility showing `[SET]` not actual values
- Add logging sanitization filter

```python
def mask_secret(value: str | None) -> str:
    if value is None:
        return "[NOT SET]"
    if value.startswith("${"):
        return value  # Placeholder, show as-is
    return "[SET]"
```

**Affects Phases**: All

---

#### Discovery 03: Source Attribution Must Track Override Chain
**Impact**: High
**Sources**: [I1-03, R1-02, PL-02]

The deep_merge() function loses information about which source each value came from. UI must show `(value, source)` pairs with override history.

```python
@dataclass
class ConfigValue:
    value: Any
    source: Literal["user", "project", "env", "default"]
    source_file: Path | None
    override_chain: list[tuple[str, Any]]  # Previous values overridden
```

**Affects Phases**: 1, 3

---

#### Discovery 04: Three-State Placeholder Resolution
**Impact**: High
**Sources**: [R1-06, PL-09]

Placeholder expansion has two-stage validation. UI must display three distinct states:
1. `${VAR}` - Placeholder present, showing literal syntax
2. `[SET]` - Placeholder resolved successfully (masked)
3. `⚠ ${MISSING}` - Placeholder present but env var not set

**Affects Phases**: 3, 4

---

#### Discovery 05: Backup-Before-Save Transaction Pattern
**Impact**: High
**Sources**: [R1-04]

Config backup could fail silently. Must implement atomic backup with verification:
1. Create backup to temp file
2. Verify backup integrity (checksum)
3. Atomic rename temp → backup
4. Only then write new config

**Affects Phases**: 3

---

#### Discovery 06: Session Isolation Required
**Impact**: High
**Sources**: [R1-05, PL-06]

No module-level service instances allowed. All services must be session-scoped via `st.session_state` with namespaced keys (`fs2_web_*`).

**Affects Phases**: All

---

#### Discovery 07: Global Graph Selector Persistence
**Impact**: High
**Sources**: [I1-07]

Graph selection must persist across page navigation. Use session state with `st.rerun()` on selection change.

**Affects Phases**: 5, 6

---

#### Discovery 08: Test Pollution Prevention
**Impact**: High
**Sources**: [R1-08, PL-12]

Tests must use `autouse=True` fixtures to clear all `FS2_*` environment variables before each test. No module-level config loading.

**Affects Phases**: All (testing)

---

### High-Impact Discoveries

| # | Title | Impact | Key Insight |
|---|-------|--------|-------------|
| 09 | Web Service Composition | High | Web services are composition wrappers, not replacements |
| 10 | Streamlit Page Organization | High | Numbered pages with sidebar navigation |
| 11 | Relative Path Resolution | Medium | Must preserve `_source_dir` context (PL-14) |
| 12 | REPO vs Standalone Detection | Medium | Check for sibling `config.yaml` |

---

## Testing Philosophy

### Testing Approach
**Selected Approach**: Full TDD
**Rationale**: Security-critical features (secret handling), config backup reliability, and service integration require comprehensive test coverage with tests written before implementation.

### Test-Driven Development

For each feature:
1. **RED**: Write comprehensive tests that fail
2. **GREEN**: Implement minimal code to pass tests
3. **REFACTOR**: Improve code quality while keeping tests green

### Mock Usage: Targeted Fakes

Continue fs2's established Fake adapter pattern:
- `FakeConfigInspectorService` - for UI testing without real files
- `FakeConfigBackupService` - for testing save flows
- `FakeTestConnectionService` - for testing wizard flows

All fakes follow pattern:
```python
class FakeConfigInspectorService:
    def __init__(self, user_raw: dict = None, ...):
        self._user_raw = user_raw or {}
        self.call_history: list[str] = []
        self.simulate_error: Exception | None = None

    def reset(self) -> None:
        self.call_history.clear()
        self.simulate_error = None
```

### Test File Organization

```
tests/
├── unit/
│   └── web/
│       ├── services/
│       │   ├── test_config_inspector.py
│       │   ├── test_config_backup.py
│       │   └── test_connection_tester.py
│       └── components/
│           ├── test_doctor_panel.py
│           └── test_wizard_steps.py
└── integration/
    └── web/
        ├── test_wizard_flow.py
        └── test_config_editor_flow.py
```

---

## Implementation Phases

### Phase 1: Foundation

**Objective**: Create core infrastructure including read-only config inspection, backup service, CLI command, and Streamlit skeleton.

**Deliverables**:
- `src/fs2/web/` directory structure
- ConfigInspectorService with source attribution
- ConfigBackupService with atomic operations
- `fs2 web` CLI command
- Basic Streamlit app.py skeleton
- All service fakes for testing

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ConfigInspectorService accidentally mutates os.environ | Medium | Critical | Unit test verifies environ unchanged |
| Import of load_secrets_to_env | Low | Critical | Static analysis in CI |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 1.1 | [x] | Write tests for ConfigInspectorService | 2 | Tests cover: read-only behavior, source attribution, placeholder detection, secret masking | [📋](tasks/phase-1-foundation/execution.log.md#task-t002-write-configinspectorservice-tests-red-phase) | T002 · 22 tests [^1] |
| 1.2 | [x] | Implement ConfigInspectorService | 3 | All tests from 1.1 pass, uses dotenv_values() only | [📋](tasks/phase-1-foundation/execution.log.md#task-t003-implement-configinspectorservice) | T003 · [^2] |
| 1.3 | [x] | Write tests for ConfigBackupService | 2 | Tests cover: atomic backup, integrity verification, permission errors | [📋](tasks/phase-1-foundation/execution.log.md#task-t004-write-configbackupservice-tests-red-phase) | T004 · 19 tests [^3] |
| 1.4 | [x] | Implement ConfigBackupService | 2 | All tests from 1.3 pass | [📋](tasks/phase-1-foundation/execution.log.md#task-t005-implement-configbackupservice) | T005 · [^4] |
| 1.5 | [x] | Write tests for FakeConfigInspectorService | 1 | Fake follows call_history/simulate_error pattern | [📋](tasks/phase-1-foundation/execution.log.md#tasks-t007-t010-fake-services) | T007 · 10 tests [^5] |
| 1.6 | [x] | Implement FakeConfigInspectorService | 1 | Fake usable in subsequent phase tests | [📋](tasks/phase-1-foundation/execution.log.md#tasks-t007-t010-fake-services) | T008 · [^5] |
| 1.7 | [x] | Write tests for FakeConfigBackupService | 1 | Fake tracks backup operations | [📋](tasks/phase-1-foundation/execution.log.md#tasks-t007-t010-fake-services) | T009 · 12 tests [^6] |
| 1.8 | [x] | Implement FakeConfigBackupService | 1 | Fake usable in subsequent phase tests | [📋](tasks/phase-1-foundation/execution.log.md#tasks-t007-t010-fake-services) | T010 · [^6] |
| 1.9 | [x] | Create directory structure | 1 | src/fs2/web/{app.py,pages/,components/,services/} exists | [📋](tasks/phase-1-foundation/execution.log.md#task-t001-create-web-module-directory-structure) | T001 · [^7] |
| 1.10 | [x] | Write tests for CLI command | 1 | Tests cover: port option, host option, no-browser flag | [📋](tasks/phase-1-foundation/execution.log.md#tasks-t011-t013-cli-and-streamlit) | T011 · 9 tests [^8] |
| 1.11 | [x] | Implement `fs2 web` CLI command | 2 | CLI launches Streamlit, all tests pass | [📋](tasks/phase-1-foundation/execution.log.md#tasks-t011-t013-cli-and-streamlit) | T012 · [^8] |
| 1.12 | [x] | Create Streamlit app.py skeleton | 2 | App loads, shows sidebar, has page routing | [📋](tasks/phase-1-foundation/execution.log.md#tasks-t011-t013-cli-and-streamlit) | T013 · [^9] |
| 1.13 | [x] | Add UIConfig to config objects | 1 | UIConfig with port, host, theme fields | [📋](tasks/phase-1-foundation/execution.log.md#task-t006-add-uiconfig-model-to-objectspy) | T006 · [^10] |

### Test Examples

```python
# tests/unit/web/services/test_config_inspector.py

import os
import pytest
from pathlib import Path
from fs2.web.services.config_inspector import ConfigInspectorService

class TestConfigInspectorReadOnly:
    """
    Purpose: Proves ConfigInspectorService never modifies os.environ
    Quality Contribution: Prevents PL-01 violation (global state mutation)
    Acceptance Criteria: AC-16
    """

    def test_inspect_does_not_mutate_environ(self, tmp_path, monkeypatch):
        """Verify os.environ unchanged after inspection."""
        # Arrange
        original_env = os.environ.copy()
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  provider: azure")

        # Act
        inspector = ConfigInspectorService(project_path=config_file)
        inspector.inspect()

        # Assert
        assert os.environ == original_env

    def test_source_attribution_tracks_override(self, tmp_path):
        """Verify source attribution when project overrides user config."""
        # Arrange
        user_config = tmp_path / "user" / "config.yaml"
        user_config.parent.mkdir()
        user_config.write_text("llm:\n  timeout: 30")

        project_config = tmp_path / "project" / "config.yaml"
        project_config.parent.mkdir()
        project_config.write_text("llm:\n  timeout: 60")

        # Act
        inspector = ConfigInspectorService(
            user_path=user_config,
            project_path=project_config,
        )
        result = inspector.inspect()

        # Assert
        assert result.attribution["llm.timeout"].value == 60
        assert result.attribution["llm.timeout"].source == "project"
        assert result.attribution["llm.timeout"].override_chain == [("user", 30)]
```

### Non-Happy-Path Coverage
- [ ] Missing config files handled gracefully
- [ ] Invalid YAML returns validation errors
- [ ] Permission denied on backup directory
- [ ] Disk full during backup creation

### Acceptance Criteria
- [ ] All tests passing (13 tasks)
- [ ] ConfigInspectorService never imports load_secrets_to_env
- [ ] Test coverage > 80% for new code
- [ ] os.environ unchanged after all operations (verified by test)

### Commands to Run

```bash
# Run phase tests
pytest tests/unit/web/services/test_config_inspector.py tests/unit/web/services/test_config_backup.py -v

# Check linting
ruff check src/fs2/web/ src/fs2/cli/web.py

# Verify coverage
pytest tests/unit/web/ --cov=src/fs2/web --cov-report=term-missing --cov-fail-under=80

# Verify no forbidden imports
grep -r "load_secrets_to_env" src/fs2/web/ && echo "FAIL: Forbidden import found" || echo "PASS: No forbidden imports"

# Test CLI command
fs2 web --help
```

---

### Phase 2: Diagnostics Integration

**Objective**: Create shared validation module, refactor doctor.py to use it, then build web DoctorPanel component showing config health.

**Deliverables**:
- **Shared validation module** (`src/fs2/core/validation/`) - single source of truth
- **Refactored doctor.py** - imports from shared module (prevents drift)
- ValidationService for web (thin wrapper over shared module)
- DoctorPanel component for persistent health display
- HealthBadge component for sidebar
- Dashboard page with health overview and quick actions

**Dependencies**: Phase 1 complete (ConfigInspectorService required)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| doctor.py refactor breaks CLI | Medium | High | Extract-and-Verify pattern (baseline tests before/after) |
| Session state conflicts | Low | Low | Namespaced keys (`fs2_web_health_*`) |

> **Scope Note**: Phase 2 expanded from 7 to 12 tasks per Critical Insights session (2026-01-15). Shared validation module prevents CLI/Web drift—see [tasks.md](tasks/phase-2-diagnostics-integration/tasks.md) for full rationale.

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 2.1 | [x] | Write tests for shared validation module | 2 | Tests cover: LLM/embedding validation, placeholders, secrets | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t001) | Completed [^11] |
| 2.2 | [x] | Create shared validation module | 3 | Pure functions in `src/fs2/core/validation/` | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t002) | Completed [^11] |
| 2.3 | [x] | Refactor doctor.py to use shared module | 2 | Existing doctor tests pass unchanged | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t003) | Completed [^12] |
| 2.4 | [x] | Write tests for ValidationService | 2 | Composition with ConfigInspectorService | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t004) | Completed [^13] |
| 2.5 | [x] | Implement ValidationService | 2 | Thin wrapper over shared module | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t005) | Completed [^13] |
| 2.6 | [x] | Write tests for FakeValidationService | 1 | call_history/simulate_error pattern | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t006) | Completed [^13] |
| 2.7 | [x] | Implement FakeValidationService | 1 | Usable in component tests | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t007) | Completed [^13] |
| 2.8 | [x] | Write tests for DoctorPanel | 1 | Service integration tests only | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t008) | Completed [^14] |
| 2.9 | [x] | Implement DoctorPanel component | 2 | Renders health status | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t009) | Completed [^14] |
| 2.10 | [x] | Write tests for HealthBadge | 1 | Data flow tests only | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t010) | Completed [^14] |
| 2.11 | [x] | Implement HealthBadge | 1 | Sidebar badge | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t011) | Completed [^14] |
| 2.12 | [x] | Create Dashboard page | 2 | Health overview + quick actions | [📋](tasks/phase-2-diagnostics-integration/execution.log.md#task-t012) | Completed [^15] |

### Acceptance Criteria
- [x] All tests passing (12 tasks)
- [x] AC-06: Doctor panel shows health status with actionable fix suggestions
- [x] Shared validation module used by both CLI and Web (no duplication)
- [x] Existing `fs2 doctor` tests pass after refactor

### Commands to Run

```bash
# Shared validation module
pytest tests/unit/core/validation/test_config_validator.py -v

# doctor.py refactor verification
pytest tests/unit/cli/test_doctor.py -v

# Web services and components
pytest tests/unit/web/services/test_validation.py tests/unit/web/components/test_doctor_panel.py -v

# Full phase verification
pytest tests/unit/core/validation/ tests/unit/web/ tests/unit/cli/test_doctor.py -v
```

---

### Phase 3: Configuration Editor

**Objective**: Create YAML configuration editor with source attribution display, validation feedback, and save-with-backup functionality.

**Deliverables**:
- Configuration page with YAML editor
- Source attribution badges showing value origins
- Placeholder state display (resolved/unresolved/missing)
- Save button with backup integration
- File path indicator showing which file is being edited

**Dependencies**: Phase 1 complete (ConfigInspectorService, ConfigBackupService)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| User edits wrong config file | Medium | Medium | Show file path prominently, require confirmation |
| Backup fails before save | Low | High | Abort save if backup fails |
| Secrets displayed unmasked | Low | Critical | All secret fields use mask_secret() |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 3.1 | [ ] | Write tests for source badge component | 1 | Tests cover: user/project/env/default sources | - | |
| 3.2 | [ ] | Implement source badge component | 1 | Badge shows source with appropriate color | - | components/source_badge.py |
| 3.3 | [ ] | Write tests for placeholder state display | 2 | Tests cover: resolved, unresolved, literal states | - | |
| 3.4 | [ ] | Implement placeholder state display | 2 | Three states render with correct icons/colors | - | |
| 3.5 | [ ] | Write tests for secret masking in editor | 2 | Tests verify secrets show as [SET], placeholders shown | - | AC-15 |
| 3.6 | [ ] | Implement secret masking in editor | 2 | All api_key fields masked, validation passes | - | |
| 3.7 | [ ] | Write tests for config editor component | 2 | Tests cover: load, display, edit, validate | - | |
| 3.8 | [ ] | Implement config editor component | 3 | Editor displays YAML with attribution | - | components/config_editor.py |
| 3.9 | [ ] | Write tests for save-with-backup flow | 2 | Tests cover: successful save, backup failure, invalid YAML | - | AC-05 |
| 3.10 | [ ] | Implement save-with-backup flow | 2 | Save creates backup first, handles errors | - | |
| 3.11 | [ ] | Create Configuration page | 2 | Page integrates all components | - | pages/2_Configuration.py |

### Acceptance Criteria
- [ ] All tests passing (11 tasks)
- [ ] AC-02: Each field shows value AND source file
- [ ] AC-03: Placeholder states show resolved/unresolved/missing
- [ ] AC-05: Backup created before save
- [ ] AC-15: Secrets masked as [SET]

### Commands to Run

```bash
# Run phase tests
pytest tests/unit/web/components/test_config_editor.py tests/unit/web/components/test_source_badge.py -v

# Check linting
ruff check src/fs2/web/components/config_editor.py src/fs2/web/components/source_badge.py src/fs2/web/pages/2_Configuration.py

# Security audit: verify no raw secrets in test output
pytest tests/unit/web/components/test_config_editor.py -v 2>&1 | grep -i "sk-\|api_key.*=" && echo "FAIL: Secrets in output" || echo "PASS"

# Verify coverage for phase
pytest tests/unit/web/ --cov=src/fs2/web --cov-report=term-missing --cov-fail-under=80
```

---

### Phase 4: Setup Wizards

**Objective**: Create step-by-step setup wizards for Azure LLM, OpenAI, and fake providers with connection testing.

**Deliverables**:
- Wizard component with step navigation
- Azure LLM wizard (6 fields)
- OpenAI wizard (4 fields)
- Fake provider wizard (minimal config)
- Test Connection buttons with latency display
- TestConnectionService for provider validation

**Dependencies**: Phase 1, Phase 3 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Wizard saves invalid config | Low | Medium | Validate before save, show preview |
| Connection test exposes secrets | Low | Critical | Never log request/response bodies |
| Test connection hangs indefinitely | Medium | Low | Timeout with user feedback |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 4.1 | [ ] | Write tests for TestConnectionService | 2 | Tests cover: success, auth failure, timeout, network error | - | |
| 4.2 | [ ] | Implement TestConnectionService | 3 | Service tests LLM and embedding providers | - | services/test_connection.py |
| 4.3 | [ ] | Write tests for FakeTestConnectionService | 1 | Fake allows configurable results | - | |
| 4.4 | [ ] | Implement FakeTestConnectionService | 1 | Fake usable in wizard tests | - | |
| 4.5 | [ ] | Write tests for wizard step component | 2 | Tests cover: step navigation, validation, completion | - | |
| 4.6 | [ ] | Implement wizard step component | 2 | Reusable multi-step wizard UI | - | components/wizard_steps.py |
| 4.7 | [ ] | Write tests for Azure LLM wizard | 2 | Tests cover: all fields, validation, config generation | - | AC-01 |
| 4.8 | [ ] | Implement Azure LLM wizard | 3 | Wizard generates valid llm: config | - | |
| 4.9 | [ ] | Write tests for OpenAI wizard | 2 | Tests cover: API key, model selection | - | |
| 4.10 | [ ] | Implement OpenAI wizard | 2 | Wizard generates valid config | - | |
| 4.11 | [ ] | Write tests for Fake provider wizard | 1 | Minimal config for dev/CI | - | |
| 4.12 | [ ] | Implement Fake provider wizard | 1 | Enables testing without API keys | - | |
| 4.13 | [ ] | Create Setup Wizard page with tabs | 2 | Page has tabs for each provider type | - | pages/3_Setup_Wizard.py |

### Acceptance Criteria
- [ ] All tests passing (13 tasks)
- [ ] AC-01: Azure wizard creates valid config with ${} placeholders
- [ ] AC-04: Test Connection shows success/failure with latency
- [ ] Fake provider wizard enables dev/CI testing

### Commands to Run

```bash
# Run phase tests
pytest tests/unit/web/services/test_connection_tester.py tests/unit/web/components/test_wizard_steps.py -v

# Check linting
ruff check src/fs2/web/services/test_connection.py src/fs2/web/components/wizard_steps.py src/fs2/web/pages/3_Setup_Wizard.py

# Test connection timeout handling (should complete within 35 seconds)
timeout 35 pytest tests/unit/web/services/test_connection_tester.py::test_timeout_handling -v

# Verify coverage for phase
pytest tests/unit/web/ --cov=src/fs2/web --cov-report=term-missing --cov-fail-under=80

# Integration test: wizard flow
pytest tests/integration/web/test_wizard_flow.py -v
```

---

### Phase 5: Graph Management

**Objective**: Create graph list display, add existing repo flow, initialize new repo flow, and repo config editing.

**Deliverables**:
- Graphs page with list of all graphs
- Availability status (exists / not found)
- REPO vs standalone detection
- Add existing repo flow (validates .fs2 exists)
- Initialize new repo flow (runs fs2 init)
- Scan trigger with progress display

**Dependencies**: Phase 1 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Relative path resolution incorrect | Medium | Medium | Always show resolved absolute path |
| Init in wrong directory | Low | Medium | Require confirmation with path display |
| Scan hangs with no feedback | Medium | Low | Progress display, timeout |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Write tests for graph list service | 2 | Tests cover: list graphs, availability check, REPO detection | - | |
| 5.2 | [ ] | Implement graph list wrapper | 2 | Wraps GraphService.list_graphs() with UI metadata | - | |
| 5.3 | [ ] | Write tests for REPO vs standalone detection | 1 | Tests cover: has sibling config.yaml, standalone pickle | - | AC-08 |
| 5.4 | [ ] | Implement REPO detection | 1 | Detection based on path sibling check | - | |
| 5.5 | [ ] | Write tests for graph card component | 2 | Tests cover: name, path, description, status badge | - | |
| 5.6 | [ ] | Implement graph card component | 2 | Card displays graph info with status | - | components/graph_card.py |
| 5.7 | [ ] | Write tests for add repo flow | 2 | Tests cover: path validation, .fs2 check, config update | - | AC-09 |
| 5.8 | [ ] | Implement add repo flow | 2 | Flow validates path, adds to other_graphs | - | |
| 5.9 | [ ] | Write tests for init repo flow | 2 | Tests cover: fs2 init subprocess, success/failure | - | AC-10 |
| 5.10 | [ ] | Implement init repo flow | 2 | Flow runs fs2 init, adds new graph | - | |
| 5.11 | [ ] | Write tests for scan trigger | 2 | Tests cover: progress display, completion, error handling | - | AC-17, AC-18 |
| 5.12 | [ ] | Implement scan trigger | 2 | Button triggers scan with progress | - | |
| 5.13 | [ ] | Create Graphs page | 2 | Page integrates all graph management | - | pages/4_Graphs.py |

### Acceptance Criteria
- [ ] All tests passing (13 tasks)
- [ ] AC-07: All graphs show with availability status
- [ ] AC-08: REPO graphs show edit config option
- [ ] AC-09: Add existing repo validates .fs2
- [ ] AC-10: Init new repo runs fs2 init
- [ ] AC-17, AC-18: Scan trigger with progress

### Commands to Run

```bash
# Run phase tests
pytest tests/unit/web/components/test_graph_card.py tests/unit/web/services/test_graph_list.py -v

# Check linting
ruff check src/fs2/web/components/graph_card.py src/fs2/web/pages/4_Graphs.py

# Test subprocess timeout (fs2 init should timeout gracefully at 30s)
timeout 35 pytest tests/unit/web/test_init_repo_flow.py::test_init_timeout -v

# Verify coverage for phase
pytest tests/unit/web/ --cov=src/fs2/web --cov-report=term-missing --cov-fail-under=80

# Integration test: add repo flow with real filesystem
pytest tests/integration/web/test_add_repo_flow.py -v
```

---

### Phase 6: Exploration

**Objective**: Create global graph selector, tree browser, search interface, and node inspector for code exploration.

**Deliverables**:
- Global graph selector in sidebar (persists across pages)
- Tree browser with pattern filtering
- Search interface (text, regex, semantic modes)
- Node inspector with syntax highlighting
- Integrated browse + search workflow

**Dependencies**: Phase 5 complete (graph management)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Large graph causes UI lag | Medium | Medium | Pagination, lazy loading |
| Semantic search without embeddings | Low | Low | Hide semantic mode if no embeddings |
| Session state graph selector conflicts | Low | Medium | Namespaced session keys |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 6.1 | [ ] | Write tests for graph selector component | 2 | Tests cover: selection persistence, rerun on change, unavailable handling | - | AC-19, AC-20 |
| 6.2 | [ ] | Implement graph selector component | 2 | Dropdown persists selection across pages | - | components/graph_selector.py |
| 6.3 | [ ] | Write tests for tree view component | 2 | Tests cover: expand/collapse, pattern filter, node selection | - | |
| 6.4 | [ ] | Implement tree view component | 3 | Tree renders with expand/collapse | - | components/tree_view.py |
| 6.5 | [ ] | Write tests for search filter integration | 2 | Tests cover: search filters tree, clear restores | - | AC-21 |
| 6.6 | [ ] | Implement search filter integration | 2 | Search box filters tree view | - | |
| 6.7 | [ ] | Write tests for search results component | 2 | Tests cover: text/regex/semantic results, scores | - | |
| 6.8 | [ ] | Implement search results component | 2 | Results display with mode-appropriate info | - | components/search_results.py |
| 6.9 | [ ] | Write tests for node inspector component | 2 | Tests cover: syntax highlighting, metadata display | - | AC-12 |
| 6.10 | [ ] | Implement node inspector component | 2 | Code displays with highlighting | - | components/node_viewer.py |
| 6.11 | [ ] | Write tests for node expansion from search | 2 | Tests cover: click result, show in tree, expand children | - | AC-22 |
| 6.12 | [ ] | Implement node expansion workflow | 2 | Click search result shows in tree context | - | |
| 6.13 | [ ] | Create Explore page | 3 | Page combines tree, search, inspector | - | pages/5_Explore.py |

### Acceptance Criteria
- [ ] All tests passing (13 tasks)
- [ ] AC-11: Semantic search only if embeddings exist
- [ ] AC-12: Node inspector shows syntax highlighting
- [ ] AC-19: Global selector on all exploration pages
- [ ] AC-20: Selection persists across navigation
- [ ] AC-21: Search filters tree
- [ ] AC-22: Click result continues browsing

### Commands to Run

```bash
# Run phase tests
pytest tests/unit/web/components/test_graph_selector.py tests/unit/web/components/test_tree_view.py tests/unit/web/components/test_node_viewer.py -v

# Check linting
ruff check src/fs2/web/components/graph_selector.py src/fs2/web/components/tree_view.py src/fs2/web/pages/5_Explore.py

# Test session state isolation
pytest tests/unit/web/components/test_graph_selector.py::test_session_isolation -v

# Verify coverage for phase
pytest tests/unit/web/ --cov=src/fs2/web --cov-report=term-missing --cov-fail-under=80

# Integration test: browse + search workflow
pytest tests/integration/web/test_explore_workflow.py -v
```

---

### Phase 7: Polish & Documentation

**Objective**: Final polish including error handling improvements, help text, and user documentation.

**Deliverables**:
- Consistent error messages with fix suggestions
- Help text for all form fields
- README.md Web UI section
- docs/how/user/web-ui.md detailed guide
- Final test cleanup and coverage verification

**Dependencies**: All previous phases complete

### Tasks (Lightweight Approach for Documentation)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 7.1 | [ ] | Audit error messages for consistency | 1 | All errors follow "Problem → Cause → Fix" pattern | - | |
| 7.2 | [ ] | Add help text to all form fields | 2 | Fields show descriptions from config docs | - | |
| 7.3 | [ ] | Survey existing docs/how/ directories | 1 | Documented structure, identified placement | - | |
| 7.4 | [ ] | Update README.md with Web UI section | 2 | Getting started, basic usage, link to guide | - | |
| 7.5 | [ ] | Create docs/how/user/web-ui.md | 3 | Comprehensive guide with all features | - | |
| 7.6 | [ ] | Run full test suite, verify coverage | 1 | All tests pass, >80% coverage | - | |
| 7.7 | [ ] | Final security audit for secret exposure | 1 | No secrets in logs, session state, or UI | - | |

### Acceptance Criteria
- [ ] All tests passing
- [ ] Documentation complete (README + docs/how/)
- [ ] No secret exposure in any code path

### Commands to Run

```bash
# Run full test suite with coverage
pytest tests/unit/web/ tests/integration/web/ --cov=src/fs2/web --cov-report=term-missing --cov-report=html --cov-fail-under=80

# Check all linting
ruff check src/fs2/web/ src/fs2/cli/web.py

# Final security audit: no secrets in any output
pytest tests/ -v 2>&1 | grep -iE "sk-[a-zA-Z0-9]{20,}|api_key\s*=\s*['\"][^$]" && echo "FAIL: Secrets found" || echo "PASS: No secrets"

# Verify documentation links work
python -c "import fs2.web; print('Web module imports successfully')"

# Verify all pages load without error
python -c "
import streamlit as st
st.set_page_config(page_title='Test')
from fs2.web.pages import _1_Dashboard, _2_Configuration, _3_Setup_Wizard, _4_Graphs, _5_Explore
print('All pages import successfully')
"

# Check docs exist
test -f README.md && grep -q "fs2 web" README.md && echo "README updated" || echo "README missing web section"
test -f docs/how/user/web-ui.md && echo "Guide exists" || echo "Guide missing"
```

---

## Cross-Cutting Concerns

### Security Considerations

| Concern | Mitigation |
|---------|------------|
| Secret exposure in logs | SecretSanitizingFilter on all loggers |
| Secret exposure in UI | mask_secret() on all api_key fields |
| Secret in session state | Store only `is_set: bool`, not actual value |
| Secret in browser history | Use POST, not GET; password input type |

### Observability

| Aspect | Implementation |
|--------|---------------|
| Logging | Structured logging with request ID |
| Error tracking | Rich error messages with fix suggestions |
| Performance | Session-scoped caching with TTL |

### Documentation

| Location | Content |
|----------|---------|
| README.md | Quick start, `fs2 web` command, link to guide |
| docs/how/user/web-ui.md | Full guide with screenshots |

---

## Complexity Tracking

| Component | CS | Label | Breakdown | Justification | Mitigation |
|-----------|-----|-------|-----------|---------------|------------|
| ConfigInspectorService | 3 | Medium | S=1,I=1,D=1,N=1,F=1,T=1 | Read-only config with attribution | Thorough unit tests |
| Setup Wizards | 3 | Medium | S=1,I=1,D=1,N=1,F=0,T=2 | New UX pattern | Reference existing wizard patterns |
| Tree Browser + Search | 3 | Medium | S=1,I=1,D=1,N=1,F=0,T=2 | UI state complexity | Session state isolation |
| Overall Feature | 4 | Large | See spec | First web UI | Phased rollout, comprehensive testing |

---

## Progress Tracking

### Phase Completion Checklist

- [x] Phase 1: Foundation - COMPLETE (72 tests, 2026-01-15)
- [x] Phase 2: Diagnostics Integration - COMPLETE (12/12 tasks, 2026-01-16)
- [ ] Phase 3: Configuration Editor - NOT STARTED
- [ ] Phase 4: Setup Wizards - NOT STARTED
- [ ] Phase 5: Graph Management - NOT STARTED
- [~] Phase 6: Exploration - IN PROGRESS (12/17 tasks, 2026-01-16) ← Pulled forward
- [ ] Phase 7: Polish & Documentation - NOT STARTED

**Note**: Phase 6 (Exploration) was implemented before Phases 3-5 to enable "verify before configure" workflow.

### STOP Rule

**IMPORTANT**: This plan has been validated and is READY for implementation.

**Validation Status**: ✅ READY (2026-01-15)
- Structure: PASS
- Testing: PASS
- Completeness: PASS (commands added to all phases)
- Doctrine: PASS (minor items accepted)
- ADR: N/A (no ADRs exist)

**Next Step**: Run `/plan-5-phase-tasks-and-brief` for Phase 1 to begin implementation.

---

## Change Footnotes Ledger

**NOTE**: This section is populated during implementation by plan-6a-update-progress.

**Footnote Numbering Authority**: plan-6a-update-progress is the **single source of truth** for footnote numbering across the entire plan.

### Phase 1: Foundation (2026-01-15)

[^1]: Task 1.1 (T002) - ConfigInspectorService tests (22 tests)
  - `file:tests/unit/web/services/test_config_inspector.py`

[^2]: Task 1.2 (T003) - ConfigInspectorService implementation
  - `type:src/fs2/web/services/config_inspector.py:PlaceholderState`
  - `type:src/fs2/web/services/config_inspector.py:ConfigValue`
  - `type:src/fs2/web/services/config_inspector.py:InspectionResult`
  - `type:src/fs2/web/services/config_inspector.py:ConfigInspectorService`
  - `callable:src/fs2/web/services/config_inspector.py:ConfigInspectorService.inspect`
  - `callable:src/fs2/web/services/config_inspector.py:_is_secret_field`
  - `callable:src/fs2/web/services/config_inspector.py:_load_yaml_safe`
  - `callable:src/fs2/web/services/config_inspector.py:_flatten_dict`
  - `callable:src/fs2/web/services/config_inspector.py:_deep_merge`

[^3]: Task 1.3 (T004) - ConfigBackupService tests (19 tests)
  - `file:tests/unit/web/services/test_config_backup.py`

[^4]: Task 1.4 (T005) - ConfigBackupService implementation
  - `type:src/fs2/web/services/config_backup.py:BackupResult`
  - `type:src/fs2/web/services/config_backup.py:ConfigBackupService`
  - `callable:src/fs2/web/services/config_backup.py:ConfigBackupService.backup`

[^5]: Tasks 1.5-1.6 (T007-T008) - FakeConfigInspectorService
  - `file:tests/unit/web/services/test_config_inspector_fake.py`
  - `type:src/fs2/web/services/config_inspector_fake.py:FakeConfigInspectorService`
  - `callable:src/fs2/web/services/config_inspector_fake.py:FakeConfigInspectorService.inspect`

[^6]: Tasks 1.7-1.8 (T009-T010) - FakeConfigBackupService
  - `file:tests/unit/web/services/test_config_backup_fake.py`
  - `type:src/fs2/web/services/config_backup_fake.py:FakeConfigBackupService`
  - `callable:src/fs2/web/services/config_backup_fake.py:FakeConfigBackupService.backup`

[^7]: Task 1.9 (T001) - Directory structure
  - `file:src/fs2/web/__init__.py`
  - `file:src/fs2/web/services/__init__.py`
  - `file:src/fs2/web/pages/__init__.py`
  - `file:src/fs2/web/components/__init__.py`
  - `file:tests/unit/web/__init__.py`
  - `file:tests/unit/web/services/__init__.py`
  - `file:tests/unit/web/services/conftest.py`

[^8]: Tasks 1.10-1.11 (T011-T012) - CLI command
  - `file:tests/unit/cli/test_web_cli.py`
  - `file:src/fs2/cli/web.py`

[^9]: Task 1.12 (T013) - Streamlit app skeleton
  - `file:src/fs2/web/app.py`
  - `callable:src/fs2/web/app.py:main`
  - `callable:src/fs2/web/app.py:_render_dashboard`
  - `callable:src/fs2/web/app.py:_render_configuration`
  - `callable:src/fs2/web/app.py:_render_graph_browser`
  - `callable:src/fs2/web/app.py:_render_doctor`

[^10]: Task 1.13 (T006) - UIConfig model
  - `type:src/fs2/config/objects.py:UIConfig`
  - `callable:src/fs2/config/objects.py:UIConfig.validate_port`

### Phase 2: Diagnostics Integration (2026-01-16)

[^11]: Phase 2 T001-T002 - Shared validation module
  - `file:src/fs2/core/validation/__init__.py`
  - `file:src/fs2/core/validation/config_validator.py`
  - `file:src/fs2/core/validation/constants.py`

[^12]: Phase 2 T003 - doctor.py refactored to use shared module
  - `file:src/fs2/cli/doctor.py`

[^13]: Phase 2 T004-T007 - ValidationService and FakeValidationService
  - `file:src/fs2/web/services/validation.py`
  - `file:src/fs2/web/services/validation_fake.py`

[^14]: Phase 2 T008-T011 - DoctorPanel and HealthBadge components
  - `file:src/fs2/web/components/__init__.py`
  - `file:src/fs2/web/components/doctor_panel.py`
  - `file:src/fs2/web/components/health_badge.py`

[^15]: Phase 2 T012 - Dashboard page
  - `file:src/fs2/web/pages/1_Dashboard.py`

### Phase 6: Exploration (2026-01-16)

[^16]: Phase 6 T001 - GraphSelector tests (11 tests)
  - `file:tests/unit/web/components/test_graph_selector.py`

[^17]: Phase 6 T002 - GraphSelector component
  - `class:src/fs2/web/components/graph_selector.py:GraphSelector`
  - `method:src/fs2/web/components/graph_selector.py:GraphSelector.render`
  - `method:src/fs2/web/components/graph_selector.py:GraphSelector.get_graph_options`

[^18]: Phase 6 T003 - TreeView tests (13 tests)
  - `file:tests/unit/web/components/test_tree_view.py`

[^19]: Phase 6 T004 - TreeView component
  - `class:src/fs2/web/components/tree_view.py:TreeView`
  - `method:src/fs2/web/components/tree_view.py:TreeView.render`
  - `method:src/fs2/web/components/tree_view.py:TreeView.get_display_nodes`

[^20]: Phase 6 T005 - SearchPanel tests (14 tests)
  - `file:tests/unit/web/components/test_search_panel.py`

[^21]: Phase 6 T006 - SearchPanel component
  - `class:src/fs2/web/components/search_panel.py:SearchPanel`
  - `class:src/fs2/web/components/search_panel.py:SearchPanelOutput`
  - `method:src/fs2/web/components/search_panel.py:SearchPanel.render`
  - `method:src/fs2/web/components/search_panel.py:SearchPanel.get_search_output`

[^22]: Phase 6 T009 - NodeInspector tests (9 tests)
  - `file:tests/unit/web/components/test_node_inspector.py`

[^23]: Phase 6 T010 - NodeInspector component
  - `class:src/fs2/web/components/node_inspector.py:NodeInspector`
  - `method:src/fs2/web/components/node_inspector.py:NodeInspector.render`
  - `method:src/fs2/web/components/node_inspector.py:NodeInspector.get_node_data`
  - `method:src/fs2/web/components/node_inspector.py:NodeInspector.get_language`

[^24]: Phase 6 T013 - Explore page
  - `file:src/fs2/web/pages/5_Explore.py`

[^25]: Phase 6 T014 - Web UI integration
  - `method:src/fs2/web/app.py:_render_explore`

[^26]: Phase 6 T016 - SearchPanelService tests (15 tests)
  - `file:tests/unit/web/services/test_search_panel_service.py`

[^27]: Phase 6 T017 - SearchPanelService + Fake
  - `class:src/fs2/web/services/search_panel_service.py:SearchPanelService`
  - `class:src/fs2/web/services/search_panel_service.py:SearchPanelResult`
  - `method:src/fs2/web/services/search_panel_service.py:SearchPanelService.search`
  - `class:src/fs2/web/services/search_panel_service_fake.py:FakeSearchPanelService`

---

## Appendix: Directory Structure

```
src/fs2/
├── web/                          # New web UI module
│   ├── __init__.py
│   ├── app.py                    # Streamlit main app
│   ├── pages/
│   │   ├── 1_Dashboard.py        # Health overview
│   │   ├── 2_Configuration.py    # YAML editor
│   │   ├── 3_Setup_Wizard.py     # Provider wizards
│   │   ├── 4_Graphs.py           # Graph management
│   │   └── 5_Explore.py          # Tree + Search + Inspector
│   ├── components/
│   │   ├── __init__.py
│   │   ├── doctor_panel.py       # Reusable health display
│   │   ├── config_editor.py      # YAML editor with validation
│   │   ├── source_badge.py       # Config source attribution
│   │   ├── graph_selector.py     # Global dropdown for sidebar
│   │   ├── graph_card.py         # Graph info display
│   │   ├── tree_view.py          # Expandable tree component
│   │   ├── search_results.py     # Search result cards
│   │   ├── node_viewer.py        # Code display with highlighting
│   │   └── wizard_steps.py       # Wizard step components
│   └── services/
│       ├── __init__.py           # Service providers
│       ├── config_inspector.py   # ConfigInspectorService
│       ├── config_backup.py      # ConfigBackupService
│       └── test_connection.py    # TestConnectionService
├── cli/
│   └── web.py                    # New `fs2 web` command
└── config/
    └── objects.py                # Add UIConfig model
```

---

**Plan Complete**: 2026-01-15
**Plan Validated**: 2026-01-15
**Status**: ✅ READY
**Total Phases**: 7
**Total Tasks**: 77
**Next Step**: Run `/plan-5-phase-tasks-and-brief` for Phase 1

---

## Subtasks Registry

Mid-implementation detours requiring structured tracking.

| ID | Created | Phase | Parent Task | Reason | Status | Dossier |
|----|---------|-------|-------------|--------|--------|---------|
| 001-subtask-virtual-folder-hierarchy | 2026-01-16 | Phase 6: Exploration | T004 | TreeView shows flat file nodes instead of virtual folder hierarchy like CLI | [ ] Pending | [Link](tasks/phase-6-exploration/001-subtask-virtual-folder-hierarchy.md) |
