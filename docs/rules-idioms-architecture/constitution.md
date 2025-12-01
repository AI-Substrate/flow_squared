# Flowspace2 (fs2) Project Constitution

<!--
Sync Impact Report:
- Mode: CREATE
- Version: 1.0.0 (initial)
- Creation Date: 2025-12-01
- Source: docs/plans/002-project-skele (spec, plan, tasks phases 0-5)
- Supporting Docs: docs/rules-idioms-architecture/{rules.md, idioms.md, architecture.md}
- Outstanding TODOs: None
-->

**Version**: 1.0.0
**Ratified**: 2025-12-01
**Last Amended**: 2025-12-01

---

## 1. Project Identity

| Attribute | Value |
|-----------|-------|
| **Name** | Flowspace2 |
| **Short Name** | fs2 |
| **Env Prefix** | `FS2_` |
| **Config Dir** | `.fs2/` |
| **Package Manager** | `uv` |
| **Python Version** | 3.12+ |

---

## 2. Guiding Principles

### P1: Clean Architecture with Strict Dependency Flow

**Statement**: Dependencies flow left-to-right only: `CLI → Services → {Adapters, Repos} → External Systems`. Infrastructure types (HTTP, SDKs, databases) MUST NEVER leak into services.

**Rationale**: Prevents LLM agents from making field decisions that create circular dependencies, vendor type leakage, or bypass composition layers.

**Key Constraints**:
- Services receive only domain types and adapter/repo interfaces (ABCs)
- Adapters and repos MUST NOT import from services
- External SDK types stay in `*_impl.py` files only
- Models are the shared language across all layers

<!-- USER CONTENT START -->
<!-- Add project-specific architectural principles here -->
<!-- USER CONTENT END -->

### P2: ABC-Based Interfaces with @abstractmethod

**Statement**: Use `abc.ABC` with `@abstractmethod` for explicit contracts. Implementations MUST inherit from ABC base class.

**Rationale**: Runtime enforcement catches missing methods immediately (`TypeError` on instantiation). Clear inheritance hierarchy aids code navigation. Explicit contracts help AI agents understand requirements.

**Pattern**:
```python
from abc import ABC, abstractmethod

class LogAdapter(ABC):
    @abstractmethod
    def info(self, msg: str, **context: Any) -> None: ...
```

### P3: No Concept Leakage

**Statement**: Composition root passes `ConfigurationService` (registry) to all components. Components call `config.require(TheirConfigType)` internally. Composition root doesn't know what configs each component needs.

**Rationale**: Prevents tight coupling; allows swapping implementations without modifying composition root; enables independent testing.

**Correct Pattern**:
```python
# Composition root passes registry
service = MyService(config=config, adapter=adapter)

# Inside MyService.__init__:
self._config = config.require(MyServiceConfig)  # Gets own config internally
```

**Anti-Pattern**:
```python
# WRONG - Composition root extracts config (concept leakage)
service_cfg = config.require(MyServiceConfig)
service = MyService(config=service_cfg, adapter=adapter)
```

### P4: Fakes Over Mocks

**Statement**: Implement real test doubles as interface implementations that inherit from ABC. Never use `unittest.mock` for adapters/repos.

**Rationale**: Fakes provide higher confidence than mocks. Mocks risk false positives from implementation changes. Fakes serve as documentation of how to implement the interface correctly.

**Allowed**: Environment variables, file system via `monkeypatch` during config TDD.
**Forbidden**: `Mock(spec=Adapter)` for any adapter or repository.

### P5: Immutable Domain Models

**Statement**: Domain models use `@dataclass(frozen=True)` for immutable value objects. Zero business logic; pure data containers. Models are shared language across layers.

**Rationale**: Prevents accidental mutation across async contexts; makes state transitions explicit; enables safe concurrent access.

**Constraints**:
- Models MUST NOT import from services, adapters, or repos
- All layers MAY import from models
- Models contain no business logic

### P6: Exception Translation at Adapter Boundary

**Statement**: Catch SDK exceptions in adapter implementations and translate to domain exceptions. Infrastructure errors are the adapter's responsibility to handle.

**Rationale**: Prevents vendor-specific exception types from leaking into business logic; enables uniform error handling.

**Pattern**:
```python
try:
    return sdk.call()
except SDKAuthError as e:
    raise AuthenticationError(f"Auth failed: {e}") from e
```

### P7: Tests as Executable Documentation

**Statement**: Tests serve as the most reliable form of documentation. Each test includes a Test Doc block with: Why, Contract, Usage Notes, Quality Contribution, Worked Example.

**Rationale**: Executable docs are enforced by CI; tests show real usage scenarios; prevents documentation drift.

**Naming Convention**: `test_given_<precondition>_when_<action>_then_<outcome>`

### P8: Actionable Error Messages

**Statement**: All exceptions include fix instructions: which env var to set, which config file to edit, what the user should do next.

**Rationale**: Reduces debugging time; improves developer experience; critical for AI agent troubleshooting.

**Example**:
```
LiteralSecretError: Literal secret in api_key. Use placeholder: ${API_KEY}. Then set env var: API_KEY=<secret>
```

---

## 3. Quality & Verification Strategy

### 3.1 Testing Philosophy

| Aspect | Approach |
|--------|----------|
| **Methodology** | Full TDD (Test-Driven Development) |
| **Coverage Target** | >80% on new code |
| **Test Doubles** | Fakes over mocks (inherit from ABC) |
| **Documentation** | Tests include Test Doc blocks |

### 3.2 Test Structure

```
tests/
├── conftest.py          # Shared fixtures (TestContext, clean_config_env)
├── unit/
│   ├── config/          # Configuration tests
│   ├── adapters/        # Adapter tests
│   ├── models/          # Domain model tests
│   └── services/        # Service tests
├── docs/                # Canonical documentation tests
└── scratch/             # Fast exploration (excluded from CI)
```

### 3.3 Test Quality Standards

Every test MUST include:
1. **Why**: Business/bug/regression reason for existence
2. **Contract**: Plain-English invariants being asserted
3. **Usage Notes**: How to call the API, gotchas
4. **Quality Contribution**: What failures it catches
5. **Worked Example**: Inputs/outputs summary (SHOULD include)

### 3.4 Scratch → Promote Workflow

1. Probe tests MAY be written in `tests/scratch/` for fast exploration
2. `tests/scratch/` MUST be excluded from CI
3. Tests MUST be promoted from scratch/ only if they add durable value
4. **Promotion heuristic**: Keep if Critical path, Opaque behavior, Regression-prone, or Edge case
5. Promoted tests MUST move to `tests/unit/` or `tests/integration/`
6. Non-valuable scratch tests MUST be deleted

### 3.5 Linting & Formatting

| Tool | Command | Purpose |
|------|---------|---------|
| ruff | `just lint` | Linting and style checks |
| ruff | `just fix` | Auto-fix and format |

### 3.6 Test Reliability

- Tests MUST NOT use network calls (use fixtures/fakes)
- Tests MUST NOT use sleep/timers (use time mocking if needed)
- Tests MUST be deterministic (no flaky tests in main suite)
- Tests SHOULD be fast for quick feedback loops

<!-- USER CONTENT START -->
<!-- Add project-specific quality gates here -->
<!-- USER CONTENT END -->

---

## 4. Delivery Practices

### 4.1 Planning Approach

| Aspect | Value |
|--------|-------|
| **Methodology** | Phase-based planning with full specification |
| **Workflow** | Full mode (comprehensive gates, strict clarifications) |
| **Estimation** | Complexity Score (CS 1-5), never time-based |

### 4.2 Complexity Scoring (CS 1-5)

**Prohibition**: Never output or imply time, duration, or ETA in any form.

**Scoring Rubric** (0-2 points each, sum to determine CS):
- **Surface Area (S)**: Files/modules touched
- **Integration Breadth (I)**: External libs/services/APIs
- **Data & State (D)**: Schema changes, migrations, concurrency
- **Novelty & Ambiguity (N)**: Requirements clarity, research needed
- **Non-Functional Constraints (F)**: Performance, security, compliance
- **Testing & Rollout (T)**: Test depth, flags, staged rollout

**Mapping**:
| Points | CS | Label | Description |
|--------|-----|-------|-------------|
| 0-2 | CS-1 | Trivial | Isolated tweak, no new deps, unit test touchups |
| 3-4 | CS-2 | Small | Few files, familiar code, maybe one internal integration |
| 5-7 | CS-3 | Medium | Multiple modules, small migration or stable external API |
| 8-9 | CS-4 | Large | Cross-component, new dependency, meaningful migration |
| 10-12 | CS-5 | Epic | Architectural change, high uncertainty, phased rollout |

### 4.3 Definition of Done

**Code**:
- [ ] All tests passing (unit, integration, docs)
- [ ] Coverage >80% on new code
- [ ] No SDK/vendor types in service/adapter ABCs
- [ ] ABC inheritance enforced
- [ ] ConfigurationService injection pattern used

**Documentation**:
- [ ] Test docstrings with Purpose, Quality Contribution
- [ ] README explains architecture and responsibilities
- [ ] Each ABC has docstring explaining contract
- [ ] Configuration fields have descriptions

**Process**:
- [ ] Acceptance criteria explicitly verified
- [ ] Code review checklist passed
- [ ] Final validation: `just test` and `just lint` pass

### 4.4 Code Review Checklist

**Dependency Flow**:
- [ ] Services import only from: models, adapter/repo ABCs, config service
- [ ] Adapters/repos do NOT import from services
- [ ] Models do NOT import from core modules
- [ ] SDK imports only in `*_impl.py` files

**Interface Contracts**:
- [ ] All adapters and repos inherit from ABC
- [ ] All methods have `@abstractmethod` decorator
- [ ] Interfaces use only domain types (no SDK types)

**Test Quality**:
- [ ] Tests use Given-When-Then naming convention
- [ ] Tests have Arrange-Act-Assert structure
- [ ] Fakes inherit from ABC, not mocks
- [ ] Test Doc blocks present

<!-- USER CONTENT START -->
<!-- Add project-specific delivery practices here -->
<!-- USER CONTENT END -->

---

## 5. Governance

### 5.1 Amendment Procedure

1. Propose change via PR with rationale
2. Changes to principles require team consensus
3. Version bump follows semantic versioning:
   - **MAJOR**: Breaking changes to principles or governance
   - **MINOR**: New principles/sections or materially expanded guidance
   - **PATCH**: Clarifications or formatting adjustments
4. Update "Last Amended" date on approval

### 5.2 Review Cadence

| Review Type | Frequency |
|-------------|-----------|
| Principle adherence | Every PR (via checklist) |
| Constitution review | Quarterly or after major changes |
| Doctrine sync | When adding new adapters/patterns |

### 5.3 Compliance Tracking

- Architecture violations flagged in code review
- Test coverage tracked in CI
- Dependency flow verified via import analysis

### 5.4 Roles and Responsibilities

| Role | Responsibility |
|------|----------------|
| **Developers** | Follow TDD, clean architecture patterns, constitution |
| **Reviewers** | Verify dependency flow, ABC usage, test quality, docs |
| **AI Agents** | Follow constitution explicitly; ask for clarification when rules unclear; don't guess architecture decisions |

<!-- USER CONTENT START -->
<!-- Add project-specific governance rules here -->
<!-- USER CONTENT END -->

---

## 6. Supporting Documents

| Document | Purpose | Path |
|----------|---------|------|
| **Rules** | Normative MUST/SHOULD statements | `docs/rules-idioms-architecture/rules.md` |
| **Idioms** | Recurring patterns and examples | `docs/rules-idioms-architecture/idioms.md` |
| **Architecture** | Structure, boundaries, contracts | `docs/rules-idioms-architecture/architecture.md` |
| **How-To Guides** | Implementation guides | `docs/how/*.md` |

---

## Appendix: Key Architecture Decisions

| Decision | Rationale | Impact |
|----------|-----------|--------|
| ABC over Protocol | Runtime enforcement, explicit contracts | All adapters/repos inherit from ABC |
| Typed Object Registry | Decoupled config, testable | `config.require(ConfigType)` pattern |
| Leaf-level Config Override | Partial nested override works | Env vars override single fields |
| Frozen Dataclasses | Immutability, thread safety | Models raise `FrozenInstanceError` on mutation |
| Separate `*_impl.py` Files | SDK isolation | Clear boundary for SDK imports |
| Fakes over Mocks | Higher confidence, better docs | Test doubles implement full ABC |

---

*This constitution is the authoritative source for project governance. All team members and AI agents MUST adhere to these principles.*
