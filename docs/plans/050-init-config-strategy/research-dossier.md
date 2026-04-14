# Research Report: fs2 init config generation strategy

**Generated**: 2026-04-14T08:30:00Z
**Research Query**: "fs2 init keeps creating bung configs — what should local vs global contain?"
**Mode**: Pre-Plan
**Location**: `docs/plans/050-init-config-strategy/research-dossier.md`
**FlowSpace**: Not Available
**Findings**: 12

## Executive Summary

### What's Happening
`fs2 init` writes the **same bloated 138-line template** to both the project config (`.fs2/config.yaml`) and the user config (`~/.config/fs2/config.yaml`). This template includes active (uncommented) `smart_content:` and `embedding:` sections that assume Ollama and local embeddings are available. If Ollama is detected, it gets even more opinionated by auto-uncommenting the `llm:` block. Users without these tools get confusing behavior on first scan, and everyone has to edit the generated config to match their actual setup.

### The Core Problem
**There is no separation of concerns between project and user config.** They should serve different roles:
- **Project config** (`.fs2/config.yaml`): What to scan in THIS repo. Committed to git. Shared by team.
- **User config** (`~/.config/fs2/config.yaml`): How I connect to LLM/embedding providers. Personal. Not committed.

Currently both get the same everything-and-the-kitchen-sink template.

### Key Insights
1. **Scan works fine with just `scan:` section** — smart content and embeddings are fully optional. The scan CLI already handles missing LLM/embedding config gracefully with "not configured" messages.
2. **The global config should own LLM/embedding/provider settings** — these are per-user (API keys, endpoints, Ollama preference). They shouldn't be in the project config at all.
3. **The project config should be minimal** — just `scan:` section (paths, ignores, gitignore). Maybe `graph:` path. Everything else is comments/docs.
4. **Ollama auto-detection is good UX but wrong location** — detecting Ollama and auto-configuring is nice, but it should go in the USER config, not the project config.

## How It Currently Works

### Init Flow
```
fs2 init
  ├─ Write ~/.config/fs2/config.yaml  ← DEFAULT_CONFIG (138 lines, if not exists)
  ├─ Detect Ollama → auto-uncomment llm: block
  ├─ Write .fs2/config.yaml           ← SAME DEFAULT_CONFIG (with Ollama edits)
  └─ Write .fs2/.gitignore
```

### DEFAULT_CONFIG Active Sections (uncommented)
| Section | Lines | Purpose | Should be in project? | Should be in user? |
|---------|-------|---------|----------------------|-------------------|
| `scan:` | 22-32 | Scan paths, ignores, gitignore | ✅ YES | ❌ NO (defaults are fine) |
| `smart_content:` | 74-79 | Worker count, token limits, categories | ❌ NO | ⚠️ Maybe (advanced tuning) |
| `embedding:` | 85-91 | `mode: local`, `dimensions: 384` | ❌ NO | ✅ YES |

### Config Precedence (from service.py)
```
Defaults → User YAML → Project YAML → Env vars
                ↑ lowest         ↑ highest
```
Project overrides user. So if both have `embedding:`, project wins. This means project config shouldn't have provider settings — they'd override the user's personal setup.

## What Happens Without Each Section

| Missing Section | Result | Source |
|----------------|--------|--------|
| No `scan:` | Uses defaults: `scan_paths=["."]`, `respect_gitignore=true` | `ScanConfig` Pydantic defaults |
| No `llm:` | Smart content skipped: "not configured (no llm section)" | `scan.py:612-665` |
| No `smart_content:` | Smart content skipped: "not configured" | `scan.py:612-665` |
| No `embedding:` | Embeddings skipped: "not configured" | `scan.py:676-697` |
| No `graph:` | Uses default: `.fs2/graph.pickle` | `GraphConfig` defaults |

**Bottom line**: A project config with ONLY `scan:` produces a perfectly working `fs2 scan` that discovers files, parses them, and saves the graph. Smart content and embeddings are bonus features.

## Recommended Config Strategy

### Project Config (`.fs2/config.yaml`) — MINIMAL
What to scan. Committed to git. Shared by team.

```yaml
# fs2 project configuration
# Provider settings (LLM, embeddings) go in ~/.config/fs2/config.yaml

scan:
  scan_paths:
    - "."
  ignore_patterns:
    - "node_modules"
    - ".venv"
    - "*.pyc"
    - "__pycache__"
  respect_gitignore: true
  max_file_size_kb: 500
```

That's it. ~12 lines. No LLM, no embedding, no smart content. Just what to scan.

### User Config (`~/.config/fs2/config.yaml`) — PERSONAL PROVIDERS
How I connect to services. NOT committed. Personal to each developer.

```yaml
# fs2 user configuration — personal provider settings
# Project-specific settings go in .fs2/config.yaml

# ─── LLM (for smart content) ────────────────────────────
# Uncomment ONE provider:

# Local (Ollama):
# llm:
#   provider: local
#   base_url: http://localhost:11434
#   model: qwen2.5-coder:7b

# Azure:
# llm:
#   provider: azure
#   base_url: https://YOUR-RESOURCE.openai.azure.com/
#   azure_deployment_name: gpt-4o
#   azure_api_version: "2024-12-01-preview"
#   model: gpt-4o

# OpenAI:
# llm:
#   provider: openai
#   api_key: ${OPENAI_API_KEY}
#   model: gpt-4o

# ─── Embedding (for semantic search) ────────────────────
# Default: local embeddings (no API key needed)
# embedding:
#   mode: local
#   dimensions: 384

# Azure:
# embedding:
#   mode: azure
#   dimensions: 1024
#   azure:
#     endpoint: https://YOUR-RESOURCE.openai.azure.com/
#     deployment_name: text-embedding-3-small
#     api_version: "2024-02-01"
```

If Ollama is detected, auto-uncomment the local LLM block HERE.

### What Changes in Init

| Current | Proposed |
|---------|----------|
| Same DEFAULT_CONFIG → both locations | Two separate templates |
| `smart_content:` active in project | Removed from project template |
| `embedding:` active in project | Removed from project template |
| Ollama auto-config → project config | Ollama auto-config → user config |
| 138 lines per config | ~12 lines project, ~40 lines user |

## Critical Discoveries

### 🚨 CD-01: Project config overrides user config for providers
**Impact**: Critical
**What**: Because project YAML overrides user YAML in the merge, any `embedding:` or `llm:` in the project config overrides the user's personal provider settings. If a team commits `.fs2/config.yaml` with `embedding: mode: local`, it forces ALL team members to use local embeddings even if they have Azure configured in their user config.
**Required Action**: Remove provider settings from project config template entirely.

### 🚨 CD-02: Ollama detection writes to wrong config
**Impact**: High
**What**: `_detect_ollama()` auto-uncomments the LLM block in the project config (line 248-260). This means a personal tool choice (Ollama) gets committed to the project's git history.
**Required Action**: Move Ollama auto-detection to user config creation only.

### ⚠️ CD-03: Active `embedding: mode: local` causes confusion
**Impact**: High
**What**: The template has `embedding: mode: local` and `dimensions: 384` active. On first scan, fs2 tries to download the BGE model (~130MB). Users who just want to scan files are surprised by a model download.
**Required Action**: Make embedding commented-out in both templates. Users opt-in.

### ⚠️ CD-04: `smart_content:` section is active but useless without LLM
**Impact**: Medium
**What**: `smart_content:` with `enabled_categories: ["file"]` is uncommented, but does nothing without a configured LLM. It's confusing clutter.
**Required Action**: Remove from project template. Move to user template as commented reference.

## Modification Considerations

### ✅ Safe to Modify
- `DEFAULT_CONFIG` string in `init.py` — it's a template, not runtime config
- `init()` function — just file creation logic
- The global config is only written if it doesn't exist (line 221)

### ⚠️ Modify with Caution
- Existing users who already have configs — `init` skips if files exist, so this only affects new projects / `--force`
- Ollama detection logic — still useful, just needs to target the right file

## Recommendations

### Immediate Fix (this plan)
1. Split `DEFAULT_CONFIG` into `PROJECT_CONFIG` and `USER_CONFIG` templates
2. Project: scan-only (~12 lines)
3. User: provider references, all commented, Ollama auto-uncomment
4. Keep `--force` flag for re-creating project config
5. Add `--global` flag to re-create user config

### Future Enhancement
- `fs2 init --provider azure` interactive setup that asks for endpoint/deployment
- `fs2 config set llm.provider azure` for key-value updates
- Validation in doctor for "you have smart_content configured but no LLM provider"

## Next Steps

- Run `/plan-1b-specify` to create the specification
- This is likely CS-2 (small) — one file change (init.py), two template strings

---

**Research Complete**: 2026-04-14T08:32:00Z
**Report Location**: docs/plans/050-init-config-strategy/research-dossier.md
