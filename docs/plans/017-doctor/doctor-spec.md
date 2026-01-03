# fs2 Doctor Command

**Mode**: Simple

📚 *This specification incorporates findings from research-dossier.md*

---

## Research Context

Based on comprehensive codebase research (55+ findings from 7 specialized subagents):

- **Components affected**: New CLI command (`src/fs2/cli/doctor.py`), enhanced `fs2 init` command
- **Critical dependencies**: `src/fs2/config/paths.py` (XDG resolution), `src/fs2/config/loaders.py` (multi-source loading), Rich library
- **Modification risks**: Low - pure addition for doctor; moderate for init enhancement
- **Prior learnings applied**: 15 gotchas including singleton pollution (PL-01), CWD brittleness (PL-11), leaf-level override behavior (PL-05)

See `research-dossier.md` for full analysis.

---

## Summary

**WHAT**: A diagnostic CLI command (`fs2 doctor`) that displays configuration health status, showing all config sources in play, the merge/override chain, provider status (LLM/embeddings), placeholder resolution status, and actionable warnings with clickable documentation links.

**WHY**: Users setting up fs2 (especially via uvx) need visibility into:
1. Which configuration files are being loaded and from where
2. Whether their LLM and embedding providers are properly configured
3. When local configs override central/user-global configs (potentially unintentionally)
4. Which `${VAR}` placeholders are unresolved
5. Clear next steps when configuration is incomplete

Additionally, `fs2 init` should be enhanced to automatically bootstrap user-global config (`~/.config/fs2/`) alongside local project config, eliminating the need for users to understand the internal config hierarchy.

---

## Goals

1. **Configuration Visibility**: Show all config files in play across central (`~/.config/fs2/`) and local (`./.fs2/`) locations
2. **Merge Chain Transparency**: Display the precedence chain showing how values are composed and overridden
3. **Override Warnings**: Highlight when local configs override central configs (user awareness)
4. **Provider Status**: Clearly indicate whether LLM and embedding providers are configured
5. **Placeholder Validation**: Check that all `${VAR}` placeholders resolve to actual environment values
6. **Actionable Guidance**: Provide clickable GitHub documentation links for setup help
7. **Setup Detection**: Warn when no configs exist and suggest `fs2 init`
8. **Workspace Awareness**: Warn when central configs exist but local `.fs2/` is missing
9. **Human-Readable Output**: Use Rich library for clear, scannable terminal output
10. **Enhanced Init**: `fs2 init` automatically bootstraps both local `./.fs2/` and global `~/.config/fs2/` configs in one command

---

## Non-Goals

1. **Config Editing**: Doctor is read-only diagnostic; does not modify configuration files
2. **Auto-Fix**: Does not automatically resolve configuration issues (only reports and suggests)
3. **Secret Display**: Never displays actual secret values (only shows resolution status: ✓/✗)
4. **API Connectivity Testing**: Does not test API connectivity or credential validity (only validates config structure)
5. **Interactive Prompts**: No interactive configuration wizard (that's a separate feature)
6. **Performance Profiling**: Does not measure config loading performance

---

## Complexity

**Score**: CS-2 (small)

**Breakdown**:
| Factor | Score | Rationale |
|--------|-------|-----------|
| Surface Area (S) | 1 | New CLI command + init enhancement (2-3 files) |
| Integration (I) | 0 | Internal only - uses existing config loaders |
| Data/State (D) | 0 | No schema changes; read-only inspection |
| Novelty (N) | 1 | Clear requirements but some UX design choices |
| Non-Functional (F) | 0 | Standard CLI output; no special requirements |
| Testing/Rollout (T) | 0 | Unit tests sufficient; no staged rollout needed |

**Total**: P = 2 → **CS-2 (small)**

**Confidence**: 0.85

**Assumptions**:
- Rich library already available (it is - used throughout CLI)
- XDG path resolution functions already exist (confirmed in research)
- Config loaders can be called independently for inspection (confirmed)

**Dependencies**:
- Example config templates must exist in `docs/` before init can copy them

**Risks**:
- Terminal width constraints may require responsive layout for merge chain display

**Phases**:
1. Implement `fs2 doctor` command with Rich output
2. Enhance `fs2 init --global` for user-global config setup
3. Create example config templates in `docs/examples/`

---

## Acceptance Criteria

### fs2 doctor Command

1. **AC-01**: Running `fs2 doctor` displays a header showing current working directory
2. **AC-02**: Command lists all configuration files found/not found:
   - `~/.config/fs2/config.yaml` (or `$XDG_CONFIG_HOME/fs2/config.yaml`)
   - `~/.config/fs2/secrets.env`
   - `./.fs2/config.yaml`
   - `./.fs2/secrets.env`
   - `./.env`
3. **AC-03**: Command displays merge chain showing precedence layers with values at each layer
4. **AC-04**: When local config overrides a central value, a warning is displayed identifying the override
5. **AC-05**: Provider status section shows LLM configuration status (configured/not configured)
6. **AC-06**: Provider status section shows embedding configuration status (configured/not configured)
7. **AC-07**: When a provider is not configured, a clickable GitHub URL is displayed linking to setup documentation (e.g., `https://github.com/AI-Substrate/flow_squared/blob/main/docs/how/embeddings/2-configuration.md`)
8. **AC-08**: Placeholder section lists all `${VAR}` placeholders found and their resolution status (✓ resolved / ✗ not found)
9. **AC-09**: When no configuration files exist anywhere, command suggests running `fs2 init`
10. **AC-10**: When central config exists but no local `.fs2/` folder, a warning is displayed
11. **AC-11**: Output uses Rich library formatting (panels, tables, colored status indicators)
12. **AC-12**: Command exits with code 0 when healthy, code 1 when critical issues found
13. **AC-13**: Command warns when literal secrets detected in config files (`sk-*` prefix or >64 char strings in secret fields)

### fs2 init Enhancement

14. **AC-14**: `fs2 init` creates both local `./.fs2/` AND global `~/.config/fs2/` in one command
15. **AC-15**: If global `~/.config/fs2/` already exists, it is skipped (not overwritten, no error)
16. **AC-16**: If local `./.fs2/` already exists, `--force` is required to overwrite (unchanged from current behavior)
17. **AC-17**: Example files are sourced from `docs/examples/` (not hardcoded in Python)
18. **AC-18**: Reports what was created: "Created local config", "Created global config", "Skipped global (already exists)"
19. **AC-19**: No `--global` flag needed - users don't need to understand config hierarchy
20. **AC-20**: `fs2 init` displays current working directory path before creating configs
21. **AC-21**: If no `.git` folder exists in current directory, shows prominent red warning (but does not fail)
22. **AC-22**: `fs2 init` creates `.fs2/.gitignore` that ignores everything except `config.yaml`

### CLI Guard (Require Init)

23. **AC-23**: Commands like `scan`, `search`, `tree`, `get-node`, `mcp` fail if `.fs2/` doesn't exist in current directory
24. **AC-24**: When command fails due to missing init, error message shows current working directory path
25. **AC-25**: Error message suggests running `fs2 init` when `.fs2/` is missing
26. **AC-26**: If no `.git` folder exists, error also shows prominent red warning (helps identify wrong directory)
27. **AC-27**: These commands always work without init: `init`, `doctor`, `--help`, `--version`, and any subcommand `--help`
28. **AC-28**: No auto-init behavior - commands never create `.fs2/` implicitly

### Example Templates

29. **AC-29**: `docs/how/user/config.yaml.example` exists with documented LLM and embedding sections (source of truth)
30. **AC-30**: `docs/how/user/secrets.env.example` exists with placeholder variable names (source of truth)
31. **AC-31**: `just doc-build` copies `.example` files to `src/fs2/docs/` and `pyproject.toml` includes them in wheel; accessible via `importlib.resources.files("fs2.docs")` (NOT registered in registry.yaml - they're templates, not documentation)

### Config Validation

32. **AC-32**: `fs2 doctor` attempts to load all found config files using YAML parser and catches syntax errors
33. **AC-33**: YAML syntax errors display line number and actionable fix suggestion
34. **AC-34**: Pydantic validation errors display field path and expected type
35. **AC-35**: LLM provider validation checks required fields based on provider type (azure needs endpoint/deployment/api_key, openai needs api_key, etc.)
36. **AC-36**: Embedding mode validation checks required fields based on mode (azure, openai, local, none)
37. **AC-37**: Validation errors include clickable link to relevant documentation section (configuration-guide.md)
38. **AC-38**: Doctor distinguishes between "not configured" (missing section) vs "misconfigured" (present but invalid)

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Terminal width too narrow for merge chain | Medium | Low | Use Rich responsive layout; fall back to compact format |
| GitHub URLs change | Low | Medium | Use constant for base URL; easy to update |
| Users run doctor before any init | Medium | Low | Handled by AC-09 (suggest init) |

### Assumptions

1. Rich library is already a dependency (confirmed: used in all CLI commands)
2. `get_user_config_dir()` and `get_project_config_dir()` are available in `paths.py` (confirmed)
3. Config loaders (`load_yaml_config`, `load_secrets_to_env`) can be called for inspection without side effects (needs verification - may need read-only variants)
4. Terminal supports clickable hyperlinks (graceful degradation: display URL as text)

---

## Open Questions

1. **Q1**: Should `fs2 doctor --json` provide machine-readable output for CI/automation?
   - *Decision*: **Deferred** - focus on human-readable first; add --json in future iteration

2. **Q2**: Should doctor warn about literal secrets in config files (security check)?
   - *Decision*: **Yes** - include `sk-*` prefix detection and >64 char string warnings per PL-07

3. **Q3**: How should `fs2 init` handle existing global config?
   - *Decision*: **Skip silently** - if global exists, just skip it and continue with local; report "Skipped global (already exists)"

---

## ADR Seeds (Optional)

### Decision Drivers
- Must work in terminals without hyperlink support (iTerm2, Windows Terminal support links; basic terminals don't)
- Must not trigger singleton creation (per PL-01)
- Example configs must ship with uvx package (not require separate download)

### Candidate Alternatives
- **A**: Doctor as standalone command (chosen) - simple, focused
- **B**: Doctor as subcommand of `fs2 config doctor` - more organized but deeper nesting
- **C**: Doctor integrated into `fs2 init --check` - conflates creation with diagnosis

### Stakeholders
- End users setting up fs2 for first time
- AI agent operators configuring fs2 via uvx
- CI/CD pipelines needing config validation

---

## Output Mockup

```
$ fs2 doctor

╭─ fs2 Configuration Health Check ─────────────────────────────────────────────╮
│                                                                               │
│  Current Directory: /home/user/my-project                                     │
│                                                                               │
╰───────────────────────────────────────────────────────────────────────────────╯

📁 Configuration Files:
  ✓ ~/.config/fs2/config.yaml
  ✓ ~/.config/fs2/secrets.env
  ✓ ./.fs2/config.yaml
  ✗ ./.fs2/secrets.env (not found)
  ✓ ./.env

⛓️  Merge Chain (lowest → highest priority):
  ┌─ Defaults ──────────────────────────────────────────────────────────────────┐
  │  scan.max_file_size_kb = 500                                                │
  ├─ ~/.config/fs2/config.yaml ─────────────────────────────────────────────────┤
  │  embedding.mode = "azure"                                                   │
  │  embedding.dimensions = 1024                                                │
  ├─ ./.fs2/config.yaml ────────────────────────────────────────────────────────┤
  │  ⚠️  scan.max_file_size_kb = 1000  (overrides central: 500)                 │
  ├─ Environment (FS2_*) ───────────────────────────────────────────────────────┤
  │  FS2_LLM__PROVIDER = "azure"                                                │
  └─────────────────────────────────────────────────────────────────────────────┘

🔌 Provider Status:
  ✓ LLM: azure (configured)
  ✗ Embeddings: NOT CONFIGURED
    → https://github.com/AI-Substrate/flow_squared/blob/main/docs/how/embeddings/2-configuration.md

🔐 Secrets & Placeholders:
  ✓ ${AZURE_OPENAI_API_KEY} → resolved
  ✗ ${AZURE_EMBEDDING_API_KEY} → NOT FOUND
    → https://github.com/AI-Substrate/flow_squared/blob/main/docs/how/secrets.md

⚠️  Warnings:
  • Local config overrides 1 central value (scan.max_file_size_kb)
  • Missing: ./.fs2/secrets.env

💡 Suggestions:
  • Set AZURE_EMBEDDING_API_KEY to enable embeddings
```

---

## Testing Strategy

**Approach**: Full TDD

**Rationale**: User selected comprehensive testing for this diagnostic command.

**Focus Areas**:
- Config file discovery (all 5 locations)
- Merge chain computation and override detection
- Provider status detection (LLM/embeddings)
- Placeholder resolution validation
- Rich output formatting
- Exit code logic (0 vs 1)

**Excluded**: N/A - full coverage

**Mock Usage**: Avoid mocks entirely - use real data/fixtures and existing fakes (e.g., `FakeConfigurationService`). Create temp directories with actual config files for file discovery tests.

---

## Documentation Strategy

**Location**: README.md only

**Rationale**: Quick-start essentials; doctor is a simple diagnostic command users discover from README.

**Content**:
- Add `fs2 doctor` to README command list
- Brief description of what it checks
- Example output snippet (abbreviated)

**Target Audience**: New users setting up fs2, troubleshooting configuration

**Maintenance**: Update when doctor gains new checks

---

## Clarifications

### Session 2026-01-02

**Q1: Testing Strategy**
- **Question**: What testing approach best fits this feature?
- **Answer**: A (Full TDD)
- **Rationale**: Comprehensive unit/integration tests for diagnostic command
- **Updated**: Testing Strategy section added

**Q2: Mock Usage**
- **Question**: How should mocks/stubs/fakes be used?
- **Answer**: A (Avoid mocks entirely)
- **Rationale**: Use real data/fixtures and existing fakes; aligns with fs2 patterns
- **Updated**: Mock Usage field in Testing Strategy

**Q3: Documentation Strategy**
- **Question**: Where should documentation live?
- **Answer**: A (README.md only)
- **Rationale**: Quick-start essentials; simple diagnostic command
- **Updated**: Documentation Strategy section added

**Q4: Literal Secret Detection**
- **Question**: Should doctor warn about literal secrets in config files?
- **Answer**: A (Yes - detect `sk-*` prefix and >64 char strings)
- **Rationale**: Security best practice; patterns already exist in codebase per PL-07
- **Updated**: AC-13 added, Open Questions Q2 resolved

**Q5: Init Behavior**
- **Question**: How should `fs2 init` handle global config setup?
- **Answer**: `fs2 init` does both local AND global in one command. If global exists, skip silently. No `--global` flag needed.
- **Rationale**: Users shouldn't need to understand config hierarchy internals. One command does everything.
- **Updated**: AC-14-19 rewritten, `--global` flag removed, simpler UX

---

*Specification ready for architecture phase.*
