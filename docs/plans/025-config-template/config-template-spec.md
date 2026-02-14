# Config Template for fs2 init

**Mode**: Simple

> This specification incorporates findings from research-dossier.md

## Research Context

- **Components affected**: `DEFAULT_CONFIG` string literal in `src/fs2/cli/init.py` (lines 18-35), plus 3 `.example` file copies
- **Critical dependencies**: None — pure template string change, no logic changes
- **Modification risks**: Low — `DEFAULT_CONFIG` has no consumers other than `init()`. YAML date-like values must be quoted.
- **Link**: See [research-dossier.md](./research-dossier.md) for full analysis

## Summary

When a user runs `fs2 init`, the generated `config.yaml` contains only scan settings. Users have no guidance on how to configure LLM or embedding providers. The goal is to expand the template with commented-out worked examples for Azure AI Foundry (with API key and with `az login`) and OpenAI, so new users can see how things work and uncomment the block they need.

## Goals

- New users see fully worked LLM config examples (Azure key, Azure AD, OpenAI) in their config.yaml after `fs2 init`
- New users see fully worked embedding config examples (Azure key, Azure AD, OpenAI-compatible) in their config.yaml
- Azure AD keyless auth (`az login`) is shown as a first-class option with install instructions
- All examples use `${ENV_VAR}` placeholders to teach the env-var pattern and prevent hardcoded secrets
- Date-like YAML values are properly quoted to avoid parsing gotchas
- The 3 `.example` file copies are updated to match

## Non-Goals

- No changes to config loading, validation, or parsing logic
- No changes to the `init()` function behavior (file creation, force flag, gitignore)
- No addition of `search`, `smart_content`, `graph`, `other_graphs`, or `watch` sections (YAGNI)
- No Jinja2 templating or external file loading — keep it as a string literal
- No separate templates for local vs global config

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=1, I=0, D=0, N=0, F=0, T=0
- **Confidence**: 0.95
- **Assumptions**: String literal change only; no logic changes needed; existing tests don't assert on template content
- **Dependencies**: None
- **Risks**: YAML date-parsing gotcha (mitigated by quoting all date-like values)
- **Phases**: Single phase — update template string + sync example files

## Acceptance Criteria

1. After `fs2 init` on a clean directory, `~/.config/fs2/config.yaml` contains commented-out LLM examples for Azure (API key), Azure (az login), and OpenAI
2. After `fs2 init`, config.yaml contains commented-out embedding examples for Azure (API key), Azure (az login), and OpenAI-compatible
3. The Azure AD examples include `# Requires: pip install fs2[azure-ad] && az login`
4. All `api_version` and `azure_api_version` values are quoted strings (e.g., `"2024-12-01-preview"`)
5. All API key values use `${ENV_VAR}` placeholder syntax
6. The scan section remains active (not commented out) with the same defaults as today
7. `docs/how/user/config.yaml.example` and `src/fs2/docs/config.yaml.example` are updated to match
8. All existing tests pass without modification

## Risks & Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| YAML date parsing of unquoted api_version | Medium | Medium | Quote all date-like values in template |
| Existing tests assert on DEFAULT_CONFIG content | Low | Low | Research shows no tests assert on template content |
| Template becomes stale as config options evolve | Low | Low | Template shows minimal required fields only |

**Assumptions**:
- Same template is acceptable for both local and global config (per research Option A)
- Users prefer seeing examples in their config file over being pointed to separate docs

## Open Questions

None — workshop resolved all design questions.

## Workshop Completed

| Topic | Type | Status |
|-------|------|--------|
| [config.yaml template content](./workshops/config-yaml-template.md) | Storage Design | Draft |
