# Research Report: Config Template for fs2 init

**Generated**: 2026-02-14
**Research Query**: "Ensure fs2 init creates config.yaml with full worked examples of Azure AI Foundry and OpenAI config (commented out)"
**Mode**: Pre-Plan
**Location**: docs/plans/025-config-template/research-dossier.md
**FlowSpace**: Not Available (graph not built in worktree)
**Findings**: 20 (deduplicated from 38 raw findings)

## Executive Summary

### What It Does
`fs2 init` creates a minimal `config.yaml` (scan section only) in both `.fs2/` and `~/.config/fs2/`. Rich example files with Azure/OpenAI configs **already exist** in the codebase but are NOT used by `fs2 init`.

### Business Purpose
New users run `fs2 init` and get a config with no guidance on LLM/embedding setup. They must discover example files or docs separately. The goal is to make the generated config self-documenting with commented-out worked examples.

### Key Insights
1. `DEFAULT_CONFIG` is a 17-line string literal in `src/fs2/cli/init.py` — only `scan` section
2. `docs/how/user/config.yaml.example` (117 lines) already has Azure + OpenAI examples — but init doesn't use it
3. The example files are missing Azure AD (keyless) auth examples — our az-login work isn't reflected yet
4. Same template goes to both local and global config — but they serve different purposes (local=project, global=user defaults)

### Quick Stats
- **Files to modify**: 1-3 (init.py template, possibly example files)
- **Config classes**: 12 registered in `YAML_CONFIG_TYPES`
- **Example files**: 3 copies (`.fs2/`, `docs/how/user/`, `src/fs2/docs/`)
- **Prior learnings**: 10 relevant discoveries from previous plans
- **Complexity**: CS-2 (small) — template string change, no logic changes

---

## How It Currently Works

### Entry Point
| Entry Point | Type | Location | Purpose |
|------------|------|----------|---------|
| `fs2 init` | CLI Command | `src/fs2/cli/init.py:init()` | Creates local + global config |

### Core Execution Flow

1. **CLI dispatch**: `src/fs2/cli/main.py` registers `init` as unguarded command (no `@require_init`)
2. **Path resolution**: `init()` computes `cwd/.fs2/config.yaml` and `~/.config/fs2/config.yaml` via `get_user_config_dir()`
3. **Global config**: If `~/.config/fs2/config.yaml` doesn't exist → `mkdir -p` + `write_text(DEFAULT_CONFIG)`
4. **Local config**: If `.fs2/config.yaml` doesn't exist (or `--force`) → create dir + `write_text(DEFAULT_CONFIG)` + write `.gitignore`
5. **Report**: Print actions list, suggest `fs2 scan`

### Current DEFAULT_CONFIG Template (17 lines)

```python
# File: src/fs2/cli/init.py, lines 18-35
DEFAULT_CONFIG = """\
# fs2 configuration file
# See docs/how/scanning.md for all options

scan:
  # Directories to scan (relative to project root)
  scan_paths:
    - "."

  # Respect .gitignore patterns
  respect_gitignore: true

  # Maximum file size to parse (in KB)
  max_file_size_kb: 500

  # Follow symbolic links
  follow_symlinks: false
"""
```

### Existing Example Files (NOT used by init)

| File | Lines | Content | Used By Init? |
|------|-------|---------|---------------|
| `.fs2/config.yaml.example` | 145 | Full architecture docs + legacy `azure.openai` section | No |
| `docs/how/user/config.yaml.example` | 117 | Modern examples: Azure, OpenAI, Fake for LLM + Embedding | No |
| `src/fs2/docs/config.yaml.example` | 117 | Identical to docs/ copy (bundled in wheel) | No |

### What the Example Files Already Cover

From `docs/how/user/config.yaml.example`:
- `scan` section (active, not commented)
- `llm` section with 3 provider examples (Azure, OpenAI, Fake — all commented out)
- `embedding` section with 3 mode examples (Azure, OpenAI-compatible, Fake — all commented)
- `search` section (commented)
- `smart_content` section (commented)

### What's MISSING from Example Files
- **Azure AD (keyless) auth** — no example of `api_key: null` with `pip install fs2[azure-ad]` note
- **`graph` section** — not shown in examples
- **`other_graphs` section** — not shown in examples
- **`watch` section** — not shown in examples

---

## Config Model Reference

### LLMConfig (`llm:`)

| Field | Type | Default | Required |
|-------|------|---------|----------|
| `provider` | `"azure" \| "openai" \| "fake"` | — | Yes |
| `api_key` | `str \| None` | `None` | No (Azure AD fallback if None + azure-identity installed) |
| `base_url` | `str \| None` | `None` | Yes for Azure |
| `azure_deployment_name` | `str \| None` | `None` | Yes for Azure |
| `azure_api_version` | `str \| None` | `None` | Yes for Azure |
| `model` | `str \| None` | `None` | No |
| `temperature` | `float` | `0.1` | No |
| `max_tokens` | `int` | `1024` | No |
| `timeout` | `int` | `30` | No (1-120) |
| `max_retries` | `int` | `3` | No |

### EmbeddingConfig (`embedding:`)

| Field | Type | Default |
|-------|------|---------|
| `mode` | `"azure" \| "openai_compatible" \| "fake"` | `"azure"` |
| `dimensions` | `int` | `1024` |
| `batch_size` | `int` | `16` |
| `azure.endpoint` | `str` | — (required) |
| `azure.api_key` | `str \| None` | `None` |
| `azure.deployment_name` | `str` | `"text-embedding-3-small"` |
| `azure.api_version` | `str` | `"2024-02-01"` |

### SmartContentConfig (`smart_content:`)

| Field | Type | Default |
|-------|------|---------|
| `max_workers` | `int` | `50` |
| `max_input_tokens` | `int` | `50000` |
| `token_limits` | `dict[str, int]` | file:200, type:200, callable:150, etc. |

---

## Prior Learnings (From Previous Implementations)

### PL-01: YAML gotcha — unquoted date-like strings parsed as datetime
**Source**: Plan 009 (Embeddings)
**Action**: Always quote `api_version` values in YAML examples: `"2024-02-01"` not `2024-02-01`

### PL-02: Template packaging requires explicit Hatch config
**Source**: Plans 008, 017
**Action**: If we use a .yaml template file instead of string literal, it must be added to `pyproject.toml` Hatch includes

### PL-03: `importlib.resources.files()` needs `__init__.py` in all parents
**Source**: Plans 008, 014
**Action**: If loading template from package, ensure directory has `__init__.py`

### PL-04: Config validation failures should be loud
**Source**: Plan 023
**Action**: Commented-out sections won't trigger validation — only active sections do

### PL-05: Same DEFAULT_CONFIG goes to both local and global
**Source**: Plan 017
**Action**: Consider whether local and global should have different templates (local = project scan only, global = user LLM/embedding defaults)

### PL-06: `.fs2/config.yaml.example` has chicken-and-egg problem
**Source**: Plan 002, 017
**Action**: Having example in `.fs2/` looks like a real config — the canonical location moved to `docs/how/user/`

---

## Modification Considerations

### Safe to Modify
1. **`DEFAULT_CONFIG` in `src/fs2/cli/init.py`** — String literal, no consumers other than init. Change template content freely.
2. **`docs/how/user/config.yaml.example`** — Documentation file, no runtime consumers.
3. **`src/fs2/docs/config.yaml.example`** — Bundled copy, keep in sync with docs/ version.

### Design Decision: One Template or Two?

**Option A: Single rich template** — Same comprehensive template for both local and global config.
- Pro: Simple, consistent
- Con: Local project config gets bloated with LLM/embedding examples that belong in global

**Option B: Two templates** — Minimal local (scan only) + comprehensive global (LLM/embedding examples)
- Pro: Correct separation — LLM keys belong in global, scan paths in local
- Con: More code to maintain, two templates to keep in sync

**Option C: Rich local, skip global if exists** — One comprehensive template for local, keep current "skip if exists" for global
- Pro: Users see examples on first project init
- Con: Global config stays minimal forever after first init

**Recommendation**: Option A is simplest and matches KISS/YAGNI. Users edit the one file they find. The commented-out examples serve as documentation regardless of location.

---

## Critical Discoveries

### 01: Example files exist but init doesn't use them
**Impact**: Critical
**What**: Three `.example` files have comprehensive configs but `fs2 init` writes a minimal 17-line string
**Required Action**: Either make init use the example files, or expand the `DEFAULT_CONFIG` string

### 02: Azure AD auth not in any example file
**Impact**: High
**What**: After our az-login work, `api_key` is now optional for Azure. No example shows keyless auth.
**Required Action**: Add Azure AD example to template showing `api_key` omitted + comment about `pip install fs2[azure-ad]`

### 03: Date-like YAML values must be quoted
**Impact**: Medium
**What**: `api_version: 2024-02-01` gets parsed as `datetime.date`. Must be `"2024-02-01"`.
**Required Action**: Ensure all date-like values in template are quoted strings

### 04: Three example file copies must stay in sync
**Impact**: Medium
**What**: `.fs2/config.yaml.example`, `docs/how/user/config.yaml.example`, `src/fs2/docs/config.yaml.example`
**Required Action**: Update all three when changing template content (or consolidate)

---

## Recommendations

### Implementation Approach
1. Expand `DEFAULT_CONFIG` in `init.py` to include commented-out Azure AI Foundry and OpenAI examples
2. Include Azure AD (keyless) auth as a variant
3. Update the three `.example` files to match
4. Keep it simple — string literal is fine, no need for Jinja2 or file loading

### Template Structure (Proposed)
```yaml
# fs2 configuration file

scan:
  scan_paths:
    - "."
  respect_gitignore: true
  max_file_size_kb: 500
  follow_symlinks: false

# --- LLM Configuration ---
# Uncomment ONE provider block below.
#
# Azure AI Foundry (with API key):
# llm:
#   provider: azure
#   api_key: ${AZURE_OPENAI_API_KEY}
#   base_url: https://YOUR-RESOURCE.openai.azure.com/
#   azure_deployment_name: gpt-4o
#   azure_api_version: "2024-12-01-preview"
#   model: gpt-4o
#
# Azure AI Foundry (with az login — no API key):
# llm:
#   provider: azure
#   base_url: https://YOUR-RESOURCE.openai.azure.com/
#   azure_deployment_name: gpt-4o
#   azure_api_version: "2024-12-01-preview"
#   model: gpt-4o
#   # Requires: pip install fs2[azure-ad] && az login
#
# OpenAI:
# llm:
#   provider: openai
#   api_key: ${OPENAI_API_KEY}
#   model: gpt-4o

# --- Embedding Configuration ---
# ...similar pattern...
```

---

## Next Steps

- Run `/plan-1b-specify` to create specification
- Implementation is CS-2 (small) — string literal change + example file updates

---

**Research Complete**: 2026-02-14
**Report Location**: docs/plans/025-config-template/research-dossier.md
