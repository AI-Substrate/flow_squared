# Workshop: config.yaml Template for New Users

**Type**: Storage Design
**Plan**: 025-config-template
**Research**: [research-dossier.md](../research-dossier.md)
**Created**: 2026-02-14
**Status**: Draft

---

## Purpose

Define exactly what a new user sees in `config.yaml` after running `fs2 init`. The file should be self-documenting — a user can uncomment the right block and start working.

## Key Questions Addressed

- What does the config.yaml look like when a user first opens it?
- How do we show Azure AI Foundry (with key), Azure AI Foundry (with az login), and OpenAI?
- How do we handle the embedding section alongside the LLM section?

---

## The File

This is the exact content that `DEFAULT_CONFIG` in `init.py` will produce. A new user opens `~/.config/fs2/config.yaml` (or `.fs2/config.yaml`) and sees this:

```yaml
# fs2 configuration file
# Full docs: https://github.com/AI-Substrate/flow_squared

scan:
  scan_paths:
    - "."
  respect_gitignore: true
  max_file_size_kb: 500
  follow_symlinks: false

# ─── LLM (for smart content) ───────────────────────────────────────
# Uncomment ONE block below. Required for: fs2 scan --smart-content
#
# Azure AI Foundry (API key):
# llm:
#   provider: azure
#   api_key: ${AZURE_OPENAI_API_KEY}
#   base_url: https://YOUR-RESOURCE.openai.azure.com/
#   azure_deployment_name: gpt-4o
#   azure_api_version: "2024-12-01-preview"
#   model: gpt-4o
#
# Azure AI Foundry (az login — no API key needed):
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

# ─── Embedding (for semantic search) ──────────────────────────────
# Uncomment ONE block below. Required for: fs2 scan --embed
#
# Azure AI Foundry (API key):
# embedding:
#   mode: azure
#   dimensions: 1024
#   azure:
#     endpoint: https://YOUR-RESOURCE.openai.azure.com/
#     api_key: ${AZURE_EMBEDDING_API_KEY}
#     deployment_name: text-embedding-3-small
#     api_version: "2024-02-01"
#
# Azure AI Foundry (az login — no API key needed):
# embedding:
#   mode: azure
#   dimensions: 1024
#   azure:
#     endpoint: https://YOUR-RESOURCE.openai.azure.com/
#     deployment_name: text-embedding-3-small
#     api_version: "2024-02-01"
#   # Requires: pip install fs2[azure-ad] && az login
#
# OpenAI-compatible:
# embedding:
#   mode: openai_compatible
#   dimensions: 1024
#   openai_compatible:
#     endpoint: https://api.openai.com/v1
#     api_key: ${OPENAI_API_KEY}
#     model: text-embedding-3-small
```

---

## Design Decisions

### D1: api_version values are quoted

```yaml
azure_api_version: "2024-12-01-preview"  # ✅ Quoted — treated as string
azure_api_version: 2024-12-01-preview    # ❌ YAML parses as date object
```

YAML spec treats unquoted `2024-02-01` as a date. Always quote.

### D2: No optional fields in examples

The examples show only **required** fields per provider. Optional fields like `temperature`, `max_tokens`, `timeout`, `max_retries` are omitted — they have good defaults and add clutter.

A user who needs them can check the docs or the `.example` files.

### D3: `${ENV_VAR}` placeholders instead of dummy values

```yaml
api_key: ${AZURE_OPENAI_API_KEY}    # ✅ Shows the env var pattern
api_key: sk-your-key-here           # ❌ Looks like a real key, invites hardcoding
```

fs2 supports env var expansion in YAML. Teaching users this pattern upfront prevents secrets in config files.

### D4: Same file for local and global config

Both `.fs2/config.yaml` and `~/.config/fs2/config.yaml` get the same content. The global one typically holds LLM/embedding creds, the local one typically holds scan paths. The commented examples serve as documentation regardless of which file the user edits.

### D5: Section separators use Unicode box-drawing

```
# ─── LLM (for smart content) ───────────────────────────────────────
```

Visually separates sections. Easy to scan. Grep-friendly. The `───` characters are widely supported in modern terminals and editors.

### D6: "az login" variant shown as a peer option

Not hidden in a footnote or sub-comment. Azure AD keyless auth is a first-class path, shown right next to API key auth. The `# Requires: pip install fs2[azure-ad] && az login` line tells users exactly what to do.

---

## What Changed vs. Current

| Aspect | Current (17 lines) | New (~55 lines) |
|--------|-------------------|-----------------|
| scan section | Active, with comments | Same |
| LLM section | Missing | 3 commented examples (Azure key, Azure AD, OpenAI) |
| Embedding section | Missing | 3 commented examples (Azure key, Azure AD, OpenAI-compatible) |
| Azure AD auth | Missing | Shown as first-class option with install instructions |
| Section headers | None | Unicode box-drawing separators |
| Docs link | `docs/how/scanning.md` | GitHub URL (works outside repo) |

---

## Sections NOT Included (YAGNI)

These sections exist in the config system but are **not** shown in the init template:

| Section | Why Excluded |
|---------|-------------|
| `search:` | Has good defaults, rarely customized |
| `smart_content:` | Has good defaults, rarely customized |
| `graph:` | Only for non-standard graph paths |
| `other_graphs:` | Advanced multi-repo feature |
| `watch:` | Experimental |

Users who need these can find them in `docs/how/user/config.yaml.example`.
