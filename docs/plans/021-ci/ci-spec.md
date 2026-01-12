# CI Pipeline for fs2

**Mode**: Simple

## Research Context

This specification incorporates findings from `research-dossier.md`.

- **Components affected**: `.github/workflows/ci.yml` (new file)
- **Critical dependencies**: `astral-sh/setup-uv@v7`, existing `ruff` config in `pyproject.toml`, existing `just lint` command
- **Modification risks**: None - greenfield CI addition
- **Link**: See `research-dossier.md` for full analysis

---

## Summary

**WHAT**: A GitHub Actions CI pipeline that validates code quality and package installability on every push to main and every pull request.

**WHY**: To catch lint/format issues before they enter the codebase and ensure the `uvx` installation path documented in README actually works. This prevents broken code from being merged and gives confidence that users can install fs2 as documented.

---

## Goals

1. **Enforce code quality** - Fail CI if code doesn't pass lint or format checks
2. **No auto-fixing** - CI must not modify code; developers run `just fix` locally
3. **Clear failure messages** - When checks fail, tell developers exactly what to run
4. **Validate installability** - Confirm `uvx --from . fs2 --help` works on every change
5. **Fast feedback** - Target under 2 minutes total CI time
6. **Work for main and PRs** - Single workflow handles both triggers

---

## Non-Goals

- **Running tests** - Out of scope for initial CI (future enhancement)
- **Auto-fixing in CI** - Explicitly rejected; no commits back to PRs
- **Coverage reporting** - Future enhancement
- **Multi-Python matrix** - Start with 3.12 only; expand later if needed
- **Release automation** - Separate concern for a future plan

---

## Complexity

- **Score**: CS-1 (trivial)
- **Breakdown**: S=0, I=1, D=0, N=0, F=0, T=0
- **Confidence**: 0.95
- **Assumptions**:
  - GitHub Actions is available for this repository
  - The existing `ruff` configuration is correct and working
  - `uvx --from .` works in CI environment (validated in research)
- **Dependencies**:
  - `astral-sh/setup-uv@v7` action availability
  - GitHub Actions runners (ubuntu-latest)
- **Risks**:
  - First run may be slow due to cache miss (~2-3 min instead of ~1 min)
- **Phases**:
  - Phase 1: Create workflow file and push to main

---

## Acceptance Criteria

### AC1: Lint Check Fails on Violations
**Given** code with lint violations (e.g., unused import)
**When** CI runs on push or PR
**Then** the lint-and-format job fails with non-zero exit code
**And** the error output identifies the specific violations

### AC2: Format Check Fails on Unformatted Code
**Given** code that doesn't match `ruff format` style
**When** CI runs on push or PR
**Then** the lint-and-format job fails
**And** the error message instructs user to run `just fix` locally

### AC3: Clean Code Passes All Checks
**Given** code that passes `just lint` locally
**When** CI runs on push or PR
**Then** the lint-and-format job succeeds with exit code 0

### AC4: Smoke Test Validates Installation
**Given** the current codebase
**When** CI runs the smoke-test job
**Then** `uvx --from . fs2 --help` executes successfully
**And** `uvx --from . fs2 --version` outputs version information

### AC5: CI Triggers on Main Push
**Given** a commit pushed directly to main
**When** GitHub receives the push event
**Then** the CI workflow is triggered and runs both jobs

### AC6: CI Triggers on Pull Request
**Given** a pull request opened against main
**When** GitHub receives the PR event
**Then** the CI workflow is triggered and runs both jobs

### AC7: No Auto-Fixing Occurs
**Given** code with fixable lint/format issues
**When** CI runs
**Then** no files are modified in the repository
**And** no commits are created by CI

### AC8: Inline Annotations on PR
**Given** a PR with lint violations
**When** CI runs with `--output-format=github`
**Then** GitHub displays inline annotations on the PR diff showing violation locations

---

## Risks & Assumptions

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GitHub Actions rate limiting | Low | Medium | Use `enable-cache: true` to reduce API calls |
| First-run cache miss slowness | High (once) | Low | Accept initial 2-3 min run; subsequent runs cached |
| uvx build failure in CI | Low | High | Test locally first with `uvx --from . fs2 --help` |

### Assumptions
1. The repository has GitHub Actions enabled
2. `uv.lock` file is committed and up-to-date
3. Current `pyproject.toml` and `justfile` work correctly
4. Python 3.12 is sufficient (matches `requires-python`)

---

## Open Questions

None - requirements are clear from research and user input.

---

## ADR Seeds (Optional)

Not applicable - implementation is straightforward with no significant architectural decisions. Using official Astral actions (`setup-uv`, `ruff`) is the obvious choice.

---

## External Research

No external research was required. GitHub Actions documentation and official action repositories provided sufficient guidance.

---

**Spec Created**: 2026-01-12
**Plan Directory**: `docs/plans/021-ci/`
**Next Step**: Run `/plan-2-clarify` or proceed directly to implementation (CS-1 may not need clarification)
