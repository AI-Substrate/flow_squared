# Research Report: CI Pipeline for fs2

**Generated**: 2026-01-12
**Research Query**: CI for PR and main branch - FFT check (no auto-fix) and uvx install smoke test
**Mode**: Plan-Associated
**Location**: docs/plans/021-ci/research-dossier.md
**FlowSpace**: Available
**Findings**: 24

## Executive Summary

### What It Does
CI pipeline that runs on PR and main branch to enforce code quality (lint/format checks) and validate the uvx install workflow works correctly.

### Business Purpose
Ensures code quality standards are maintained, prevents broken code from being merged, and validates that end-users can install fs2 via the documented `uvx` command.

### Key Insights
1. Project already has `just lint` command that does check-only (no auto-fix) - perfect for CI
2. GitHub Actions has official `astral-sh/setup-uv@v7` action with caching support
3. uvx smoke test is straightforward: `uvx --from . fs2 --help`

### Quick Stats
- **CI Triggers**: Push to main, Pull Request to main
- **Jobs**: 2 (lint-format-check, smoke-test)
- **Dependencies**: uv, Python 3.12, ruff (via dev dependencies)
- **Estimated CI Time**: ~1-2 minutes

---

## Current Project Setup

### Package Manager: uv
- **Lock file**: `uv.lock` exists at project root
- **Python version**: `>=3.12` (from pyproject.toml)
- **No `.python-version` file** - CI should use pyproject.toml

### Ruff Configuration (pyproject.toml)
```toml
[tool.ruff]
line-length = 88
target-version = "py312"
exclude = [
    "tests/fixtures/ast_samples/python/syntax_error.py",
]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM"]
ignore = ["E501", "E402"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["B017", "SIM102"]

[tool.ruff.lint.isort]
known-first-party = ["fs2"]
```

### Existing Commands (justfile)

| Command | What It Does | CI Use |
|---------|--------------|--------|
| `just lint` | `ruff check` + `ruff format --check` (no fixes) | **CI should use this** |
| `just fix` | `ruff check --fix` + `ruff format` (auto-fix) | User runs locally |
| `just fft` | `fix` then `test` | Development workflow |
| `just test` | `uv run pytest tests/ -v` | Future CI expansion |

**Key distinction for CI**: `lint` = check only (fail on issues), `fix` = auto-correct

---

## GitHub Actions Components

### 1. astral-sh/setup-uv (Official Action)

**Repository**: https://github.com/astral-sh/setup-uv
**Current Version**: v7.1.1

**Key Features**:
- Installs uv on runner
- Built-in caching (`enable-cache: true`)
- Can install Python via `uv python install`
- Supports version pinning

**Basic Usage**:
```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v7
  with:
    enable-cache: true
    # version: "0.9.12"  # Optional: pin version
```

### 2. Python Installation Options

**Option A: uv python install (Recommended)**
```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v7
  with:
    enable-cache: true

- name: Set up Python
  run: uv python install 3.12
```

**Option B: actions/setup-python (Faster due to GitHub caching)**
```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version-file: "pyproject.toml"

- name: Install uv
  uses: astral-sh/setup-uv@v7
  with:
    enable-cache: true
```

**Recommendation**: Use Option A for simplicity since uv handles Python well.

### 3. Ruff in CI

**Two approaches**:

**A. Via uv run (after installing deps)**:
```yaml
- run: uv sync --extra dev
- run: uv run ruff check src/ tests/
- run: uv run ruff format --check src/ tests/
```

**B. Via astral-sh/ruff-action (standalone)**:
```yaml
- uses: astral-sh/ruff-action@v3
  with:
    args: "check"

- uses: astral-sh/ruff-action@v3
  with:
    args: "format --check"
```

**Recommendation**: Use approach A since we need uv sync anyway and `just lint` already encapsulates this.

---

## Proposed CI Workflows

### Workflow 1: Main Branch CI (on push to main)

**Trigger**: Push to main branch
**Purpose**: Validate main branch stays clean after merges

```yaml
name: CI

on:
  push:
    branches: [main]

jobs:
  lint-and-format:
    name: Lint & Format Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --locked --extra dev

      - name: Run lint check
        run: uv run ruff check src/ tests/

      - name: Run format check
        run: uv run ruff format --check src/ tests/

  smoke-test:
    name: Install Smoke Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v7

      - name: Set up Python
        run: uv python install 3.12

      - name: Test uvx install from local
        run: uvx --from . fs2 --help

      - name: Verify output
        run: |
          uvx --from . fs2 --version
```

### Workflow 2: PR CI (on pull_request to main)

**Trigger**: Pull request targeting main
**Purpose**: Validate PR code before merge

```yaml
name: PR Check

on:
  pull_request:
    branches: [main]

jobs:
  lint-and-format:
    name: Lint & Format Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --locked --extra dev

      - name: Run lint check
        run: uv run ruff check --output-format=github src/ tests/

      - name: Run format check
        run: uv run ruff format --check src/ tests/

  smoke-test:
    name: Install Smoke Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v7

      - name: Set up Python
        run: uv python install 3.12

      - name: Test uvx install from PR branch
        run: uvx --from . fs2 --help

      - name: Verify version output
        run: uvx --from . fs2 --version
```

### Combined Single Workflow (Alternative)

For simplicity, can combine into one workflow:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-format:
    name: Lint & Format Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --locked --extra dev

      - name: Run lint check
        run: uv run ruff check --output-format=github src/ tests/

      - name: Run format check
        run: |
          uv run ruff format --check src/ tests/ || {
            echo "::error::Format check failed. Run 'just fix' locally and commit the changes."
            exit 1
          }

  smoke-test:
    name: Install Smoke Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v7

      - name: Set up Python
        run: uv python install 3.12

      - name: Test uvx install
        run: uvx --from . fs2 --help

      - name: Verify version
        run: uvx --from . fs2 --version
```

---

## Key Implementation Details

### 1. No Auto-Fixing in CI

The user explicitly requested **no auto-fixing**. The CI should:
- Run checks only (`ruff check` without `--fix`, `ruff format --check`)
- Fail with a clear message telling user to run `just fix` locally
- Not commit any changes back to the PR

### 2. Error Messages

When format check fails:
```
Format check failed. Run 'just fix' locally and commit the changes.
```

When lint check fails:
```
Lint check failed. Run 'just fix' locally to auto-fix issues, or manually address them.
```

### 3. GitHub Output Format

Using `--output-format=github` with ruff check enables inline annotations on PR diffs, making it easier for developers to see exactly where issues are.

### 4. Smoke Test Details

The smoke test validates:
1. **Build works**: `uvx --from .` builds the package from source
2. **Entry point works**: `fs2 --help` runs successfully
3. **Version command works**: `fs2 --version` outputs version info

Note: First `uvx` run builds from source (~30-60 seconds). Cache helps on subsequent runs.

### 5. Caching Strategy

```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v7
  with:
    enable-cache: true
    cache-dependency-glob: "uv.lock"
```

This caches:
- Downloaded packages
- Virtual environment (keyed by uv.lock hash)

---

## Files to Create

| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | Main CI workflow |

**Folder structure needed**:
```
.github/
└── workflows/
    └── ci.yml
```

---

## Recommendations

### Phase 1: Main Branch CI (Now)
1. Create `.github/workflows/ci.yml` with push trigger on main
2. Include lint/format check job
3. Include smoke test job
4. Push to main to activate

### Phase 2: PR CI (When branching)
1. Add `pull_request` trigger to same workflow
2. The combined workflow handles both cases
3. Test with a PR

### Optional Enhancements (Future)
- Add test job (`uv run pytest tests/ -v`)
- Add coverage reporting
- Add type checking (if mypy is added)
- Matrix testing for Python 3.12, 3.13

---

## Validation Checklist

Before implementing, verify:
- [ ] `.github/workflows/` directory can be created
- [ ] `uv sync --locked` works locally
- [ ] `uv run ruff check src/ tests/` works locally
- [ ] `uv run ruff format --check src/ tests/` works locally
- [ ] `uvx --from . fs2 --help` works locally

---

## References

1. **uv GitHub Actions Guide**: https://docs.astral.sh/uv/guides/integration/github/
2. **astral-sh/setup-uv**: https://github.com/astral-sh/setup-uv
3. **Ruff Integrations**: https://docs.astral.sh/ruff/integrations/
4. **astral-sh/ruff-action**: https://github.com/astral-sh/ruff-action

---

## Prior Learnings

No prior CI-related learnings found in existing plan documentation. This is the first CI implementation for the project.

---

## External Research Opportunities

No external research gaps identified. The GitHub Actions documentation and official action repositories provide comprehensive guidance for this implementation.

---

**Research Complete**: 2026-01-12
**Report Location**: /workspaces/flow_squared/docs/plans/021-ci/research-dossier.md
