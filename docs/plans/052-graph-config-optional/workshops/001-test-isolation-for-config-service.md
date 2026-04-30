# Workshop: Test Isolation for `FS2ConfigurationService`

**Type**: Integration Pattern
**Plan**: 052-graph-config-optional
**Spec**: [graph-config-optional-spec.md](../graph-config-optional-spec.md)
**Plan**: [graph-config-optional-plan.md](../graph-config-optional-plan.md)
**Created**: 2026-04-30
**Status**: Draft

**Related Documents**:
- Existing patterns: `tests/unit/config/test_configuration_service.py`, `tests/unit/config/test_yaml_loading.py`, `tests/unit/config/test_singleton_pattern.py`
- Source under test: `src/fs2/config/service.py`, `src/fs2/config/paths.py`

---

## Purpose

This workshop nails down **how to write hermetic tests for `FS2ConfigurationService`** so that production behavior (XDG config discovery, project `.fs2/config.yaml` discovery, env var expansion, secrets loading) is exercised end-to-end **without contaminating the developer's actual `~/.config/fs2/`, `~/.fs2/`, or environment**. It is the operational manual for tasks T002–T005 in the plan.

## Key Questions Addressed

1. How does `FS2ConfigurationService` discover config sources? Where can a test slip up and accidentally read the real user's config?
2. What's the existing test isolation pattern, and is it sufficient for testing the new auto-registration mechanism (T001)?
3. What's the canonical fixture/helper for "give me an isolated `FS2ConfigurationService` loaded from this YAML string"?
4. Should T002 use `FS2ConfigurationService` (real loader) or `FakeConfigurationService` (test double)? When does each apply?
5. How do T003/T004/T005 (service-level tests) consume an isolated config without re-implementing the YAML setup boilerplate?

---

## Overview

`FS2ConfigurationService.__init__()` walks four sources in this order:

```
                            FS2ConfigurationService.__init__
                                          │
        ┌─────────────────────────────────┼─────────────────────────────────┐
        ▼                                 ▼                                 ▼
   1. SECRETS                      2. RAW DICTS                     3. MERGED + TYPED
   load secrets into               from each source                 deep-merge in precedence
   os.environ:                                                       order, expand ${VAR}
   - user .env                                                       placeholders, then
   - project .env                                                    create typed config
                                                                     objects from
                                                                     YAML_CONFIG_TYPES
```

Sources discovered (lowest → highest precedence):

| # | Source | Path | Discovery |
|---|---|---|---|
| 1 | Config defaults | (in code) | Pydantic model defaults |
| 2 | User YAML | `${XDG_CONFIG_HOME}/fs2/config.yaml` or `~/.config/fs2/config.yaml` | `get_user_config_dir()` reads `XDG_CONFIG_HOME` env var, falls back to `Path.home()` |
| 3 | Project YAML | `${CWD}/.fs2/config.yaml` | `get_project_config_dir()` returns `Path.cwd() / ".fs2"` |
| 4 | Environment vars | `FS2_*` (e.g. `FS2_GRAPH__GRAPH_PATH`) | Read from `os.environ` during merge |

**Critical for tests**: every one of these sources is influenced by *process state* — `HOME`, `XDG_CONFIG_HOME`, `cwd`, and `FS2_*` env vars. A naive test will read your real `~/.config/fs2/config.yaml` and produce confusing results.

---

## The Existing Pattern (proven, in production tests)

`tests/unit/config/test_configuration_service.py` and `test_yaml_loading.py` already use a clean three-line incantation. Every `FS2ConfigurationService` test starts the same way:

```python
def test_something(self, monkeypatch, tmp_path):
    # ── Hermetic setup (the canonical 3 lines) ──
    monkeypatch.setenv("HOME", str(tmp_path))         # block ~/.config discovery
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)  # block XDG override
    monkeypatch.chdir(tmp_path)                       # isolate project .fs2 discovery
    # ── Now write whatever fixtures you want under tmp_path ──
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(YAML_FIXTURE)

    from fs2.config.service import FS2ConfigurationService
    config = FS2ConfigurationService()
    # ... assertions ...
```

**Why this works**:

| Source | Production path | Test redirect | Effect |
|---|---|---|---|
| `~/.config/fs2/config.yaml` | `Path.home() / ".config" / "fs2"` | `HOME=tmp_path` → `~/.config` becomes `tmp_path/.config` | Discovery looks under tmp_path; finds nothing unless we put it there |
| `$XDG_CONFIG_HOME/fs2/config.yaml` | `Path(os.environ["XDG_CONFIG_HOME"]) / "fs2"` | `XDG_CONFIG_HOME` deleted | Falls through to `HOME` path (already redirected) |
| `./.fs2/config.yaml` | `Path.cwd() / ".fs2"` | `chdir(tmp_path)` | `cwd` is now tmp_path; project config is whatever we write there |
| `FS2_*` env vars | `os.environ` | (handled per-test via `monkeypatch.setenv("FS2_…", …)`) | Each test owns its env state; auto-restored after test |

`monkeypatch` automatically reverts after the test — no leakage to other tests.

---

## Decision Tree: Which Service to Use in Each Test

```
                         ┌──────────────────────────────┐
                         │ What are you testing?         │
                         └──────────────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
   ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
   │ Config LOADING      │  │ Service that USES   │  │ Service-level unit  │
   │ behavior itself     │  │ a typed config and  │  │ test where config   │
   │ (T002 belongs here) │  │ you want end-to-end │  │ is incidental       │
   │                     │  │ proof (T003-T005)   │  │                     │
   └─────────────────────┘  └─────────────────────┘  └─────────────────────┘
              │                        │                        │
              ▼                        ▼                        ▼
   FS2ConfigurationService   FS2ConfigurationService   FakeConfigurationService
   from real YAML fixture    from real YAML fixture    pre-loaded with the
   under tmp_path            under tmp_path            specific config object
                             (proves T001 end-to-end)  (per R4.2 fakes-over-mocks)
```

### When to use `FS2ConfigurationService` (real loader)

- You're testing the **loading pipeline** (auto-registration, YAML merge, env var expansion, secrets loading).
- You want to **prove the new mechanism actually works** when invoked the way production invokes it.
- You're willing to pay ~ms for YAML I/O.

**Use for**: T002 (auto-registration mechanism test) — must use the real loader to prove `_create_config_objects` runs the new fall-through.

### When to use `FakeConfigurationService` (test double)

- You're testing a **service** (e.g., `TreeService.search()`), and config is incidental.
- You want test setup to be a one-liner.
- You don't care about merge precedence / YAML parsing for this test.

**Use for**: most existing tests in `test_tree_service.py`, `test_get_node_service.py`, etc.

### When to use BOTH (hybrid)

T003/T004/T005 in this plan are **service tests** that specifically need to prove "service initializes correctly when YAML omits `graph:`". This requires the **real loader** to actually run the auto-registration. So they cross from "service test" → "config-loading integration test."

**Recommendation**: T003/T004/T005 should use `FS2ConfigurationService` (real loader, real fixture YAML without a `graph:` block) — anything less doesn't prove the behavior under test. This is mildly heavier than the typical service test, but it's the right call for these specific regression tests.

---

## Canonical Fixture: `tmp_fs2_config`

To avoid copy-pasting the 3-line incantation across 4+ new tests, this workshop **proposes** a shared pytest fixture. **Status: design proposal — implementor decides whether to adopt.**

### Proposed location: `tests/conftest.py` (root — visible to all tests under `tests/`)

```python
"""Shared fixtures for config-related tests.

Provides hermetic FS2ConfigurationService construction so tests don't
contaminate (or get contaminated by) the developer's real config.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def isolated_config_env(monkeypatch, tmp_path):
    """Redirect HOME/XDG/cwd to tmp_path so config discovery is hermetic.

    Any test using this fixture will:
      - read from `tmp_path/.config/fs2/config.yaml` for user config
        (won't exist unless the test creates it)
      - read from `tmp_path/.fs2/config.yaml` for project config
        (won't exist unless the test creates it)
      - have no FS2_* env vars unless the test sets them via monkeypatch.setenv

    Returns:
        Path: tmp_path, ready to be populated with `.fs2/config.yaml` etc.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def make_project_config(isolated_config_env):
    """Factory: write a project-level .fs2/config.yaml from a YAML string.

    Usage:
        def test_x(make_project_config):
            make_project_config('''
                scan:
                  scan_paths:
                    - "."
                # NOTE: no graph: section
            ''')
            from fs2.config.service import FS2ConfigurationService
            config = FS2ConfigurationService()
            assert config.require(GraphConfig).graph_path == ".fs2/graph.pickle"
    """
    tmp_path = isolated_config_env

    def _write(yaml_text: str) -> None:
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "config.yaml").write_text(yaml_text)

    return _write
```

### Why this design

- **Two fixtures, separated by responsibility**: `isolated_config_env` does the env-var/cwd dance only; `make_project_config` adds the project YAML write. Tests that don't need a YAML file (e.g., "config service works with no config files") use only the first.
- **No singletons, no module-level state**: each test gets a fresh `tmp_path`.
- **Fixture composes**: `make_project_config` depends on `isolated_config_env`, so any test using the factory automatically gets isolation.
- **Returns a callable**: tests can vary YAML content without re-importing or re-instantiating.

### Should we adopt the fixture?

| Reason to adopt | Reason to skip |
|---|---|
| 4+ new tests benefit; eliminates 3-line copy-paste | Existing tests already inline the pattern — adding a fixture doesn't refactor them, just standardizes new ones |
| Lowers cognitive load for future config tests | Mild dependency footprint (new conftest) |
| Documents the canonical pattern in code | Lightweight scope — keep-it-simple ethos says don't add infrastructure for 4 tests |

**Recommendation**: **Adopt the fixture**. The cost is ~30 lines in a new `conftest.py`; the benefit is that T002/T003/T004/T005 each become 5-line tests instead of 15-line tests, and any future config-loading regression test gets the same hermetic guarantee for free.

If the implementor disagrees, they may inline the pattern per-test — both are acceptable.

---

## Worked Examples

### Example 1: T002 — Test the Auto-Registration Mechanism

```python
"""Tests for GraphConfig auto-registration when YAML omits `graph:` block."""

import pytest


@pytest.mark.unit
class TestGraphConfigAutoRegistration:
    """Tests that FS2ConfigurationService auto-registers GraphConfig() defaults
    when the YAML config has no `graph:` section.

    Closes issue #14: previously, services using `config.require(GraphConfig)`
    would raise `MissingConfigurationError` when the optional `graph:` block
    was absent from `.fs2/config.yaml`, even though every field on GraphConfig
    has a default.
    """

    def test_given_yaml_without_graph_section_when_loading_then_graph_config_uses_defaults(
        self, make_project_config
    ):
        """
        Purpose: Auto-registration provides a default-constructed GraphConfig
            when the YAML has no `graph:` block.
        Quality Contribution: Closes the footgun reported in issue #14 — MCP
            tools (tree, search, get_node) now work out of the box without
            requiring users to add a graph: section by hand.
        Contract: After loading a config that omits `graph:`,
            `config.require(GraphConfig)` MUST return a `GraphConfig` instance
            with `graph_path == ".fs2/graph.pickle"`.
        Worked Example: A user runs `fs2 init` (which produces a config
            without `graph:` in pre-fix versions), then wires fs2 into an MCP
            host. `tree(pattern=".")` should succeed, not raise.
        """
        # Arrange — YAML deliberately omits the `graph:` section
        make_project_config(
            """
scan:
  scan_paths:
    - "."
"""
        )

        # Act
        from fs2.config.objects import GraphConfig
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()
        graph_config = config.require(GraphConfig)

        # Assert
        assert isinstance(graph_config, GraphConfig)
        assert graph_config.graph_path == ".fs2/graph.pickle"

    def test_given_explicit_graph_section_when_loading_then_explicit_value_wins(
        self, make_project_config
    ):
        """
        Purpose: Explicit YAML graph_path overrides the auto-registered default.
        Quality Contribution: Verifies the auto-registration doesn't mask
            user-provided values — backward compatibility preserved.
        Contract: When YAML provides `graph: { graph_path: X }`, the loader
            MUST register that value, NOT the default. Auto-registration MUST
            be skipped if the type was already registered from YAML.
        """
        # Arrange — YAML provides an explicit non-default path
        make_project_config(
            """
graph:
  graph_path: "custom/path/to/graph.pickle"
"""
        )

        # Act
        from fs2.config.objects import GraphConfig
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()
        graph_config = config.require(GraphConfig)

        # Assert
        assert graph_config.graph_path == "custom/path/to/graph.pickle"
```

### Example 2: T003 — `TreeService` Initializes With No `graph:` Block

```python
@pytest.mark.unit
class TestTreeServiceWithMissingGraphConfig:
    """Tests that TreeService works when YAML config omits `graph:`."""

    def test_given_yaml_without_graph_section_when_constructing_tree_service_then_initializes_with_defaults(
        self, make_project_config
    ):
        """
        Purpose: TreeService initializes successfully via `config.require(GraphConfig)`
            when YAML has no `graph:` section, using auto-registered defaults.
        Quality Contribution: Closes the issue #14 footgun for the `tree` MCP tool
            specifically. Proves the auto-registration mechanism integrates correctly
            with the service that consumes GraphConfig.
        Contract: TreeService.__init__ MUST NOT raise MissingConfigurationError
            when `graph:` is absent from YAML. The service MUST receive a
            GraphConfig with graph_path equal to ".fs2/graph.pickle".
        Worked Example: User runs `fs2 init` then connects fs2 to Copilot CLI;
            `tree(pattern=".")` succeeds and lists nodes from the default graph path.
        """
        # Arrange — YAML omits `graph:`
        make_project_config(
            """
scan:
  scan_paths:
    - "."
"""
        )

        # Act
        from fs2.config.service import FS2ConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore
        from fs2.core.services.tree_service import TreeService

        config = FS2ConfigurationService()
        graph_store = NetworkXGraphStore()  # Real ABC implementation; see R4.2
        service = TreeService(config=config, graph_store=graph_store)

        # Assert — service constructed; default graph_path used internally
        assert service is not None
        # Optional deeper assertion if accessor available:
        # assert service._config.graph_path == ".fs2/graph.pickle"
```

### Example 3: Updating the Existing Negative Test (T004)

The existing test at `tests/unit/services/test_get_node_service.py:106-121` (`test_given_missing_graph_config_when_created_then_raises`) **must be removed or rewritten** after T001 lands. Two options:

**Option A — Replace with positive assertion** (recommended):

```python
def test_given_missing_graph_config_when_created_then_uses_default(
    self, make_project_config
):
    """
    Purpose: GetNodeService uses auto-registered GraphConfig defaults when
        YAML omits the `graph:` section. Replaces the previous test that
        asserted MissingConfigurationError was raised.
    Quality Contribution: Documents the post-fix-#14 behavior. Future readers
        can grep this test to understand why the missing-config raise was
        intentionally removed.
    Contract: Same as the auto-registration test above, scoped to GetNodeService.
    """
    # Arrange — YAML deliberately omits `graph:`
    make_project_config(
        """
scan:
  scan_paths:
    - "."
"""
    )

    # Act
    from fs2.config.service import FS2ConfigurationService
    from fs2.core.repos.graph_store_impl import NetworkXGraphStore
    from fs2.core.services.get_node_service import GetNodeService

    config = FS2ConfigurationService()
    graph_store = NetworkXGraphStore()
    service = GetNodeService(config=config, graph_store=graph_store)

    # Assert — no raise
    assert service is not None
```

**Option B — Delete the existing test**: only valid if a new positive test (above) exists in the same file. Don't leave the repo with neither test.

---

## Pitfalls & Anti-Patterns

| ❌ Anti-pattern | ✅ Correct |
|---|---|
| `os.environ["HOME"] = "/tmp/whatever"` | `monkeypatch.setenv("HOME", str(tmp_path))` (auto-reverts) |
| Forgetting `monkeypatch.delenv("XDG_CONFIG_HOME")` | Always delete it — production CI machines often set it, leaking the host config |
| Forgetting `monkeypatch.chdir(tmp_path)` | Project YAML discovery uses cwd — without chdir, you read the *real* repo's `.fs2/config.yaml` |
| Using `Mock(spec=ConfigurationService)` | Use `FakeConfigurationService` per R4.2 (Fakes Over Mocks) |
| Asserting `MissingConfigurationError` for absent `graph:` | After T001, this no longer raises — assert the default value instead |
| Reading from `~/.config/fs2/config.yaml` in a test (even via env vars) | Always set `HOME` to a tmp dir — a test that reads `~/.config` will pass on your dev machine and fail in CI |
| Hard-coding paths like `/tmp/fs2-test/...` | Use the `tmp_path` fixture — pytest auto-cleans, no collision between tests |
| Sharing `FS2ConfigurationService` instances across tests | Each test constructs its own — the loader is cheap and isolation is the point |

---

## Validation Checklist (for the implementor)

Before considering a config-loading test complete:

- [ ] `monkeypatch.setenv("HOME", str(tmp_path))` is set before `FS2ConfigurationService()` is constructed
- [ ] `monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)` is set before construction
- [ ] `monkeypatch.chdir(tmp_path)` is called before construction
- [ ] No reference to `~`, `$HOME`, `Path.home()`, or `Path.cwd()` outside fixtures
- [ ] Test runs and passes when `XDG_CONFIG_HOME` is set in your dev shell (try: `XDG_CONFIG_HOME=/tmp/xdg pytest tests/unit/config/...`)
- [ ] Test runs and passes when invoked from a directory that has its own `.fs2/config.yaml` (try: `cd ~/some-fs2-project && pytest path/to/the/test`)
- [ ] Test docstring includes Purpose + Quality Contribution per R4.3 (and SHOULD include Contract + Worked Example per the spec's Test Doc requirement)

---

## Open Questions

### Q1: Should we add the `make_project_config` fixture or inline the pattern per-test?

**RESOLVED**: Adopt the fixture (in `tests/unit/config/conftest.py`). Cost is ~30 lines; benefit is that 4 new tests get cleaner and any future test gets the hermetic guarantee for free.

### Q2: For T003/T004/T005, should we use `FakeConfigurationService` (lighter) or `FS2ConfigurationService` (proves end-to-end)?

**RESOLVED**: Use `FS2ConfigurationService` with real fixture YAML. The whole point of these tests is "the auto-registration in T001 actually flows through to service initialization." `FakeConfigurationService` skips the loader, which would not exercise T001.

### Q3: Do we need to test `FS2_GRAPH__GRAPH_PATH` env var override too?

**RESOLVED**: Out of scope for this plan. Env var override is governed by the existing merge logic and isn't affected by T001 (T001 only changes behavior when no value is provided from any source). If a future plan touches env-var precedence for `GraphConfig`, it should add that test.

### Q4: Should we verify the `__defaults_when_missing__` mechanism works for OTHER configs not yet in `_AUTO_DEFAULT_CONFIGS`?

**OPEN**: The plan lists only `GraphConfig` in `_AUTO_DEFAULT_CONFIGS`. We deliberately don't auto-default LLM/Embedding/Smart Content configs because they require user setup (API keys, deployment names). However, the test should sanity-check that adding a new config to `_AUTO_DEFAULT_CONFIGS` works — perhaps via a parametrized test, or by trusting the implementation pattern. Implementor's call.

---

## Quick Reference

```python
# Hermetic config test setup — copy-paste this into any new test
def test_x(self, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.chdir(tmp_path)

    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("""
        # YAML fixture here
    """)

    from fs2.config.service import FS2ConfigurationService
    config = FS2ConfigurationService()
    # ... assertions ...

# OR with the proposed fixture:
def test_y(self, make_project_config):
    make_project_config("""
        scan:
          scan_paths:
            - "."
    """)
    from fs2.config.service import FS2ConfigurationService
    config = FS2ConfigurationService()
    # ... assertions ...
```

```bash
# Sanity-check your test isn't reading the real config:
XDG_CONFIG_HOME=/tmp/nope HOME=/tmp/nope pytest tests/unit/config/your_test.py -v
```
