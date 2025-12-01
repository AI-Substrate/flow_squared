# fs2 Rules

> Normative MUST/SHOULD/MUST NOT statements enforcing the [Constitution](../rules/constitution.md).

**Version**: 1.0.0
**Last Updated**: 2025-12-01

---

## 1. Source Control & Branching

### R1.1 Branch Hygiene
- Branches MUST be named descriptively (`feature/`, `fix/`, `refactor/`)
- Commits MUST have clear, imperative messages
- PRs MUST reference related issues when applicable

### R1.2 Commit Standards
- Commits SHOULD be atomic (one logical change per commit)
- Commits MUST NOT include generated files or secrets
- Merge commits SHOULD be avoided (prefer rebase)

<!-- USER CONTENT START -->
<!-- Add project-specific branching rules here -->
<!-- USER CONTENT END -->

---

## 2. Coding Standards

### R2.1 Import Rules (CRITICAL)

**MUST**:
- Services MUST import only from: `models`, adapter/repo ABCs, `config`
- Adapters MUST import `ConfigurationService` via `TYPE_CHECKING`
- Models MUST be importable by all layers

**MUST NOT**:
- Adapters MUST NOT import from services
- Repos MUST NOT import from services
- Config MUST NOT import from any `fs2.core.*` modules
- ABCs MUST NOT import external SDKs (only domain types)
- SDK imports MUST NOT appear outside `*_impl.py` files

### R2.2 Naming Conventions

**Files**:
- Adapter ABC: `{name}_adapter.py`
- Adapter implementations: `{name}_adapter_{impl}.py` (e.g., `log_adapter_console.py`)
- Services: `{name}_service.py`
- Config types: All in `src/fs2/config/objects.py`

**Classes**:
- Adapters: `{Impl}{Name}Adapter` (e.g., `ConsoleLogAdapter`, `FakeLogAdapter`)
- Services: `{Name}Service` (e.g., `SampleService`)
- Config: `{Name}Config` (e.g., `LogAdapterConfig`)
- Exceptions: `{Name}Error` (e.g., `AdapterError`, `AuthenticationError`)

**Tests**:
- Test functions: `test_given_<precondition>_when_<action>_then_<outcome>`
- Test files: `test_{module}.py`

### R2.3 Environment Variables

- Prefix MUST be `FS2_` (uppercase)
- Nesting delimiter MUST be `__` (double underscore)
- Format: `FS2_{SECTION}__{SUBSECTION}__{FIELD}`
- Example: `FS2_AZURE__OPENAI__TIMEOUT=60`

### R2.4 Code Style

- Code MUST pass `just lint` (ruff) without errors
- Code SHOULD be formatted with `just fix` before commit
- Type hints SHOULD be used for public APIs
- Docstrings MUST be present on all ABCs and public methods

<!-- USER CONTENT START -->
<!-- Add project-specific coding standards here -->
<!-- USER CONTENT END -->

---

## 3. Interface & Contract Rules

### R3.1 ABC Requirements

- All adapters and repos MUST inherit from `abc.ABC`
- All interface methods MUST have `@abstractmethod` decorator
- ABCs MUST use only domain types (no SDK types in signatures)
- ABCs MUST have docstrings explaining the contract

### R3.2 Dependency Injection

- Components MUST receive `ConfigurationService` (registry), not extracted configs
- Components MUST call `config.require(TheirConfigType)` internally
- Composition root MUST NOT know what configs components need (no concept leakage)

### R3.3 Exception Handling

- Adapters MUST catch SDK exceptions and translate to domain exceptions
- Domain exceptions MUST include actionable fix instructions
- Logging methods MUST NOT propagate exceptions (industry standard error swallowing)

### R3.4 Immutability

- Domain models MUST use `@dataclass(frozen=True)`
- Models MUST NOT contain business logic
- Models MUST be pure data containers

<!-- USER CONTENT START -->
<!-- Add project-specific interface rules here -->
<!-- USER CONTENT END -->

---

## 4. Testing Rules

### R4.1 Testing Philosophy

- Development MUST follow TDD (Test-Driven Development)
- Coverage MUST be >80% on new code
- Tests MUST be deterministic (no flaky tests)
- Tests MUST be fast (no network calls, no sleep)

### R4.2 Test Doubles

- Test doubles MUST inherit from ABC (Fakes, not Mocks)
- `unittest.mock` MUST NOT be used for adapters/repos
- `monkeypatch` MAY be used for env vars and file system
- Fakes MUST implement all abstract methods

### R4.3 Test Documentation

Every test MUST include a docstring with:
1. **Purpose**: What truth this test proves
2. **Quality Contribution**: How this prevents bugs

Every test SHOULD include:
3. **Contract**: Plain-English invariants
4. **Usage Notes**: API gotchas
5. **Worked Example**: Inputs/outputs

### R4.4 Test Naming & Structure

- Test names MUST follow: `test_given_<X>_when_<Y>_then_<Z>`
- Tests MUST use Arrange-Act-Assert structure with clear phase comments
- Test files MUST be organized by layer: `tests/unit/{adapters,config,models,services}/`

### R4.5 Scratch Tests

- Exploration tests MAY be written in `tests/scratch/`
- `tests/scratch/` MUST be excluded from CI
- Tests MUST be promoted from scratch/ only if they add durable value
- **Promotion heuristic**: Critical path, Opaque behavior, Regression-prone, Edge case
- Promoted tests MUST include complete Test Doc blocks
- Non-valuable scratch tests MUST be deleted

### R4.6 Test Reliability

- Tests MUST NOT make network calls (use fixtures/fakes)
- Tests MUST NOT use `time.sleep()` or timers
- Tests MUST NOT depend on execution order
- Tests MUST clean up any state they create

<!-- USER CONTENT START -->
<!-- Add project-specific testing rules here -->
<!-- USER CONTENT END -->

---

## 5. Configuration Rules

### R5.1 Config Types

- Config types MUST be Pydantic models
- Config types MUST have `__config_path__` for YAML location
- Config types MUST be registered in `YAML_CONFIG_TYPES`
- Config field descriptions MUST document expected values

### R5.2 Precedence

Config sources in order (highest to lowest priority):
1. Environment variables (`FS2_*`)
2. Project YAML (`.fs2/config.yaml`)
3. User YAML (`~/.config/fs2/config.yaml`)
4. Defaults in code

### R5.3 Secrets

- Secrets MUST use placeholder syntax: `${VAR_NAME}`
- Literal secrets MUST be rejected during validation
- Secrets MUST NOT be committed to source control
- `.fs2/secrets.env` MUST be in `.gitignore`

### R5.4 Validation

- Config MUST fail fast on startup if invalid
- Error messages MUST include fix instructions
- Placeholder expansion MUST be recursive (handle nested models)

<!-- USER CONTENT START -->
<!-- Add project-specific configuration rules here -->
<!-- USER CONTENT END -->

---

## 6. Documentation Rules

### R6.1 Code Documentation

- ABCs MUST have docstrings explaining the contract
- Config fields MUST have `Field(description="...")`
- Complex logic SHOULD have inline comments explaining "why"
- Comments SHOULD NOT explain "what" (code should be self-documenting)

### R6.2 Test Documentation

- Canonical tests MUST serve as executable documentation
- `tests/docs/test_sample_adapter_pattern.py` is the reference implementation
- Tests MUST show real usage scenarios

### R6.3 Architecture Documentation

- Changes to architecture MUST be reflected in `docs/how/`
- New patterns MUST be documented with examples
- Breaking changes MUST be noted in constitution amendments

<!-- USER CONTENT START -->
<!-- Add project-specific documentation rules here -->
<!-- USER CONTENT END -->

---

## 7. Tooling & Automation

### R7.1 Required Tools

| Tool | Command | Must Pass |
|------|---------|-----------|
| pytest | `just test` | Yes |
| ruff | `just lint` | Yes |
| ruff | `just fix` | Before commit |

### R7.2 CI Requirements

- All tests MUST pass before merge
- Linting MUST pass before merge
- Coverage report SHOULD be generated

### R7.3 Local Development

- `uv sync --extra dev` MUST install all dependencies
- `just test` MUST run full test suite
- `just lint` MUST check code quality

<!-- USER CONTENT START -->
<!-- Add project-specific tooling rules here -->
<!-- USER CONTENT END -->

---

## 8. Complexity Estimation Rules

### R8.1 No Time Estimates

- Estimates MUST NOT include time, duration, or ETA
- Words like "hours", "days", "quick", "soon" MUST NOT appear
- Planning MUST use Complexity Score (CS 1-5) only

### R8.2 Complexity Scoring

- CS MUST be calculated using 6-factor rubric (S, I, D, N, F, T)
- Each factor scored 0-2, summed to determine CS
- CS-4+ MUST include staged rollout and rollback plan

### R8.3 Mandatory Output Fields

When planning, output MUST include:
```json
{
  "complexity": {
    "score": 3,
    "label": "medium",
    "breakdown": {"surface": 1, "integration": 1, "data_state": 1, "novelty": 1, "nfr": 0, "testing_rollout": 1},
    "confidence": 0.75
  }
}
```

<!-- USER CONTENT START -->
<!-- Add project-specific estimation rules here -->
<!-- USER CONTENT END -->

---

## Quick Reference

### Import Rules Summary

| From | Can Import | Cannot Import |
|------|------------|---------------|
| CLI | services (ABCs) | adapters (impl), repos (impl) |
| Services | models, adapter ABCs, repo ABCs, config | SDK types, impl files |
| Adapters (ABC) | models, domain exceptions | SDKs, services |
| Adapters (impl) | ABC, config, SDKs | services |
| Models | standard lib only | anything in core |
| Config | pydantic, os, re, yaml | anything in core |

### Test Double Rules Summary

| Use | Don't Use |
|-----|-----------|
| `FakeLogAdapter(config)` | `Mock(spec=LogAdapter)` |
| `FakeConfigurationService(...)` | `MagicMock()` |
| `monkeypatch.setenv()` | `@patch.dict(os.environ)` |

---

*See [Constitution](../rules/constitution.md) for principles and rationale.*
*See [Idioms](idioms.md) for implementation examples.*
*See [Architecture](architecture.md) for structural boundaries.*
