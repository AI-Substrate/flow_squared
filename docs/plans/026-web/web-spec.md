# fs2 Web UI: Streamlit-Based Configuration and Graph Management Interface

**Mode**: Full

📚 *This specification incorporates findings from `research-dossier.md`*

---

⚠️ **Unresolved Research Opportunities**

The following external research topics were identified in `research-dossier.md` but not addressed:
- **Streamlit Best Practices for Configuration UIs**: Form validation patterns, YAML editing, undo/redo state management, session state for multi-page apps
- **Secure Secret Handling in Web UIs**: Masking sensitive fields, secure storage patterns, preventing accidental logging of API keys

Consider running `/deepresearch` prompts from `research-dossier.md` before finalizing architecture.

---

## Research Context

**Components Affected**:
- `src/fs2/cli/` - New `web` command
- `src/fs2/config/objects.py` - New `UIConfig` model
- New `src/fs2/web/` module (pages, components, services)
- `~/.config/fs2/config.yaml` and `.fs2/config.yaml` - Read/write operations

**Critical Dependencies**:
- FS2ConfigurationService (7-phase loading pipeline)
- GraphService (multi-graph management with caching)
- Doctor validation logic (config health checks)
- ConsoleAdapter pattern (display abstraction)

**Modification Risks** (from Prior Learnings):
- PL-01: `load_secrets_to_env()` mutates global `os.environ` - web UI must use read-only inspection
- PL-02: Deep merge loses source attribution - UI must track value origins
- PL-07: Error messages must be centralized for consistency
- PL-09: Placeholder expansion has two-stage validation - show 3 states (placeholder/resolved/error)
- PL-15: Doctor shows current state; wizard guides setup - implement both modes

**Link**: See `research-dossier.md` for full analysis (65+ findings, 15 prior learnings)

---

## Summary

**WHAT**: The **fs2 Hub** - a Streamlit-based portal for configuring and browsing fs2. While fs2's primary interface is the MCP server (for AI agents), users find initial setup difficult. The Hub provides guided configuration, graph management, and basic exploration to get users productive quickly.

**WHY**: First-time users struggle with fs2's multi-source YAML configuration system. Setting up Azure OpenAI, embeddings, and multi-graph repositories requires understanding placeholder syntax (`${VAR}`), file precedence rules, and provider-specific validation. The Hub provides guided wizards, live diagnostics, and a visual interface to reduce onboarding friction and let users verify their setup works before integrating with AI tools.

---

## Product Vision: The fs2 Hub

**Core Identity**: fs2 Hub is the **portal** for configuring and exploring fs2. It's not meant to replace the MCP server or CLI for daily use—it's the place you go to:
- Set up fs2 for the first time
- Add and configure new repositories
- Verify graphs are working (browse, search, check content)
- Troubleshoot configuration issues

**Design Principles**:
1. **Configuration First**: Config and diagnostics are the primary value; browsing is secondary
2. **Hub, Not IDE**: Basic exploration only; power users use MCP/CLI for deep work
3. **Verify & Trust**: Users should be able to confirm "yes, my setup works" quickly

---

## User Experience

### Global Graph Selector
A **reusable graph/repo dropdown** appears on all pages where it makes sense (Tree, Search, Node Inspector). Users select their current working graph once, and it persists across pages.

- **Location**: Top of sidebar or page header
- **Contents**: Default graph + all `other_graphs` entries
- **Behavior**: Selection persists in session state; changing graph refreshes current view

### Browse + Search Workflow

The browsing experience is **fluid and interconnected**:

```
┌─────────────────────────────────────────────────────────────┐
│  [Graph Selector: my-project ▼]                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Search: [calculator________] [Filter]                      │
│                                                             │
│  Tree View:                    │  Node Content:             │
│  ├── 📁 src/                   │  ┌─────────────────────┐   │
│  │   ├── 📄 calc.py            │  │ class Calculator:   │   │
│  │   │   ├── 🔷 Calculator     │  │   def add(self...   │   │
│  │   │   │   ├── ƒ add     ◄───┼──│   ...               │   │
│  │   │   │   ├── ƒ subtract    │  └─────────────────────┘   │
│  │   │   │   └── ƒ multiply    │  File: src/calc.py:15-42   │
│  └── 📁 tests/                 │  Category: callable        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Workflow**:
1. **Select graph** from dropdown (persists across pages)
2. **Browse** via tree view - drill down from top level, expand/collapse nodes
3. **Search** to filter - search box filters tree by node_id pattern
4. **Click node** - see full content rendered with syntax highlighting
5. **Continue from node** - from any node (search result or tree), expand to see children or navigate to parent

**Key Insight**: Search and browse are not separate—search narrows the tree, clicking a result shows it in context, and you can continue drilling from there.

---

## Goals

### Primary Goals (Configuration Focus)
1. **Guided First-Time Setup**: New users can configure fs2 from zero to working state through step-by-step wizards for LLM and embedding providers (Azure, OpenAI)
2. **Configuration Visibility**: Users see exactly which config files exist, what values are set, and where each value comes from (source attribution)
3. **Safe Config Editing**: Users can edit YAML configurations with automatic backups, undo capability, and validation before save
4. **Connection Testing**: Users can verify LLM and embedding provider credentials work before saving configuration
5. **Live Diagnostics**: Doctor output displays after every configuration change, showing health status and actionable errors

### Secondary Goals (Graph Management)
6. **Graph Discovery**: Users see all configured graphs (default + `other_graphs`) with availability status
7. **Repository Registration**: Users can add existing repositories (with `.fs2/` already initialized) or initialize new repositories
8. **Repo vs Standalone Distinction**: UI distinguishes between "REPO" graphs (have paired `config.yaml`) and standalone pickle files

### Tertiary Goals (Exploration)
9. **Search Interface**: Users can run text, regex, and semantic searches across selected graphs
10. **Tree Browser**: Users can explore code structure with pattern filtering and depth control
11. **Node Inspector**: Users can view full source code for selected nodes with syntax highlighting

---

## Non-Goals

1. **Replace CLI Entirely**: The web UI supplements but does not replace CLI commands; power users may still prefer CLI
2. **Real-Time Collaborative Editing**: No multi-user simultaneous config editing; single-user sessions only
3. **Authentication/Authorization**: No user accounts, login, or access control (local-only tool)
4. **Remote Deployment**: Not designed for cloud hosting; intended for local `localhost` usage
5. **IDE Integration**: No VS Code/IDE embedding; standalone browser interface only
6. **Config Schema Evolution**: No automatic migration of old config formats; users must manually update
7. **Custom Provider Plugins**: No UI for adding new LLM/embedding provider types beyond Azure/OpenAI
8. **Graph Editing**: No UI for manually editing nodes in a graph; graphs are scan-generated only
9. **Background Scanning**: No automatic re-scanning when files change; user must trigger scan manually
10. **Mobile Responsiveness**: Desktop browser only; no mobile optimization

---

## Complexity

**Score**: CS-4 (large)

**Breakdown**:
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 2 | New module (`src/fs2/web/`), multiple pages, CLI command, config model |
| Integration (I) | 1 | Streamlit external dependency; reuses existing internal services |
| Data/State (D) | 1 | Config file read/write with backups; session state management |
| Novelty (N) | 2 | First web UI; wizard UX patterns not yet established in codebase |
| Non-Functional (F) | 1 | Security for secret handling; usability for first-time users |
| Testing/Rollout (T) | 2 | Need integration tests; staged rollout of features |

**Total**: S(2) + I(1) + D(1) + N(2) + F(1) + T(2) = **9** → **CS-4**

**Confidence**: 0.85

**Assumptions**:
- Streamlit provides sufficient components for YAML editing and form validation
- Existing doctor validation logic can be extracted and reused
- ConfigInspectorService can be implemented without modifying core config loading
- Users will accept localhost-only access (no remote hosting requirement)

**Dependencies**:
- Streamlit library (external, stable)
- Existing FS2ConfigurationService (internal, stable)
- Existing GraphService (internal, stable)
- Doctor validation logic (internal, may need extraction)

**Risks**:
- **Secret Exposure**: API keys could be accidentally logged or displayed without masking
- **Global State Mutation**: Incorrect use of config loading could pollute `os.environ`
- **Session Isolation**: Streamlit session state may not properly isolate between browser tabs
- **Backup Corruption**: Config backup system could fail silently, losing user changes

**Phases** (suggested):
1. **Foundation**: Directory structure, CLI command, basic Streamlit skeleton
2. **Diagnostics**: Doctor panel integration, config health display
3. **Configuration**: YAML editor, source attribution, backup/save
4. **Wizards**: Azure LLM wizard, OpenAI wizard, embedding wizard, connection tests
5. **Graph Management**: Graph list, add repo, init new repo, repo config editing
6. **Exploration**: Tree browser, search interface, node inspector
7. **Polish**: Error handling, help text, documentation links

---

## Acceptance Criteria

### Configuration & Setup
**AC-01**: Given a fresh fs2 installation with no configuration, when user launches `fs2 web` and completes the Azure LLM wizard, then `~/.config/fs2/config.yaml` contains valid `llm:` section with provider=azure and `${AZURE_OPENAI_API_KEY}` placeholder.

**AC-02**: Given an existing configuration with LLM settings, when user views the Configuration page, then each field shows its current value AND the source file it came from (user config, project config, or environment variable).

**AC-03**: Given a configuration with `api_key: ${MY_KEY}` placeholder, when user views the Configuration page, then the field shows one of three states: "✓ Resolved" (env var set), "⚠ Placeholder: ${MY_KEY}" (not yet resolved), or "✗ Missing" (env var referenced but not set).

**AC-04**: Given a valid configuration, when user clicks "Test Connection" for LLM provider, then UI shows success/failure result with latency measurement or specific error message.

**AC-05**: Given the user edits a config file through the UI, when they click Save, then a timestamped backup is created at `~/.config/fs2/config_bak/{filename}.{timestamp}.bak` before the new file is written.

**AC-06**: Given doctor validation detects configuration errors, when user views any page, then a persistent diagnostic panel shows current health status with actionable fix suggestions.

### Graph Management
**AC-07**: Given multiple graphs configured in `other_graphs.graphs`, when user views the Graphs page, then all graphs display with name, path, description, and availability status (✓ exists / ✗ not found).

**AC-08**: Given a graph that lives in a `.fs2/` folder with a sibling `config.yaml`, when displayed in the Graphs page, then it shows as "REPO" type (not standalone), and user can click to edit that repo's config.

**AC-09**: Given user wants to add an existing repository, when they enter a path containing `.fs2/config.yaml`, then the graph is added to `other_graphs.graphs` in the central config with appropriate name and path.

**AC-10**: Given user wants to initialize a new repository, when they enter a path without `.fs2/`, then the UI runs `fs2 init` in that directory and adds the new graph to central config.

### Graph Scanning
**AC-17**: Given user clicks "Scan" on a graph, then the UI triggers `fs2 scan` for that graph, displays progress (files scanned, nodes created), and shows completion summary or error message.

**AC-18**: Given a scan is in progress, when user navigates away from the Graphs page, then the scan continues in background and status is visible when returning.

### Global Graph Selector
**AC-19**: Given user is on any exploration page (Tree, Search), then a graph selector dropdown appears showing all available graphs (default + other_graphs) with availability status.

**AC-20**: Given user selects a different graph from the dropdown, then the current view refreshes with data from the newly selected graph, and the selection persists when navigating to other pages.

### Search & Exploration
**AC-11**: Given a loaded graph, when user enters a search query and selects "semantic" mode, then results show with similarity scores, and semantic mode only appears if graph has embeddings.

**AC-12**: Given user selects a node from tree or search results, then full source code displays with syntax highlighting and metadata (file path, line numbers, category).

**AC-21**: Given user is in tree view and enters text in the search/filter box, then the tree narrows to show matching nodes as roots (search results become starter_nodes for TreeView), each expandable to reveal their children. *Note: This is "search narrows tree" behavior—results replace the tree roots rather than highlighting within the original hierarchy. See DYK Session 2026-01-16 Insight #5.*

**AC-22**: Given user clicks a node in search results or tree view, then they can expand that node to see its children (if any) and continue browsing from that point.

### CLI Integration
**AC-13**: Given user runs `fs2 web`, then Streamlit server starts on default port 8501 and browser opens automatically (unless `--no-browser` flag provided).

**AC-14**: Given user runs `fs2 web --port 9000`, then Streamlit server starts on port 9000 instead of default.

### Security & Safety
**AC-15**: Given a configuration contains `api_key` fields, when displayed in the UI, then actual values are masked (shown as `••••••••` or `[SET]`) and cannot be copied; only placeholders like `${VAR}` are shown in full.

**AC-16**: Given the web UI reads configuration, then it never calls `load_secrets_to_env()` or otherwise mutates global `os.environ`; all inspection is read-only.

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Secret exposure in logs/UI | Medium | High | Implement masking service; audit all display paths |
| Config backup fails silently | Low | High | Return backup path; verify backup exists before overwrite |
| Streamlit session state conflicts | Medium | Medium | Use unique session keys; test multi-tab scenarios |
| Global state mutation | Medium | High | Create read-only ConfigInspectorService; never import `load_secrets_to_env` |
| Wizard saves invalid config | Low | Medium | Validate before save; show preview of changes |
| User edits wrong config file | Medium | Medium | Always show file path being edited; require confirmation |

### Assumptions

1. **Streamlit Sufficiency**: Streamlit provides adequate components for forms, YAML editing, and real-time updates without needing custom JavaScript
2. **Local-Only Usage**: Users will run `fs2 web` locally; no need for authentication or HTTPS
3. **Single User**: Only one user edits configuration at a time; no concurrency control needed
4. **Existing Services Stable**: GraphService, ConfigurationService, and doctor validation logic are stable and can be reused
5. **Browser Availability**: Users have a modern browser (Chrome, Firefox, Safari, Edge) available

---

## Open Questions

1. **[RESOLVED: Wizard Scope]** Wizards support Azure, OpenAI, AND fake provider. Fake provider enables development/CI testing without API keys.

2. **[RESOLVED: Backup Retention]** Keep all backups with no auto-pruning. Users manually clean up `~/.config/fs2/config_bak/` if needed.

3. **[NEEDS CLARIFICATION: Concurrent Sessions]** What happens if user opens multiple browser tabs to the same `fs2 web` instance? Should we warn, block, or allow with potential conflicts?

4. **[NEEDS CLARIFICATION: Error Recovery]** If a scan fails mid-way when triggered from web UI, how should the UI recover? Show error and retry button?

5. **[RESOLVED: Config Preview]** No diff view; direct save with automatic backup provides safety net.

6. **[RESOLVED: Graph Scanning from UI]** Yes, include scan trigger. Add 'Scan' button for each graph with progress display and long-running operation handling.

---

## ADR Seeds (Optional)

### ADR-001: Config Inspection Architecture

**Decision Drivers**:
- PL-01 requires read-only inspection (no `os.environ` mutation)
- PL-02 requires source attribution (track where each value came from)
- Must support display of placeholder states (resolved/unresolved/missing)

**Candidate Alternatives**:
- A: New `ConfigInspectorService` that loads configs separately and compares
- B: Extend `FS2ConfigurationService` with read-only inspection methods
- C: Parse YAML files directly in web UI without using config service

**Stakeholders**: Web UI, Configuration system

---

### ADR-002: Secret Masking Strategy

**Decision Drivers**:
- AC-15 requires masking actual secret values
- AC-03 requires showing placeholder syntax `${VAR}`
- Must prevent secrets from appearing in logs, session state, or browser history

**Candidate Alternatives**:
- A: Mask at display layer only (service returns real values, UI masks)
- B: Mask at service layer (inspector never returns actual secrets)
- C: Hybrid (inspector returns masked values + metadata about resolution status)

**Stakeholders**: Security, Web UI, Configuration system

---

### ADR-003: Streamlit Page Organization

**Decision Drivers**:
- Multiple feature areas (config, graphs, search, wizards)
- User journey from setup to exploration
- Streamlit multi-page app patterns

**Candidate Alternatives**:
- A: Sidebar navigation with numbered pages (1_Dashboard, 2_Config, etc.)
- B: Tab-based layout on single page
- C: Wizard-first flow that transitions to dashboard after setup complete

**Stakeholders**: UX, Web UI

---

## External Research

**Incorporated**: None (external-research/ directory does not exist)

**Key Findings**: N/A

**Applied To**: N/A

---

## Unresolved Research

**Topics** (from research-dossier.md External Research Opportunities):

1. **Streamlit Best Practices for Configuration UIs**
   - Form validation with real-time feedback
   - YAML editor components with syntax highlighting
   - Undo/redo state management
   - Session state for multi-page apps

2. **Secure Secret Handling in Web UIs**
   - Masking sensitive fields in forms
   - Secure storage patterns (environment files vs keyring)
   - Preventing accidental logging of secrets
   - Best practices for API key input forms

**Impact**: Without this research, architectural decisions about secret masking (ADR-002) and editor components may need revision during implementation.

**Recommendation**: Consider addressing before architecture phase (`/plan-3-architect`). Ready-to-use `/deepresearch` prompts are available in `research-dossier.md`.

---

## Testing Strategy

**Approach**: Full TDD
**Rationale**: Security-critical features (secret handling), config backup reliability, and service integration require comprehensive test coverage with tests written before implementation.

**Focus Areas**:
- ConfigInspectorService: Read-only behavior, source attribution accuracy, placeholder state detection
- ConfigBackupService: Backup creation, restoration, retention policy enforcement
- Secret masking: No leakage in logs, session state, or display paths
- Wizard flows: Valid config generation, validation before save
- Connection testing: Success/failure handling, timeout behavior
- Graph management: REPO vs standalone detection, path resolution

**Excluded**:
- Streamlit UI rendering details (rely on Streamlit's own testing)
- Browser-specific behavior (manual testing acceptable)
- CSS/styling (visual inspection only)

**Mock Usage**: Targeted Fakes
- Continue fs2's established Fake adapter pattern (e.g., `FakeGraphStore`, `FakeLLMAdapter`)
- Use fakes for external systems: LLM APIs, embedding APIs, file system operations
- Use real services for internal logic: ConfigInspectorService, validation logic
- No traditional mock libraries (unittest.mock, pytest-mock) unless absolutely necessary

---

## Documentation Strategy

**Location**: Hybrid (README.md + docs/how/user/)
**Rationale**: Web UI is a major new feature needing both quick-start and detailed guidance.

**Content Split**:
- **README.md**: Add "Web UI" section with `fs2 web` command, basic usage, link to detailed guide
- **docs/how/user/web-ui.md**: Comprehensive guide covering:
  - Installation/launch instructions
  - Configuration wizard walkthrough (Azure, OpenAI)
  - Graph management (add repo, init new)
  - Search/exploration features
  - Troubleshooting common issues

**Target Audience**:
- Primary: First-time fs2 users setting up configuration
- Secondary: Existing users exploring web UI features

**Maintenance**: Update docs when adding new pages/features; version-specific notes if Streamlit behavior changes

---

## Clarifications

### Session 2026-01-15

**Q1: Workflow Mode**
- **Answer**: B (Full)
- **Rationale**: CS-4 complexity with multi-phase implementation, security concerns, and novel UX patterns requires comprehensive planning gates.
- **Updated**: Mode header added to spec

**Q2: Testing Approach**
- **Answer**: A (Full TDD)
- **Rationale**: Security-critical features (secret handling), config backup reliability, and service integration require comprehensive test coverage.
- **Updated**: Testing Strategy section added

**Q3: Mock/Stub/Fake Usage**
- **Answer**: B (Targeted Fakes)
- **Rationale**: Continue fs2's established Fake adapter pattern; fakes for external systems, real services for internal logic.
- **Updated**: Mock Usage in Testing Strategy section

**Q4: Documentation Strategy**
- **Answer**: C (Hybrid)
- **Rationale**: Web UI is a major new feature needing both quick-start in README and detailed guide in docs/how/.
- **Updated**: Documentation Strategy section added

**Q5: Wizard Scope**
- **Answer**: Include fake provider
- **Rationale**: Low effort addition; useful for development and CI testing without API keys.
- **Updated**: Open Questions #1 resolved; enables dev/test workflows

**Q6: Graph Scanning from UI**
- **Answer**: Yes, include scan trigger
- **Rationale**: Users should be able to trigger scans from UI with progress display.
- **Updated**: Open Questions #6 resolved; AC-17 and AC-18 added

**Q7: Backup Retention**
- **Answer**: Keep all (no pruning)
- **Rationale**: Users manually clean up; no risk of losing important backups.
- **Updated**: Open Questions #2 resolved

**Q8: Config Preview**
- **Answer**: No diff view; direct save with backup
- **Rationale**: Simpler UX; backup provides safety net for recovery.
- **Updated**: Open Questions #5 resolved

**UX Clarification: fs2 Hub Vision**
- **Identity**: "fs2 Hub" - the portal for configuring and basic browsing
- **Primary Use**: Setup, configuration, verification that graphs work
- **Global Graph Selector**: Reusable dropdown on all exploration pages, persists in session
- **Browse + Search Integration**: Search filters the tree; clicking results lets you continue browsing from that node; fluid workflow between search and browse
- **Updated**: Product Vision section added; AC-19 through AC-22 added

---

## Appendix: User Requirements Traceability

| User Requirement | Acceptance Criteria |
|------------------|---------------------|
| `fs2 web` launches Streamlit and opens browser | AC-13, AC-14 |
| See all graphs (default + other_graphs) | AC-07 |
| Add existing repo with .fs2 | AC-09 |
| Add new path (run fs2 init) | AC-10 |
| Distinguish REPO vs standalone graph | AC-08 |
| Edit repo config (scan_paths, etc.) | AC-08 |
| Update ~/.config/fs2/config.yaml | AC-02, AC-05 |
| Setup wizards (Azure, OpenAI, fake) | AC-01, AC-04 |
| Test connection buttons | AC-04 |
| Show doctor output | AC-06 |
| Config editor with field documentation | AC-02, AC-03 |
| Show which file is being edited | AC-02 |
| Save with backup | AC-05 |
| Show composed/final config | AC-02 |
| Secrets show as "present" not value | AC-15 |
| Search interface | AC-11, AC-21 |
| Tree browser | AC-12, AC-21, AC-22 |
| Node inspector | AC-12 |
| Trigger scan from UI | AC-17, AC-18 |
| Global graph selector | AC-19, AC-20 |
| Integrated browse/search | AC-21, AC-22 |
