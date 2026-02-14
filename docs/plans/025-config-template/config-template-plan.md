# Config Template for fs2 init — Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-02-14
**Spec**: [./config-template-spec.md](./config-template-spec.md)
**Workshop**: [./workshops/config-yaml-template.md](./workshops/config-yaml-template.md)
**Research**: [./research-dossier.md](./research-dossier.md)
**Status**: DRAFT

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Testing Philosophy](#testing-philosophy)
4. [Implementation](#implementation)
5. [Change Footnotes Ledger](#change-footnotes-ledger)

## Executive Summary

When a user runs `fs2 init`, the generated `config.yaml` contains only a 17-line scan section
with no guidance on LLM or embedding configuration. Users must discover example files or docs
separately. The fix is simple: expand the `DEFAULT_CONFIG` string literal in `init.py` to
include commented-out worked examples for Azure AI Foundry (API key + az login) and OpenAI,
using the exact template designed in the [workshop](./workshops/config-yaml-template.md).
Then sync the two `.example` reference files to include Azure AD examples and quoted
`api_version` values.

## Critical Research Findings

Sourced from [research-dossier.md](./research-dossier.md) and [workshop](./workshops/config-yaml-template.md).

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | `DEFAULT_CONFIG` is a 17-line string literal at `init.py:18-35` — only consumer is `init()` | Replace string directly; no other code affected |
| 02 | Critical | `api_version: 2024-02-01` is parsed as `datetime.date` by YAML spec | Quote ALL date-like values: `"2024-02-01"` |
| 03 | High | Azure AD (keyless) auth not shown in any example file | Add Azure AD variant with `# Requires: pip install fs2[azure-ad] && az login` |
| 04 | High | Existing tests only check `scan_paths` and `respect_gitignore` in config content (no exact template assertions) | All existing tests pass unchanged with expanded template |
| 05 | High | `docs/how/user/config.yaml.example` and `src/fs2/docs/config.yaml.example` are identical 117-line files — missing Azure AD, unquoted `api_version` | Update both to add Azure AD examples and quote dates |
| 06 | Medium | Same `DEFAULT_CONFIG` goes to both local (`.fs2/`) and global (`~/.config/fs2/`) config | Keep single template per research Option A recommendation |
| 07 | Medium | Workshop document defines exact template content (~55 lines) with 6 design decisions | Use workshop template verbatim — it's the authoritative design |
| 08 | Low | `.fs2/config.yaml.example` (145 lines) exists but is legacy; canonical location is `docs/how/user/` | Not in scope per spec ACs — only update 2 example files |
| 09 | Low | Docs link in current template (`docs/how/scanning.md`) only works inside repo | Workshop changes to GitHub URL for portability |
| 10 | Low | Template shows only required fields per provider — optional fields (`temperature`, `max_tokens`, etc.) omitted per workshop D2 | YAGNI — users check docs for optional fields |

## Testing Philosophy

### Testing Approach

- **Selected Approach**: Full TDD
- **Mock Usage**: Avoid mocks — test real `DEFAULT_CONFIG` string content and YAML parsing
- **Focus Areas**:
  - Template contains all required provider examples (LLM + Embedding)
  - Azure AD variant includes install instructions
  - All `api_version` values are quoted strings
  - `${ENV_VAR}` placeholders used for API keys
  - Scan section remains active with same defaults
  - Template is valid YAML when uncommented
- **Excluded**: Init behavior tests (already well-covered by existing test suite)

### TDD Cycle

1. Write tests FIRST (RED) — tests fail because DEFAULT_CONFIG still has old 17-line content
2. Implement new template (GREEN) — make tests pass
3. Verify no regressions — run full existing test suite

## Implementation (Single Phase)

**Objective**: Expand `DEFAULT_CONFIG` with commented-out LLM and embedding examples per
workshop design, and sync the two `.example` reference files.

**Testing Approach**: Full TDD
**Mock Usage**: Avoid mocks

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|-------------------|------------|-------|
| [x] | T001 | Write tests for `DEFAULT_CONFIG` template content | 1 | Test | -- | /Users/jak/github/fs2-az-login/tests/unit/cli/test_init_cli.py | 6 new tests: (1) contains Azure key LLM example, (2) contains Azure AD LLM example with install instructions, (3) contains OpenAI LLM example, (4) contains Azure embedding examples, (5) all api_version values quoted, (6) API key placeholders use `${ENV_VAR}` syntax. All FAIL (RED). | AC1-AC5 |
| [x] | T002 | Replace `DEFAULT_CONFIG` with workshop-designed template | 1 | Core | T001 | /Users/jak/github/fs2-az-login/src/fs2/cli/init.py | T001 tests pass (GREEN). Existing init tests still pass. | Per workshop template verbatim |
| [x] | T003 | Update `docs/how/user/config.yaml.example` with Azure AD examples and quoted `api_version` | 1 | Core | -- | /Users/jak/github/fs2-az-login/docs/how/user/config.yaml.example | File contains Azure AD LLM example, Azure AD embedding example, all api_version values quoted | AC3, AC4, AC7 |
| [x] | T004 | Sync `src/fs2/docs/config.yaml.example` with updated docs copy | 1 | Core | T003 | /Users/jak/github/fs2-az-login/src/fs2/docs/config.yaml.example | Files are identical | AC7 |
| [x] | T005 | Run full test suite — verify zero regressions | 1 | Verify | T001, T002, T003, T004 | -- | `pytest tests/ -v` passes 100%. All existing tests unchanged and passing. | AC8 |

### Test Examples (Write First — T001)

```python
# tests/unit/cli/test_init_cli.py — new tests for AC1-AC5

import yaml
import pytest


@pytest.mark.unit
class TestDefaultConfigTemplate:
    """Tests for DEFAULT_CONFIG template content (AC1-AC5)."""

    def test_given_default_config_when_parsed_then_contains_azure_key_llm_example(self):
        """
        Purpose: Proves template has Azure API key LLM example.
        Quality Contribution: New users see Azure key-based auth path.
        Acceptance Criteria: Commented section includes provider: azure + api_key.
        """
        from fs2.cli.init import DEFAULT_CONFIG

        assert "# llm:" in DEFAULT_CONFIG
        assert "#   provider: azure" in DEFAULT_CONFIG
        assert "#   api_key: ${AZURE_OPENAI_API_KEY}" in DEFAULT_CONFIG

    def test_given_default_config_when_parsed_then_contains_azure_ad_llm_example(self):
        """
        Purpose: Proves template has Azure AD (az login) LLM example.
        Quality Contribution: Keyless auth shown as first-class option.
        Acceptance Criteria: Azure AD section present with install instructions.
        """
        from fs2.cli.init import DEFAULT_CONFIG

        assert "az login" in DEFAULT_CONFIG
        assert "pip install fs2[azure-ad]" in DEFAULT_CONFIG

    def test_given_default_config_when_parsed_then_contains_openai_llm_example(self):
        """
        Purpose: Proves template has OpenAI LLM example.
        Quality Contribution: OpenAI users can configure quickly.
        Acceptance Criteria: OpenAI provider section with API key placeholder.
        """
        from fs2.cli.init import DEFAULT_CONFIG

        assert "#   provider: openai" in DEFAULT_CONFIG
        assert "#   api_key: ${OPENAI_API_KEY}" in DEFAULT_CONFIG

    def test_given_default_config_when_parsed_then_contains_embedding_examples(self):
        """
        Purpose: Proves template has embedding configuration examples.
        Quality Contribution: Users see how to enable semantic search.
        Acceptance Criteria: Azure and OpenAI-compatible embedding sections present.
        """
        from fs2.cli.init import DEFAULT_CONFIG

        assert "# embedding:" in DEFAULT_CONFIG
        assert "#   mode: azure" in DEFAULT_CONFIG
        assert "#   mode: openai_compatible" in DEFAULT_CONFIG

    def test_given_default_config_when_parsed_then_api_versions_are_quoted(self):
        """
        Purpose: Proves all api_version values are quoted strings.
        Quality Contribution: Prevents YAML date-parsing gotcha.
        Acceptance Criteria: api_version lines use quoted values.
        """
        from fs2.cli.init import DEFAULT_CONFIG

        # Find all api_version lines and verify they're quoted
        for line in DEFAULT_CONFIG.splitlines():
            stripped = line.lstrip("# ").strip()
            if "api_version" in stripped and ":" in stripped:
                value = stripped.split(":", 1)[1].strip()
                assert value.startswith('"') and value.endswith('"'), (
                    f"api_version not quoted: {line.strip()}"
                )

    def test_given_default_config_when_scan_section_parsed_then_valid_yaml(self):
        """
        Purpose: Proves active scan section is valid YAML.
        Quality Contribution: Config won't fail on first use.
        Acceptance Criteria: Scan section parses without error and has expected defaults.
        """
        from fs2.cli.init import DEFAULT_CONFIG

        parsed = yaml.safe_load(DEFAULT_CONFIG)
        assert parsed is not None
        assert "scan" in parsed
        assert parsed["scan"]["scan_paths"] == ["."]
        assert parsed["scan"]["respect_gitignore"] is True
        assert parsed["scan"]["max_file_size_kb"] == 500
        assert parsed["scan"]["follow_symlinks"] is False
```

### Acceptance Criteria

- [x] **AC1**: After `fs2 init`, config.yaml contains commented-out LLM examples for Azure (API key), Azure (az login), and OpenAI
- [x] **AC2**: After `fs2 init`, config.yaml contains commented-out embedding examples for Azure (API key), Azure (az login), and OpenAI-compatible
- [x] **AC3**: Azure AD examples include `# Requires: pip install fs2[azure-ad] && az login`
- [x] **AC4**: All `api_version` and `azure_api_version` values are quoted strings
- [x] **AC5**: All API key values use `${ENV_VAR}` placeholder syntax
- [x] **AC6**: Scan section remains active (not commented out) with same defaults
- [x] **AC7**: `docs/how/user/config.yaml.example` and `src/fs2/docs/config.yaml.example` are updated to match
- [x] **AC8**: All existing tests pass without modification

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| YAML date parsing of unquoted api_version | Medium | Medium | Quote all date-like values in template |
| Existing tests assert on DEFAULT_CONFIG content | Low | Low | Research confirms no tests assert on template content |
| Template becomes stale as config options evolve | Low | Low | Template shows minimal required fields only |

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]
[^3]: [To be added during implementation via plan-6a]
[^4]: [To be added during implementation via plan-6a]

---

**Status**: COMPLETE — All tasks done, all ACs verified.

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "/Users/jak/github/fs2-az-login/docs/plans/025-config-template/config-template-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended for CS-3+ tasks)
