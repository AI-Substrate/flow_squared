# fs2 Web UI Implementation Strategy

**Generated**: 2026-01-15
**Based On**: `research-dossier.md` and `web-spec.md`
**Purpose**: Implementation-focused discoveries for phased development

---

## Implementation Discoveries

### I1-01: Phase Structure and Dependency Chain

**Title**: Foundation-First Phase Breakdown
**Category**: Phase Design

**What**: The implementation must follow a strict dependency order where foundational services enable all subsequent work. The phases are not arbitrary - they follow the actual code dependency graph.

**Implementation Approach**:

```
Phase 1: Core Infrastructure (Blocking)
├── ConfigInspectorService (read-only, PL-01 compliant)
├── ConfigBackupService (backup-before-write pattern)
├── Directory structure (src/fs2/web/)
├── CLI command (fs2 web)
└── Streamlit skeleton (app.py)

Phase 2: Diagnostics Integration (Depends on Phase 1)
├── Port doctor.py validation functions (not import)
├── DoctorPanel component
└── Persistent health display

Phase 3: Configuration Editor (Depends on Phase 1, 2)
├── YAML editor with validation
├── Source attribution badges
└── Save with backup integration

Phase 4: Setup Wizards (Depends on Phase 1, 3)
├── Azure LLM wizard
├── OpenAI wizard
├── Fake provider wizard
└── TestConnectionService

Phase 5: Graph Management (Depends on Phase 1, 2)
├── Graph list with availability
├── REPO vs standalone detection
├── Add/init repository flows

Phase 6: Exploration (Depends on Phase 5)
├── Global graph selector
├── Tree browser
├── Search interface
└── Node inspector
```

**Dependencies**: None (this is the master plan)

**Affected ACs**: All (establishes implementation order)

---

### I1-02: Service Composition Architecture

**Title**: Web Services Wire to Existing Core Services
**Category**: Integration

**What**: Web services must compose with existing fs2 services without modification. The key insight is that web services are *consumers* of core services, not replacements.

**Implementation Approach**:

```python
# Web services are COMPOSITION WRAPPERS, not replacements

# Pattern: Web service wraps core services
class ConfigInspectorService:
    """Read-only inspection - NEVER calls load_secrets_to_env()."""

    def __init__(self) -> None:
        # Direct YAML loading, not FS2ConfigurationService
        # Per PL-01: Must not mutate os.environ
        pass

    def inspect(self) -> ConfigInspection:
        """Load and analyze without side effects."""
        # Use load_yaml_config() from loaders.py
        # Use dotenv_values() from python-dotenv (read-only)
        # Use parse_env_vars() pattern for FS2_* detection
        pass

# Pattern: Web service reuses GraphService directly
class WebGraphBrowser:
    """Thin wrapper for Streamlit display."""

    def __init__(self, graph_service: GraphService) -> None:
        self._graph_service = graph_service

    def list_available(self) -> list[GraphInfo]:
        return self._graph_service.list_graphs()

# Pattern: Validation logic extracted, not imported
# Per research: doctor.py functions should be copied/adapted, not imported
# because doctor imports FS2ConfigurationService which has side effects
```

**Service Dependency Map**:
```
ConfigInspectorService (NEW)
  └── loaders.py (REUSE: load_yaml_config, parse_env_vars patterns)
  └── paths.py (REUSE: get_user_config_dir, get_project_config_dir)
  └── dotenv_values() (REUSE: read-only env file inspection)

ConfigBackupService (NEW)
  └── Pure filesystem operations (no fs2 dependencies)

TestConnectionService (NEW)
  └── LLMAdapter factory (REUSE: create_llm_adapter_from_config pattern)
  └── EmbeddingAdapter factory (REUSE: create_embedding_adapter_from_config)
  └── FakeConfigurationService (REUSE: for isolated adapter creation)

WebGraphBrowser (NEW)
  └── GraphService (INJECT: existing service)
  └── TreeService (INJECT: existing service)
  └── SearchService (INJECT: existing service)
```

**Dependencies**: Phase 1 infrastructure
**Affected ACs**: AC-02, AC-04, AC-16

---

### I1-03: Read-Only Config Inspection Design

**Title**: ConfigInspectorService Must Be Side-Effect Free
**Category**: Architecture

**What**: The ConfigInspectorService is the most critical new service. It must provide full configuration visibility (merged values, source attribution, placeholder states) without ever calling `load_secrets_to_env()` or otherwise modifying global state.

**Implementation Approach**:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from dotenv import dotenv_values
import os

@dataclass
class ConfigValue:
    """A single config value with source tracking."""
    key: str
    value: Any
    source: str  # "user", "project", "env", "default"
    source_file: Path | None
    is_secret_field: bool
    placeholder_state: str  # "resolved" | "unresolved" | "none"
    masked_value: str  # For display: "[SET]" or actual value

@dataclass
class ConfigInspection:
    """Complete config inspection result."""
    user_raw: dict[str, Any]
    project_raw: dict[str, Any]
    env_vars: dict[str, str]  # FS2_* vars from os.environ
    env_files: dict[str, dict[str, str]]  # Read-only from .env files
    merged: dict[str, Any]
    attribution: dict[str, ConfigValue]  # key path -> source
    placeholders: list[PlaceholderInfo]
    validation_errors: list[ValidationError]

class ConfigInspectorService:
    """Read-only configuration inspection.

    CRITICAL: Never calls load_secrets_to_env().
    CRITICAL: Never modifies os.environ.
    """

    def inspect(self) -> ConfigInspection:
        # Phase 1: Load raw YAML (read-only)
        user_raw = self._load_yaml_readonly(get_user_config_dir() / "config.yaml")
        project_raw = self._load_yaml_readonly(get_project_config_dir() / "config.yaml")

        # Phase 2: Read env vars (snapshot, not modify)
        env_vars = {k: v for k, v in os.environ.items() if k.startswith("FS2_")}

        # Phase 3: Read env files (dotenv_values, not load_dotenv)
        env_files = self._read_env_files_readonly()

        # Phase 4: Compute merge (simulate, don't modify)
        merged = self._simulate_merge(user_raw, project_raw, env_vars)

        # Phase 5: Compute attribution (who wins each key)
        attribution = self._compute_attribution(user_raw, project_raw, env_vars)

        # Phase 6: Analyze placeholders
        placeholders = self._find_placeholders(merged, env_vars, env_files)

        # Phase 7: Validate without side effects
        validation_errors = self._validate_schema(merged)

        return ConfigInspection(...)

    def _read_env_files_readonly(self) -> dict[str, dict[str, str]]:
        """Read all env files without loading into os.environ."""
        files = {}
        for name, path in [
            ("user_secrets", get_user_config_dir() / "secrets.env"),
            ("project_secrets", get_project_config_dir() / "secrets.env"),
            ("dotenv", Path.cwd() / ".env"),
        ]:
            if path.exists():
                # dotenv_values() reads but doesn't modify os.environ
                files[name] = dotenv_values(path)
        return files
```

**Key Constraints**:
1. Never import `load_secrets_to_env` (to avoid accidental calls)
2. Use `dotenv_values()` not `load_dotenv()` for env file reading
3. Copy `os.environ` for inspection, don't modify
4. No singleton access to FS2ConfigurationService

**Dependencies**: Phase 1 infrastructure
**Affected ACs**: AC-02, AC-03, AC-15, AC-16

---

### I1-04: Testing Strategy with Targeted Fakes

**Title**: Fake-First Testing Following fs2 Patterns
**Category**: Testing

**What**: Continue the established fake adapter pattern. Create web-specific fakes that mirror the `{name}_adapter_fake.py` convention. Key fakes needed:
- FakeConfigInspectorService (for UI testing without real files)
- FakeConfigBackupService (for testing save flows)
- FakeTestConnectionService (for testing wizard flows)

**Implementation Approach**:

```python
# Follow existing fake pattern from fs2
# See: src/fs2/core/adapters/*_fake.py

class FakeConfigInspectorService:
    """Test double for ConfigInspectorService."""

    def __init__(
        self,
        user_raw: dict | None = None,
        project_raw: dict | None = None,
        env_vars: dict | None = None,
    ) -> None:
        self._user_raw = user_raw or {}
        self._project_raw = project_raw or {}
        self._env_vars = env_vars or {}
        self.call_history: list[str] = []
        self.simulate_error: Exception | None = None

    def inspect(self) -> ConfigInspection:
        self.call_history.append("inspect")
        if self.simulate_error:
            raise self.simulate_error
        return ConfigInspection(
            user_raw=self._user_raw,
            project_raw=self._project_raw,
            env_vars=self._env_vars,
            # ... computed fields
        )

    def reset(self) -> None:
        """Reset state for test isolation."""
        self.call_history.clear()
        self.simulate_error = None


class FakeConfigBackupService:
    """Test double for ConfigBackupService."""

    def __init__(self) -> None:
        self.backups: list[tuple[Path, Path]] = []  # (source, backup)
        self.call_history: list[str] = []

    def backup(self, config_path: Path) -> Path:
        self.call_history.append(f"backup:{config_path}")
        backup_path = Path(f"/fake/backup/{config_path.name}.bak")
        self.backups.append((config_path, backup_path))
        return backup_path


class FakeTestConnectionService:
    """Test double for connection testing."""

    def __init__(self) -> None:
        self._llm_result = ConnectionTestResult(success=True, latency_ms=100)
        self._embedding_result = ConnectionTestResult(success=True, latency_ms=50)

    def set_llm_result(self, result: ConnectionTestResult) -> None:
        self._llm_result = result

    async def test_llm(self, config: LLMConfig) -> ConnectionTestResult:
        return self._llm_result
```

**Test File Organization**:
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

**Dependencies**: Phase 1 service definitions
**Affected ACs**: AC-01 through AC-06 (testability)

---

### I1-05: Critical Path Analysis

**Title**: ConfigInspectorService Unblocks Everything
**Category**: Critical Path

**What**: The ConfigInspectorService is the critical-path item. Without it, no configuration display, no wizard validation, and no source attribution. This service must be implemented and tested first.

**Implementation Approach**:

```
Week 1: Critical Path (Parallel Work Possible)
├── [P1] ConfigInspectorService + FakeConfigInspectorService
├── [P1] ConfigBackupService + FakeConfigBackupService
├── [P1] Directory structure and CLI command
└── [P1] Basic Streamlit skeleton

Week 2: Doctor Integration (Depends on ConfigInspectorService)
├── [P2] Extract validation logic from doctor.py
├── [P2] DoctorPanel component
└── [P2] Dashboard page with health display

Week 3: Config Editor (Depends on Inspector + Backup)
├── [P3] YAML editor component
├── [P3] Source attribution badges
└── [P3] Save flow with backup

Week 4: Wizards (Depends on Editor + Connection Test)
├── [P4] TestConnectionService implementation
├── [P4] Azure LLM wizard
├── [P4] OpenAI wizard
└── [P4] Fake provider wizard

Week 5-6: Graph Management + Exploration
├── [P5] Graph list page
├── [P5] Add/init repository flows
├── [P6] Global graph selector
├── [P6] Tree browser and search
└── [P6] Node inspector
```

**Blocking Dependencies**:
```
ConfigInspectorService BLOCKS:
  ├── DoctorPanel (needs config analysis)
  ├── Source Attribution (needs merge chain)
  ├── Placeholder Display (needs resolution state)
  └── Wizard Validation (needs config state)

ConfigBackupService BLOCKS:
  └── Config Editor Save (AC-05 requirement)

TestConnectionService BLOCKS:
  └── Wizard Test Buttons (AC-04 requirement)

GraphService (existing) BLOCKS:
  └── All Exploration Features (AC-07 through AC-12)
```

**Dependencies**: None (this is the plan)
**Affected ACs**: All (establishes timeline)

---

### I1-06: Streamlit Page Organization

**Title**: Multi-Page App with Sidebar Navigation
**Category**: Architecture

**What**: Use Streamlit's native multi-page app pattern with numbered pages for ordering. The global graph selector lives in the sidebar and persists via session state.

**Implementation Approach**:

```
src/fs2/web/
├── app.py                      # Main entry point (sidebar + routing)
├── pages/
│   ├── 1_Dashboard.py          # Health overview, quick actions
│   ├── 2_Configuration.py      # YAML editor, source attribution
│   ├── 3_Setup_Wizard.py       # Provider wizards (tabbed)
│   ├── 4_Graphs.py             # Graph list, add/init repo
│   └── 5_Explore.py            # Tree + Search + Inspector (combined)
├── components/
│   ├── __init__.py
│   ├── doctor_panel.py         # Reusable health display
│   ├── config_editor.py        # YAML editor with validation
│   ├── source_badge.py         # "From: user config" badge
│   ├── graph_selector.py       # Global dropdown for sidebar
│   ├── tree_view.py            # Expandable tree component
│   ├── search_results.py       # Search result cards
│   └── node_viewer.py          # Code display with highlighting
└── services/
    ├── __init__.py
    ├── config_inspector.py     # ConfigInspectorService
    ├── config_backup.py        # ConfigBackupService
    └── test_connection.py      # TestConnectionService
```

**app.py Structure**:
```python
import streamlit as st

# Page config (must be first Streamlit call)
st.set_page_config(
    page_title="fs2 Hub",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar: Global graph selector (persists across pages)
from fs2.web.components.graph_selector import render_graph_selector

with st.sidebar:
    st.title("fs2 Hub")
    st.divider()

    # Graph selector for exploration pages
    render_graph_selector()

    st.divider()

    # Quick health indicator
    from fs2.web.components.doctor_panel import render_health_badge
    render_health_badge()

# Main content: Streamlit handles page routing automatically
# Each file in pages/ becomes a navigable page
```

**Page Numbering Rationale**:
- 1_Dashboard: Landing page, overview
- 2_Configuration: Core functionality, frequent access
- 3_Setup_Wizard: Onboarding, then less frequent
- 4_Graphs: Management, moderate frequency
- 5_Explore: Verification, after setup

**Dependencies**: Phase 1 infrastructure
**Affected ACs**: AC-13, AC-14 (CLI), AC-19, AC-20 (selector)

---

### I1-07: Session State Management for Global Graph Selector

**Title**: Graph Selection Persistence Across Pages
**Category**: Architecture

**What**: The global graph selector must persist user selection across page navigation. Streamlit session state is the mechanism, but it requires careful key management to avoid conflicts.

**Implementation Approach**:

```python
# components/graph_selector.py

import streamlit as st
from typing import Optional

# Use namespaced keys to avoid conflicts
SESSION_KEY_SELECTED_GRAPH = "fs2_web_selected_graph"
SESSION_KEY_AVAILABLE_GRAPHS = "fs2_web_available_graphs"

def get_selected_graph() -> str:
    """Get currently selected graph name."""
    return st.session_state.get(SESSION_KEY_SELECTED_GRAPH, "default")

def set_selected_graph(name: str) -> None:
    """Set selected graph and trigger refresh."""
    st.session_state[SESSION_KEY_SELECTED_GRAPH] = name

def render_graph_selector() -> Optional[str]:
    """Render graph selector dropdown in sidebar.

    Returns:
        Selected graph name, or None if no graphs available.
    """
    # Lazy-load graph list (cache in session state to avoid reload)
    if SESSION_KEY_AVAILABLE_GRAPHS not in st.session_state:
        from fs2.web.services.graph_lister import list_available_graphs
        st.session_state[SESSION_KEY_AVAILABLE_GRAPHS] = list_available_graphs()

    graphs = st.session_state[SESSION_KEY_AVAILABLE_GRAPHS]

    if not graphs:
        st.warning("No graphs available")
        return None

    # Build options with availability indicators
    options = []
    for g in graphs:
        status = "ready" if g.available else "not found"
        options.append(f"{g.name} ({status})")

    # Get current selection index
    current = get_selected_graph()
    current_idx = next(
        (i for i, g in enumerate(graphs) if g.name == current),
        0
    )

    # Render dropdown
    selected_idx = st.selectbox(
        "Active Graph",
        range(len(options)),
        format_func=lambda i: options[i],
        index=current_idx,
        key="graph_selector_dropdown",  # Unique widget key
    )

    # Update selection if changed
    new_selection = graphs[selected_idx].name
    if new_selection != current:
        set_selected_graph(new_selection)
        # Force page refresh to reload data
        st.rerun()

    return new_selection

def refresh_graph_list() -> None:
    """Force refresh of available graphs list."""
    if SESSION_KEY_AVAILABLE_GRAPHS in st.session_state:
        del st.session_state[SESSION_KEY_AVAILABLE_GRAPHS]
```

**Usage in Pages**:
```python
# pages/5_Explore.py

import streamlit as st
from fs2.web.components.graph_selector import get_selected_graph

def render_exploration():
    selected = get_selected_graph()

    # Load data for selected graph
    graph_service = get_graph_service()  # From dependencies
    try:
        store = graph_service.get_graph(selected)
    except GraphFileNotFoundError:
        st.error(f"Graph '{selected}' not found. Run scan first.")
        return

    # Render tree/search/inspector using store
    ...
```

**Key Design Decisions**:
1. Namespaced session keys (`fs2_web_*`) prevent conflicts
2. Graph list cached in session state (refreshed via button)
3. Selection change triggers `st.rerun()` for immediate update
4. Graceful handling of unavailable graphs

**Dependencies**: Phase 1 infrastructure, Phase 5 GraphService integration
**Affected ACs**: AC-19, AC-20

---

### I1-08: Web Service Wiring to Core Services

**Title**: Dependency Injection Pattern for Web Module
**Category**: Integration

**What**: Web services need access to core services (GraphService, TreeService, SearchService) without creating new instances each request. Use a provider pattern with lazy initialization.

**Implementation Approach**:

```python
# services/__init__.py

"""Web services with lazy initialization.

Per PL-06: Streamlit sessions are stateless per request.
Services are created fresh but can cache where appropriate.

Usage:
    from fs2.web.services import get_graph_service, get_config_inspector

    service = get_graph_service()
    graphs = service.list_graphs()
"""

import streamlit as st
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fs2.core.services.graph_service import GraphService
    from fs2.web.services.config_inspector import ConfigInspectorService
    from fs2.web.services.config_backup import ConfigBackupService

# Session-scoped service instances
_SERVICE_KEY_GRAPH = "fs2_web_service_graph"
_SERVICE_KEY_INSPECTOR = "fs2_web_service_inspector"
_SERVICE_KEY_BACKUP = "fs2_web_service_backup"


def get_graph_service() -> "GraphService":
    """Get or create GraphService for current session.

    Per PL-06: CLI gets fresh instances, but web sessions benefit
    from session-scoped caching for responsive UI.
    """
    if _SERVICE_KEY_GRAPH not in st.session_state:
        from fs2.config.service import FS2ConfigurationService
        from fs2.core.services.graph_service import GraphService

        # This DOES call load_secrets_to_env() but only for GraphService
        # ConfigInspectorService uses separate read-only path
        config = FS2ConfigurationService()
        st.session_state[_SERVICE_KEY_GRAPH] = GraphService(config)

    return st.session_state[_SERVICE_KEY_GRAPH]


def get_config_inspector() -> "ConfigInspectorService":
    """Get or create ConfigInspectorService.

    CRITICAL: This is the READ-ONLY inspector. It never calls
    load_secrets_to_env() and never modifies os.environ.
    """
    if _SERVICE_KEY_INSPECTOR not in st.session_state:
        from fs2.web.services.config_inspector import ConfigInspectorService
        st.session_state[_SERVICE_KEY_INSPECTOR] = ConfigInspectorService()

    return st.session_state[_SERVICE_KEY_INSPECTOR]


def get_backup_service() -> "ConfigBackupService":
    """Get or create ConfigBackupService."""
    if _SERVICE_KEY_BACKUP not in st.session_state:
        from fs2.web.services.config_backup import ConfigBackupService
        st.session_state[_SERVICE_KEY_BACKUP] = ConfigBackupService()

    return st.session_state[_SERVICE_KEY_BACKUP]


def clear_services() -> None:
    """Clear all cached services (for testing or refresh)."""
    for key in [_SERVICE_KEY_GRAPH, _SERVICE_KEY_INSPECTOR, _SERVICE_KEY_BACKUP]:
        if key in st.session_state:
            del st.session_state[key]
```

**Integration with Core Services**:
```python
# For exploration pages that need TreeService and SearchService

def get_tree_service() -> "TreeService":
    """Get TreeService for current graph."""
    from fs2.core.services.tree_service import TreeService

    graph_service = get_graph_service()
    selected = get_selected_graph()
    store = graph_service.get_graph(selected)

    return TreeService(store=store)


def get_search_service() -> "SearchService":
    """Get SearchService for current graph."""
    from fs2.core.services.search.search_service import SearchService

    graph_service = get_graph_service()
    selected = get_selected_graph()
    store = graph_service.get_graph(selected)

    # Note: SearchService may need EmbeddingAdapter for semantic search
    # That integration happens in Phase 6
    return SearchService(graph_store=store)
```

**Critical Separation**:
```
Services that MUST use read-only path (ConfigInspectorService):
  - Configuration display
  - Source attribution
  - Placeholder analysis
  - Validation (without instantiating configs)

Services that CAN use FS2ConfigurationService:
  - GraphService (for exploration)
  - TreeService, SearchService (for browsing)
  - TestConnectionService (needs real adapters)
```

**Dependencies**: Phase 1 infrastructure
**Affected ACs**: AC-07 through AC-12, AC-16 (read-only separation)

---

## Summary: Implementation Order

| Order | Discovery | Key Deliverable | Blocks |
|-------|-----------|-----------------|--------|
| 1 | I1-03 | ConfigInspectorService | All config display |
| 2 | I1-01 | Directory structure + CLI | All pages |
| 3 | I1-04 | Test fakes | All testing |
| 4 | I1-06 | app.py + page skeleton | All UI |
| 5 | I1-02 | Service composition | All features |
| 6 | I1-07 | Session state management | Graph selector |
| 7 | I1-08 | Service wiring | Exploration features |
| 8 | I1-05 | Phase execution | Timeline adherence |

---

## Acceptance Criteria Coverage

| AC | Primary Discovery | Key Insight |
|----|-------------------|-------------|
| AC-01 | I1-02, I1-05 | Wizard uses ConfigBackupService |
| AC-02 | I1-03 | ConfigInspectorService attribution |
| AC-03 | I1-03 | Placeholder state detection |
| AC-04 | I1-02 | TestConnectionService pattern |
| AC-05 | I1-02, I1-05 | ConfigBackupService before save |
| AC-06 | I1-02 | Doctor validation extraction |
| AC-07 | I1-08 | GraphService.list_graphs() |
| AC-08 | I1-08 | REPO detection via path sibling |
| AC-09 | I1-08 | Add repo flow |
| AC-10 | I1-08 | Init repo flow |
| AC-11 | I1-08 | SearchService integration |
| AC-12 | I1-08 | Node inspection |
| AC-13 | I1-06 | CLI command structure |
| AC-14 | I1-06 | Port configuration |
| AC-15 | I1-03 | Secret masking in inspector |
| AC-16 | I1-03 | Read-only enforcement |
| AC-17 | I1-08 | Scan trigger integration |
| AC-18 | I1-07 | Background scan state |
| AC-19 | I1-07 | Global selector rendering |
| AC-20 | I1-07 | Selection persistence |
| AC-21 | I1-08 | Tree filtering |
| AC-22 | I1-08 | Node expansion from search |

---

**Strategy Complete**: 2026-01-15
**Ready for**: `/plan-3-architect` phase
