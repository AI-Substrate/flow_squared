# Risk & Mitigation Discoveries: fs2 Web UI Implementation

**Generated**: 2026-01-15
**Plan**: 026-web
**Purpose**: Identify implementation risks and mitigation strategies based on research findings
**Source**: research-dossier.md (65+ findings, 15 prior learnings)

---

## Risk Summary

| ID | Risk | Category | Impact | Affected Phases |
|----|------|----------|--------|-----------------|
| R1-01 | Global State Mutation via load_secrets_to_env() | State Management | Critical | Phase 1, 3, 4 |
| R1-02 | Source Attribution Loss During Config Merge | Data Integrity | High | Phase 1, 3 |
| R1-03 | Secret Exposure in Logs, UI, and Session State | Security | Critical | All Phases |
| R1-04 | Config Backup Failure Leading to Data Loss | Data Integrity | High | Phase 3 |
| R1-05 | Session Isolation Failures in Streamlit | State Management | High | All Phases |
| R1-06 | Placeholder Validation State Confusion | Data Integrity | Medium | Phase 3, 4 |
| R1-07 | Relative Path Resolution Context Loss | Data Integrity | Medium | Phase 5 |
| R1-08 | Test Pollution from Configuration Loading | Testing | High | All Phases |

---

## R1-01: Global State Mutation via load_secrets_to_env()

**Risk Category**: State Management
**Impact**: Critical
**Source**: PL-01 from research-dossier.md

### Problem Description

The function `load_secrets_to_env()` in `src/fs2/config/loaders.py` mutates the global `os.environ` dictionary when called:

```python
def load_secrets_to_env() -> None:
    # User secrets (lowest priority of files)
    user_secrets = get_user_config_dir() / "secrets.env"
    if user_secrets.exists():
        load_dotenv(user_secrets, override=True)

    # Project secrets (overrides user)
    project_secrets = get_project_config_dir() / "secrets.env"
    if project_secrets.exists():
        load_dotenv(project_secrets, override=True)

    # Working dir .env (highest priority)
    dotenv_file = Path.cwd() / ".env"
    if dotenv_file.exists():
        load_dotenv(dotenv_file, override=True)
```

**What Could Go Wrong**:
1. **Cross-request contamination**: If web UI calls this function during one user's session, environment variables persist and affect subsequent requests or other tabs
2. **Test pollution**: Tests calling production code that invokes this function will mutate `os.environ`, causing flaky tests and hard-to-debug failures
3. **Stale secrets**: If secrets files change on disk, the cached `os.environ` values won't update until function is called again
4. **Multi-project conflicts**: If user browses graphs from multiple projects, secrets from one project pollute another's environment

### Mitigation Strategy

1. **Never call `load_secrets_to_env()` from web UI code path**
   - Web UI must use a read-only inspection approach
   - Create `ConfigInspectorService` that uses `dotenv_values()` (returns dict without modifying env)

2. **Create isolated config reading functions**:
   ```python
   def read_secrets_readonly(path: Path) -> dict[str, str]:
       """Read secrets file without modifying os.environ."""
       if not path.exists():
           return {}
       return dotenv_values(path)  # Returns dict, never mutates
   ```

3. **Validate web UI import graph**:
   - Ensure no module imported by web UI transitively imports `load_secrets_to_env`
   - Add a startup check that fails loudly if `os.environ` was modified during import

### Validation

1. **Unit Test**: Test that `ConfigInspectorService` does not modify `os.environ`
   ```python
   def test_config_inspector_does_not_mutate_environ(monkeypatch, tmp_path):
       original_env = os.environ.copy()
       inspector = ConfigInspectorService()
       inspector.inspect()
       assert os.environ == original_env
   ```

2. **Integration Test**: Test multi-request isolation
   ```python
   def test_sequential_requests_have_isolated_env():
       # Request 1: Set PROJECT_A secrets
       # Request 2: Verify PROJECT_B doesn't see PROJECT_A's secrets
   ```

### Affected Phases

- **Phase 1 (Foundation)**: ConfigInspectorService must be built with read-only pattern
- **Phase 3 (Configuration Editor)**: Config loading for display must not use mutating functions
- **Phase 4 (Setup Wizards)**: Wizard validation must not pollute global state

---

## R1-02: Source Attribution Loss During Config Merge

**Risk Category**: Data Integrity
**Impact**: High
**Source**: PL-02 from research-dossier.md

### Problem Description

The `deep_merge()` function in `src/fs2/config/loaders.py` merges configuration dictionaries but loses information about which source file each value came from:

```python
def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, overlay_value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(overlay_value, dict):
            result[key] = deep_merge(result[key], overlay_value)
        else:
            result[key] = copy.deepcopy(overlay_value)  # Source info lost here
    return result
```

**What Could Go Wrong**:
1. **User confusion**: User sees a value in merged config but doesn't know if it came from user config, project config, or environment variable
2. **Debugging difficulty**: When something is wrong, user can't identify which file to edit
3. **Override invisibility**: User doesn't realize their project config is overriding their user config, or vice versa

### Mitigation Strategy

1. **Create AttributedValue wrapper**:
   ```python
   @dataclass
   class AttributedValue:
       value: Any
       source: Literal["user", "project", "env", "default"]
       source_path: Path | None  # For file sources
       override_chain: list[tuple[str, Any]]  # Previous values that were overridden
   ```

2. **Build attributed merge function**:
   ```python
   def deep_merge_with_attribution(
       sources: list[tuple[str, dict[str, Any], Path | None]]
   ) -> dict[str, AttributedValue]:
       """Merge configs while tracking which source each value came from."""
       result = {}
       for source_name, source_dict, source_path in sources:
           for key, value in flatten_dict(source_dict).items():
               if key in result:
                   # Track the override
                   result[key].override_chain.append((result[key].source, result[key].value))
               result[key] = AttributedValue(value, source_name, source_path, [])
       return result
   ```

3. **UI display with source badges**:
   ```
   api_key: ${AZURE_API_KEY}  [project config] (overrides user config)
   timeout: 30                [user config]
   model: gpt-4               [default]
   ```

### Validation

1. **Unit Test**: Verify attribution tracking through merge
   ```python
   def test_attribution_tracks_overrides():
       user = {"llm": {"timeout": 30}}
       project = {"llm": {"timeout": 60}}
       merged = deep_merge_with_attribution([
           ("user", user, Path("~/.config/fs2/config.yaml")),
           ("project", project, Path(".fs2/config.yaml")),
       ])
       assert merged["llm.timeout"].value == 60
       assert merged["llm.timeout"].source == "project"
       assert merged["llm.timeout"].override_chain == [("user", 30)]
   ```

2. **Visual Test**: Verify source badges render correctly in Streamlit

### Affected Phases

- **Phase 1 (Foundation)**: ConfigInspectorService must track attribution
- **Phase 3 (Configuration Editor)**: Editor must display source information

---

## R1-03: Secret Exposure in Logs, UI, and Session State

**Risk Category**: Security
**Impact**: Critical
**Source**: Research dossier "Danger Zones" section

### Problem Description

API keys and secrets could be accidentally exposed through multiple vectors:
1. **Logging**: Secrets logged to console, file, or error reports
2. **UI Display**: Secrets shown in plain text in config editor or diagnostics
3. **Session State**: Secrets stored in Streamlit session state persist across reruns and are serializable
4. **Browser History**: Secrets in URL parameters or form submissions
5. **Error Messages**: Exception strings containing secret values

**What Could Go Wrong**:
1. **Credential theft**: API keys visible in logs or UI could be stolen
2. **Compliance violation**: Exposing secrets violates security best practices
3. **Session hijacking**: Secrets in session state could be extracted via XSS or browser extension

### Mitigation Strategy

1. **Never store raw secrets in session state**:
   ```python
   # BAD
   st.session_state['api_key'] = user_input

   # GOOD - Store reference only
   st.session_state['api_key_is_set'] = True
   st.session_state['api_key_source'] = "env:AZURE_API_KEY"
   ```

2. **Create SecretMask utility**:
   ```python
   def mask_secret(value: str | None) -> str:
       """Mask a secret for display."""
       if value is None:
           return "[NOT SET]"
       if value.startswith("${"):
           return value  # Placeholder, show as-is
       if len(value) < 8:
           return "[SET]"
       return f"{value[:4]}...{value[-4:]}"  # Show first/last 4 chars only
   ```

3. **Implement secret field detection**:
   ```python
   SECRET_FIELD_PATTERNS = {"api_key", "secret", "password", "token", "key"}

   def is_secret_field(field_name: str) -> bool:
       return any(pattern in field_name.lower() for pattern in SECRET_FIELD_PATTERNS)
   ```

4. **Add logging sanitization**:
   ```python
   class SecretSanitizingFilter(logging.Filter):
       def filter(self, record):
           record.msg = sanitize_secrets(str(record.msg))
           return True
   ```

5. **Use password input for secrets**:
   ```python
   st.text_input("API Key", type="password", key="api_key_input")
   ```

6. **Prevent browser autocomplete for secrets**:
   ```python
   st.markdown('<input type="password" autocomplete="off">', unsafe_allow_html=True)
   ```

### Validation

1. **Security Scan**: Grep codebase for secret field names in logging statements
   ```bash
   grep -rn "api_key\|secret\|password" src/fs2/web/ | grep -v "mask\|sanitize"
   ```

2. **Unit Test**: Verify mask function handles edge cases
   ```python
   def test_mask_handles_short_secrets():
       assert mask_secret("abc") == "[SET]"
       assert mask_secret(None) == "[NOT SET]"
       assert mask_secret("sk-12345678abcdefgh") == "sk-1...efgh"
   ```

3. **Session State Test**: Verify no raw secrets in session state
   ```python
   def test_session_state_contains_no_raw_secrets():
       # After wizard completion
       for key, value in st.session_state.items():
           if is_secret_field(key):
               assert value in ("[SET]", True, False) or value.startswith("${")
   ```

### Affected Phases

- **All Phases**: Every phase that displays or processes config must apply masking

---

## R1-04: Config Backup Failure Leading to Data Loss

**Risk Category**: Data Integrity
**Impact**: High
**Source**: Research dossier "Key Services to Create" section

### Problem Description

The planned ConfigBackupService could fail silently in several ways:
1. **Disk full**: Backup fails but save proceeds, losing original config
2. **Permission denied**: Can't write to backup directory
3. **Concurrent writes**: Race condition between backup creation and config save
4. **Backup corruption**: Backup file created but truncated or corrupted

**What Could Go Wrong**:
1. **Permanent data loss**: User's working config lost with no recovery option
2. **Partial writes**: Config file left in corrupted state
3. **Silent failures**: User thinks backup exists but it doesn't

### Mitigation Strategy

1. **Atomic backup creation**:
   ```python
   def backup(self, config_path: Path) -> Path:
       """Create backup atomically - fail BEFORE touching original."""
       backup_path = self._get_backup_path(config_path)

       # Write to temp file first
       temp_path = backup_path.with_suffix(".tmp")
       try:
           shutil.copy2(config_path, temp_path)
           # Verify backup integrity
           if not self._verify_backup(temp_path, config_path):
               raise BackupCorruptionError("Backup verification failed")
           # Atomic rename
           temp_path.rename(backup_path)
           return backup_path
       except Exception:
           temp_path.unlink(missing_ok=True)
           raise
   ```

2. **Save-with-backup transaction**:
   ```python
   def save_with_backup(self, config_path: Path, new_content: str) -> SaveResult:
       """Transactional save: backup succeeds or save is aborted."""
       # Step 1: Create verified backup
       try:
           backup_path = self.backup(config_path)
       except BackupError as e:
           return SaveResult(success=False, error=f"Backup failed: {e}")

       # Step 2: Write new config to temp file
       temp_path = config_path.with_suffix(".new")
       try:
           temp_path.write_text(new_content)
           # Step 3: Validate new config is parseable
           yaml.safe_load(new_content)
           # Step 4: Atomic replace
           temp_path.rename(config_path)
           return SaveResult(success=True, backup_path=backup_path)
       except Exception as e:
           temp_path.unlink(missing_ok=True)
           return SaveResult(success=False, error=f"Save failed: {e}", backup_path=backup_path)
   ```

3. **Verify backup integrity**:
   ```python
   def _verify_backup(self, backup_path: Path, original_path: Path) -> bool:
       """Verify backup matches original."""
       backup_hash = hashlib.sha256(backup_path.read_bytes()).hexdigest()
       original_hash = hashlib.sha256(original_path.read_bytes()).hexdigest()
       return backup_hash == original_hash
   ```

4. **Disk space pre-check**:
   ```python
   def _check_disk_space(self, path: Path, required_bytes: int) -> bool:
       stat = os.statvfs(path)
       available = stat.f_frsize * stat.f_bavail
       return available > required_bytes * 2  # 2x safety margin
   ```

### Validation

1. **Unit Test**: Backup creation under failure conditions
   ```python
   def test_backup_fails_gracefully_on_permission_error(tmp_path):
       config = tmp_path / "config.yaml"
       config.write_text("key: value")
       backup_dir = tmp_path / "backups"
       backup_dir.mkdir()
       backup_dir.chmod(0o000)  # Remove write permission

       service = ConfigBackupService(backup_dir)
       with pytest.raises(BackupError):
           service.backup(config)
   ```

2. **Integration Test**: Full save-with-backup transaction
   ```python
   def test_save_aborted_if_backup_fails():
       # Arrange: Make backup directory read-only
       # Act: Attempt save
       # Assert: Original config unchanged, error message returned
   ```

### Affected Phases

- **Phase 3 (Configuration Editor)**: Backup service must be fully implemented before save feature

---

## R1-05: Session Isolation Failures in Streamlit

**Risk Category**: State Management
**Impact**: High
**Source**: PL-06 from research-dossier.md

### Problem Description

Streamlit manages session state per browser tab, but several isolation issues can occur:
1. **Shared module-level state**: Python modules are shared across sessions
2. **Singleton services**: Services created at module level are shared
3. **File descriptor leaks**: Open files from one session affect another
4. **Thread-local storage**: Not properly isolated in Streamlit's threading model

**What Could Go Wrong**:
1. **Cross-tab interference**: Actions in one browser tab affect another
2. **Stale cache**: User A's cached graph shown to User B
3. **Resource exhaustion**: File handles or connections not cleaned up between sessions

### Mitigation Strategy

1. **No module-level service instances**:
   ```python
   # BAD - Shared across all sessions
   graph_service = GraphService(config)

   # GOOD - Created per session
   def get_graph_service() -> GraphService:
       if 'graph_service' not in st.session_state:
           st.session_state['graph_service'] = GraphService(get_config())
       return st.session_state['graph_service']
   ```

2. **Session-scoped config loading**:
   ```python
   def get_session_config() -> ConfigInspectorService:
       """Load config fresh each session - no cross-session pollution."""
       return ConfigInspectorService(
           user_path=get_user_config_dir() / "config.yaml",
           project_path=get_project_config_dir() / "config.yaml",
       )
   ```

3. **Explicit cache invalidation**:
   ```python
   @st.cache_resource(ttl=60)  # Short TTL to avoid stale data
   def get_graph_store(_graph_path: Path, _mtime: float) -> GraphStore:
       """Cache with mtime to invalidate on file change."""
       return NetworkXGraphStore.load(graph_path)
   ```

4. **Session cleanup on new project**:
   ```python
   def on_project_change():
       """Clear session state when user switches projects."""
       for key in list(st.session_state.keys()):
           if key.startswith('project_'):
               del st.session_state[key]
   ```

### Validation

1. **Multi-session Test**: Verify isolation between browser tabs
   ```python
   def test_sessions_are_isolated():
       # Open two browser tabs
       # Tab 1: Set config value A
       # Tab 2: Verify config shows default, not A
   ```

2. **Singleton Audit**: Check no module-level service instances
   ```bash
   grep -rn "^[a-z_]+ = .*Service(" src/fs2/web/
   # Should return nothing
   ```

### Affected Phases

- **All Phases**: Every phase must create services within session scope

---

## R1-06: Placeholder Validation State Confusion

**Risk Category**: Data Integrity
**Impact**: Medium
**Source**: PL-09 from research-dossier.md

### Problem Description

Placeholder expansion (`${VAR}`) involves two-stage validation:
1. **Field validator** runs first, sees `${VAR}` placeholder
2. **Model validator** runs second, expands placeholder to actual value
3. No re-validation after expansion

This creates three distinct states that must be tracked:
- `${VAR}` - Placeholder present, not yet expanded
- `actual-value` - Placeholder resolved successfully
- `${MISSING_VAR}` - Placeholder present but env var not set

**What Could Go Wrong**:
1. **False success**: UI shows placeholder as valid when env var is missing
2. **State confusion**: User doesn't understand if `${VAR}` is resolved or not
3. **Validation bypass**: Expanded value might violate field constraints

### Mitigation Strategy

1. **Track three-state placeholder resolution**:
   ```python
   @dataclass
   class PlaceholderState:
       raw_value: str
       status: Literal["literal", "placeholder_resolved", "placeholder_unresolved"]
       resolved_value: str | None
       env_var_name: str | None

   def analyze_placeholder(value: str) -> PlaceholderState:
       match = re.search(r'\$\{([A-Z_][A-Z0-9_]*)\}', value)
       if not match:
           return PlaceholderState(value, "literal", value, None)

       var_name = match.group(1)
       if var_name in os.environ:
           resolved = value.replace(match.group(0), os.environ[var_name])
           return PlaceholderState(value, "placeholder_resolved", resolved, var_name)
       else:
           return PlaceholderState(value, "placeholder_unresolved", None, var_name)
   ```

2. **Visual indicator in UI**:
   ```python
   def render_config_value(field: str, state: PlaceholderState):
       if state.status == "literal":
           st.text(state.raw_value)
       elif state.status == "placeholder_resolved":
           st.success(f"{state.raw_value} -> {mask_secret(state.resolved_value)}")
       else:
           st.error(f"{state.raw_value} (${state.env_var_name} not set)")
   ```

3. **Post-expansion validation**:
   ```python
   def validate_after_expansion(config_dict: dict) -> list[ValidationError]:
       """Run field validators again after placeholder expansion."""
       errors = []
       expanded = expand_all_placeholders(config_dict)
       for field, value in expanded.items():
           if is_secret_field(field) and _is_literal_secret(value):
               errors.append(ValidationError(field, "Expanded value looks like literal secret"))
       return errors
   ```

### Validation

1. **Unit Test**: Three-state detection
   ```python
   def test_placeholder_states():
       assert analyze_placeholder("literal").status == "literal"

       os.environ["TEST_VAR"] = "resolved"
       assert analyze_placeholder("${TEST_VAR}").status == "placeholder_resolved"

       del os.environ["MISSING_VAR"]
       assert analyze_placeholder("${MISSING_VAR}").status == "placeholder_unresolved"
   ```

2. **Visual Test**: Verify correct icons/colors for each state

### Affected Phases

- **Phase 3 (Configuration Editor)**: Editor must show placeholder states
- **Phase 4 (Setup Wizards)**: Wizards must validate placeholder resolution

---

## R1-07: Relative Path Resolution Context Loss

**Risk Category**: Data Integrity
**Impact**: Medium
**Source**: PL-14 from research-dossier.md

### Problem Description

When resolving paths in configs (e.g., `other_graphs.graphs[].path`), relative paths need context about which config file they came from:
- Path `./graphs/shared.pickle` in user config resolves from `~/.config/fs2/`
- Same path in project config resolves from `./.fs2/`

The `_source_dir` PrivateAttr tracks this, but it can be lost during:
1. **Serialization**: PrivateAttr not included in `.dict()` or `.model_dump()`
2. **Display**: UI might show path without context
3. **Editing**: User modifies path without understanding resolution context

**What Could Go Wrong**:
1. **Wrong path resolution**: Relative path resolves from wrong directory
2. **Broken graphs**: User adds relative path in project config, but it resolves incorrectly
3. **Confusing display**: UI shows `./foo/bar.pickle` without indicating base directory

### Mitigation Strategy

1. **Always display resolved absolute paths**:
   ```python
   def render_graph_path(graph: OtherGraph) -> None:
       resolved = graph._resolve_path()  # Use internal resolution
       st.text(f"Path: {graph.path}")
       st.caption(f"Resolves to: {resolved}")
   ```

2. **Path input with base directory selector**:
   ```python
   def path_input(label: str, current_value: str, base_dir: Path) -> str:
       col1, col2 = st.columns([3, 1])
       with col1:
           path = st.text_input(label, value=current_value)
       with col2:
           if path.startswith(("./", "../")):
               st.caption(f"Relative to: {base_dir}")
       return path
   ```

3. **Validate path exists after resolution**:
   ```python
   def validate_graph_path(path: str, source_dir: Path) -> PathValidation:
       resolved = resolve_path(path, source_dir)
       return PathValidation(
           raw_path=path,
           resolved_path=resolved,
           exists=resolved.exists(),
           is_relative=not Path(path).is_absolute(),
           base_dir=source_dir if not Path(path).is_absolute() else None,
       )
   ```

4. **Track source_dir through edit operations**:
   ```python
   @dataclass
   class GraphConfigEdit:
       graph_name: str
       field: str
       old_value: Any
       new_value: Any
       source_file: Path  # Track which file is being edited
       source_dir: Path   # Track resolution context
   ```

### Validation

1. **Unit Test**: Relative path resolution from different contexts
   ```python
   def test_relative_path_resolves_from_source_dir():
       user_graph = OtherGraph(name="lib", path="./graphs/lib.pickle")
       user_graph._source_dir = Path.home() / ".config" / "fs2"

       project_graph = OtherGraph(name="lib", path="./graphs/lib.pickle")
       project_graph._source_dir = Path.cwd() / ".fs2"

       assert user_graph._resolve_path() != project_graph._resolve_path()
   ```

2. **Integration Test**: Add relative path via UI, verify correct resolution

### Affected Phases

- **Phase 5 (Graph Management)**: Adding graphs with relative paths must preserve context

---

## R1-08: Test Pollution from Configuration Loading

**Risk Category**: Testing
**Impact**: High
**Source**: PL-12 from research-dossier.md

### Problem Description

Test pollution occurs when:
1. Tests don't properly isolate configuration state
2. `os.environ` mutations persist between tests
3. Module-level imports trigger config loading
4. Fixtures don't reset configuration between tests

**What Could Go Wrong**:
1. **Flaky tests**: Tests pass/fail depending on execution order
2. **Hidden dependencies**: Test A only passes because Test B set up state
3. **Environment leakage**: CI environment affects local test results
4. **False positives**: Tests pass with polluted state but fail in production

### Mitigation Strategy

1. **Mandatory environment cleanup fixture**:
   ```python
   @pytest.fixture(autouse=True)
   def clean_config_env(monkeypatch):
       """Clear all FS2_* environment variables before each test."""
       for key in list(os.environ.keys()):
           if key.startswith("FS2_"):
               monkeypatch.delenv(key, raising=False)
       yield
       # Cleanup happens automatically via monkeypatch
   ```

2. **Isolated working directory**:
   ```python
   @pytest.fixture
   def isolated_project(tmp_path, monkeypatch):
       """Create isolated project directory with clean config."""
       project_dir = tmp_path / "project"
       project_dir.mkdir()
       (project_dir / ".fs2").mkdir()
       monkeypatch.chdir(project_dir)
       monkeypatch.setenv("HOME", str(tmp_path / "home"))
       return project_dir
   ```

3. **No module-level config loading in web code**:
   ```python
   # BAD - Config loaded at import time
   from fs2.config import FS2ConfigurationService
   config = FS2ConfigurationService()  # Runs at import!

   # GOOD - Config loaded on first use
   _config: FS2ConfigurationService | None = None

   def get_config() -> FS2ConfigurationService:
       global _config
       if _config is None:
           _config = FS2ConfigurationService()
       return _config
   ```

4. **Session state reset between tests**:
   ```python
   @pytest.fixture(autouse=True)
   def reset_streamlit_state():
       """Clear Streamlit session state between tests."""
       import streamlit as st
       st.session_state.clear()
       yield
   ```

5. **Import guard for dangerous functions**:
   ```python
   # In test setup
   def test_web_module_doesnt_import_dangerous_functions():
       """Verify web UI doesn't transitively import load_secrets_to_env."""
       import sys
       original_modules = set(sys.modules.keys())

       import fs2.web  # noqa

       # Check that loaders module functions weren't called
       assert 'FS2_TEST_SENTINEL' not in os.environ
   ```

### Validation

1. **Test Order Independence**: Run tests in random order
   ```bash
   pytest --randomly-seed=12345 tests/unit/web/
   ```

2. **Isolation Audit**: Check for module-level side effects
   ```python
   def test_module_import_has_no_side_effects():
       env_before = os.environ.copy()
       import fs2.web.app  # noqa
       env_after = os.environ.copy()
       assert env_before == env_after
   ```

3. **Parallel Execution**: Run tests in parallel to expose shared state
   ```bash
   pytest -n auto tests/unit/web/
   ```

### Affected Phases

- **All Phases**: All web UI code and tests must follow isolation patterns

---

## Implementation Checklist

Before each phase begins, verify these risk mitigations are in place:

### Pre-Phase 1 (Foundation)
- [ ] ConfigInspectorService uses read-only config access
- [ ] No imports of `load_secrets_to_env` in web module
- [ ] Session-scoped service creation pattern established
- [ ] Test fixtures include environment cleanup

### Pre-Phase 3 (Configuration Editor)
- [ ] ConfigBackupService with atomic backup/restore
- [ ] Source attribution tracking implemented
- [ ] Placeholder state detection (3-state)
- [ ] Secret masking utility tested

### Pre-Phase 4 (Setup Wizards)
- [ ] Secret input uses password fields
- [ ] No secrets stored in session state
- [ ] Validation does not mutate global state

### Pre-Phase 5 (Graph Management)
- [ ] Path resolution preserves _source_dir context
- [ ] Relative path display includes base directory
- [ ] Path validation checks existence after resolution

---

## Rollback Procedures

### R1-01 Rollback (Global State Mutation)
If web UI accidentally mutates os.environ:
1. Restart Streamlit server (`Ctrl+C` and re-run)
2. Clear browser session storage
3. Audit web code for load_secrets_to_env calls

### R1-04 Rollback (Backup Failure)
If config backup fails during save:
1. Check backup directory for `.tmp` files (incomplete backups)
2. Manual backup: `cp .fs2/config.yaml .fs2/config.yaml.emergency`
3. Retry save operation

### R1-05 Rollback (Session Isolation)
If cross-session state pollution detected:
1. Force session reset: `st.session_state.clear()`
2. Reload page in incognito mode
3. Restart Streamlit server to clear all sessions

---

**Document Complete**: 2026-01-15
**Next Steps**: Review with architecture team, incorporate into phase task files
