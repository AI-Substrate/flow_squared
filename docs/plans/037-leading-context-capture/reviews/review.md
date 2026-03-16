# Code Review: Leading Context Capture

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-spec.md
**Phase**: Simple Mode
**Date**: 2026-03-16
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

The phase is close, but one correctness bug is still present in the embedding staleness logic and the review artifacts overclaim acceptance-criteria coverage that the committed tests do not actually prove.

**Key failure areas**:
- **Implementation**: `embedding_hash` is computed from a different string than the one actually embedded, so stale-embedding detection can miss real payload changes.
- **Domain compliance**: The committed integration test file does not match the plan/dossier manifest, leaving one changed file outside the approved file map.
- **Testing**: AC13 is marked complete without evidence for TSX, JavaScript, C++, Ruby, or Bash; AC08 and AC09 are still only indirectly evidenced.

## B) Summary

The feature is well aligned with the spec overall: `leading_context` is threaded through parsing, search, embeddings, smart-content prompting, CLI output, and MCP output without obvious boundary violations or reinvention. Static review did not find security issues, and the targeted feature tests currently pass (`25 passed`).

However, the embedding pipeline hashes `content + leading_context` while `_chunk_content()` actually embeds `leading_context + "\n" + content`, which makes `embedding_hash` an unreliable freshness key. In addition, the phase artifacts claim `13/13` acceptance criteria verified, but the committed parser tests and execution log only evidence 8 of the 13 promised languages.

The repository snapshot also lacks `docs/domains/` and `docs/project-rules/`, so registry/map/harness checks are unavailable rather than failed. The only concrete scope/compliance drift inside this phase is the integration-test path mismatch between the manifest/dossier and the committed file.

## C) Checklist

**Testing Approach: Hybrid**

- [ ] Parser-edge-case work has concrete RED → GREEN evidence recorded
- [x] Parser edge-case tests exist for core wrapper/gap cases
- [ ] Lightweight integration checks directly verify semantic-search behavior (AC08)
- [ ] Lightweight integration checks directly verify smart-content behavior (AC09)
- [ ] Key verification points are fully documented with reproducible evidence

**Universal (all approaches)**

- [ ] Only in-scope files changed
- [ ] Linters/type checks clean (if applicable)
- [ ] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/embedding/embedding_service.py:220-225,521-527,775-779`<br>`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_leading_context_integration.py:106-121` | correctness | `embedding_hash` is calculated from `content + leading_context`, but embeddings are generated from `leading_context + "\n" + content`. | Hash the exact raw-embedding payload in both `_should_skip()` and result reassembly, then replace the arithmetic-only test with an `EmbeddingService`-level assertion. |
| F002 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md:101-103`<br>`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/execution.log.md:15-16,36-37`<br>`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/tasks.fltplan.md:14-15,128-150`<br>`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_leading_context.py:24-161` | testing | The phase claims AC13 and `13/13` AC verification, but the committed parser tests and log only evidence Python, Go, Rust, Java, TypeScript, C, GDScript, and CUDA. | Add tests or concrete fixture-scan evidence for TSX, JavaScript, C++, Ruby, and Bash, then update the plan/log/flight-plan claims to match reality. |
| F003 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_leading_context_integration.py:1-145`<br>`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/execution.log.md:20-32` | testing | AC08 and AC09 are wired in code, but there is no direct verification artifact showing semantic-search behavior or smart-content output changing because of `leading_context`. | Add deterministic tests or saved outputs for the embedding payload / semantic-search path and for the smart-content prompt/output path. |
| F004 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md:37-38`<br>`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/tasks.md:114-115`<br>`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/tasks.fltplan.md:71-73,149-150`<br>`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_leading_context_integration.py:1-145` | scope | The manifest/dossier expect `tests/unit/services/search/test_leading_context_search.py`, but the committed file is `tests/unit/services/test_leading_context_integration.py`. | Rename/move the file to the planned path or update the plan/task artifacts so the approved file list matches the actual change set. |
| F005 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_leading_context_integration.py:7-13,45`<br>`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/execution.log.md:36-37` | pattern | The new integration test file fails Ruff (unsorted imports and unused imports), so the logged `Zero ruff violations` claim is not reproducible. | Remove the unused imports, sort the import block, rerun Ruff, and attach the actual lint output to the execution log. |

## E) Detailed Findings

### E.1) Implementation Quality

Implementation quality is otherwise solid: parser extraction, search integration, and output exposure all line up with the feature intent, and no material security or performance issues stood out. The one blocking correctness issue is F001.

- **F001**: `_chunk_content()` embeds `"\n".join([leading_context, content])`, but `_should_skip()` and the final `replace()` call both hash `node.content + node.leading_context`. Those are different payloads and can produce false freshness matches for certain content/context combinations.
- The new integration test repeats the same incorrect formula instead of asserting against the actual `EmbeddingService` payload, so the bug is currently locked in by test coverage instead of caught by it.

### E.2) Domain Compliance

Repository note: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/` does not exist in this snapshot, so registry/domain-map/domain.md checks are unavailable rather than auto-failed.

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | Source files remain under the expected `src/fs2/...` trees; test files remain under `tests/...`. |
| Contract-only imports | ✅ | No cross-domain internal-import violations were identified in the changed code. |
| Dependency direction | ✅ | Changes preserve the documented Clean Architecture flow from AGENTS.md / CLAUDE.md. |
| Domain.md updated | N/A | No `docs/domains/<slug>/domain.md` files exist in this repository snapshot. |
| Registry current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/registry.md` is absent repo-wide. |
| No orphan files | ❌ | F004: the committed integration test path is not the path declared in the plan manifest / tasks dossier. |
| Map nodes current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/domain-map.md` is absent repo-wide. |
| Map edges current | N/A | Domain-map edge validation is unavailable because no domain map exists. |
| No circular business deps | ✅ | No new business-to-business cycles were introduced in the reviewed scope. |
| Concepts documented | N/A | No domain docs / Concepts tables exist in this repository snapshot. |

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| `CodeNode.leading_context` contract surface | None | models | ✅ proceed |
| `_extract_leading_context()` sibling-walk extraction | None | adapters | ✅ proceed |
| `leading_context` search / embedding / prompt wiring | None | search / embedding / smart_content | ✅ proceed |

No genuine duplication was found. This phase extends existing CodeNode/search/embedding/smart-content flows rather than reinventing a parallel subsystem.

### E.4) Testing & Evidence

**Coverage confidence**: 59%

Note: the Simple-mode default execution-log path (`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/execution.log.md`) was absent. Review used the actual implementation log at `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/execution.log.md`.

Observed validation during review:
- `uv run python -m pytest -q tests/unit/adapters/test_leading_context.py tests/unit/services/test_leading_context_integration.py` → **25 passed**
- `uv run ruff check tests/unit/services/test_leading_context_integration.py` → **4 errors** (import sorting + unused imports)

| AC | Confidence | Evidence |
|----|------------|----------|
| AC01 | 65 | `CodeNode` adds `leading_context` with a default and threads it through factory methods, but there is no explicit old-graph load/unpickle regression in the committed scope. |
| AC02 | 85 | Parser tests verify Python comment capture on `AuthenticationError` and `has_permission`; targeted pytest passed. |
| AC03 | 78 | Parser tests verify decorator capture for `@dataclass` and `@property`; targeted pytest passed. |
| AC04 | 96 | Dedicated tmp-file test verifies blank-line separation stops unrelated comment capture. |
| AC05 | 90 | TypeScript parser test verifies exported callables capture JSDoc across `export_statement` wrapping. |
| AC06 | 92 | Rust tests verify both `///` docs and `#[derive(...)]` attributes are captured. |
| AC07 | 68 | Integration tests verify `RegexMatcher` finds `leading_context` at score `0.6`; no end-to-end CLI `search` artifact was committed. |
| AC08 | 32 | Code prepends `leading_context` before chunking, but no committed test or saved search run proves semantic-search behavior actually changes. |
| AC09 | 28 | Code wires `leading_context` into smart-content context and templates, but no committed test or rendered-output artifact proves summaries reference it. |
| AC10 | 96 | Dedicated truncation test verifies `leading_context` is capped with `[TRUNCATED]`. |
| AC11 | 88 | Parser + integration tests verify `content_hash` stability across comment changes. |
| AC12 | 58 | The committed test proves the intended hash formula differs when `leading_context` exists, but it does not exercise the actual `EmbeddingService` logic—and the service currently hashes the wrong payload (F001). |
| AC13 | 30 | The committed parser tests and execution log only cover 8 languages: Python, Go, Rust, Java, TypeScript, C, GDScript, and CUDA. TSX, JavaScript, C++, Ruby, and Bash remain unverified in the review scope. |

### E.5) Doctrine Compliance

N/A — no `docs/project-rules/` directory exists in this repository snapshot. A direct AGENTS.md / CLAUDE.md sanity check did not add separate findings beyond F001, F004, and F005.

### E.6) Harness Live Validation

N/A — no harness configured. `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/harness.md` is absent, so live validation was skipped.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC01 | CodeNode field exists and stays backward compatible | New dataclass field + factory threading; no dedicated old-graph regression test in scope | 65 |
| AC02 | Python comments above definitions populate `leading_context` | Python parser tests on fixture classes/methods | 85 |
| AC03 | Python decorators are captured | `@dataclass` / `@property` parser tests | 78 |
| AC04 | Blank-line gap rule excludes unrelated comments | Dedicated tmp-file parser test | 96 |
| AC05 | TypeScript `export function` captures wrapper-sibling comments | TypeScript fixture parser test | 90 |
| AC06 | Rust attributes are captured | Rust parser tests for doc comments + `#[derive(...)]` | 92 |
| AC07 | Text search matches in `leading_context` | `RegexMatcher` integration tests at score `0.6` | 68 |
| AC08 | Semantic search includes `leading_context` in embedding | Static code wiring only; no direct semantic-search evidence | 32 |
| AC09 | Smart content uses developer comments | Static context/template wiring only; no direct output evidence | 28 |
| AC10 | `leading_context` capped at 2000 chars | Truncation parser test | 96 |
| AC11 | `content_hash` stays code-only | Parser + integration hash-stability tests | 88 |
| AC12 | `embedding_hash` changes when `leading_context` changes | Intended by tests, but currently incorrect in `EmbeddingService` (F001) | 58 |
| AC13 | All 13 fixture languages produce `leading_context` | Only 8 languages evidenced in changed tests/log | 30 |

**Overall coverage confidence**: 59%

## G) Commands Executed

```bash
git --no-pager diff --stat && printf '\n---STAGED---\n' && git --no-pager diff --staged --stat && printf '\n---LOG---\n' && git --no-pager log --oneline -10
git --no-pager show --stat --name-status --format=fuller 3e83eb3 && printf '\n---NEXT---\n' && git --no-pager show --stat --name-status --format=fuller a0ce173
mkdir -p docs/plans/037-leading-context-capture/reviews && git --no-pager diff --name-status 7ec9d3b..a0ce173 > docs/plans/037-leading-context-capture/reviews/_computed.manifest && git --no-pager diff 7ec9d3b..a0ce173 > docs/plans/037-leading-context-capture/reviews/_computed.diff && git --no-pager diff --stat 7ec9d3b..a0ce173
git --no-pager diff 7ec9d3b..a0ce173 -- src/fs2/core/services/embedding/embedding_service.py tests/unit/services/test_leading_context_integration.py | sed -n '1,220p'
git --no-pager diff 7ec9d3b..a0ce173 -- src/fs2/mcp/server.py | sed -n '1,120p'
uv run ruff check src/fs2/cli/get_node.py src/fs2/core/adapters/ast_parser_impl.py src/fs2/core/models/code_node.py src/fs2/core/services/embedding/embedding_service.py src/fs2/core/services/search/regex_matcher.py src/fs2/core/services/smart_content/smart_content_service.py src/fs2/mcp/server.py tests/unit/adapters/test_leading_context.py tests/unit/services/test_leading_context_integration.py
uv run ruff check tests/unit/services/test_leading_context_integration.py
uv run python -m pytest -q tests/unit/adapters/test_leading_context.py tests/unit/services/test_leading_context_integration.py
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-spec.md
**Phase**: Simple Mode
**Tasks dossier**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/reviews/review.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md | Needs update | plan/docs | Update AC verification counts after missing-language evidence is added |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/execution.log.md | Needs update | docs/evidence | Replace unsupported coverage/lint claims with concrete outputs |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/tasks.fltplan.md | Needs update | docs/flight-plan | Align AC13 and integration-test path claims with the actual implementation |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/get_node.py | Reviewed clean | cli | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/ast_parser_impl.py | Reviewed clean | adapters | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/models/code_node.py | Reviewed clean | models | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/embedding/embedding_service.py | Needs fix | embedding | Fix payload/hash mismatch in `_should_skip()` and final `embedding_hash` assignment |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/search/regex_matcher.py | Reviewed clean | search | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/smart_content/smart_content_service.py | Reviewed clean | smart_content | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/templates/smart_content/smart_content_base.j2 | Reviewed clean | smart_content | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/templates/smart_content/smart_content_block.j2 | Reviewed clean | smart_content | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/templates/smart_content/smart_content_callable.j2 | Reviewed clean | smart_content | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/templates/smart_content/smart_content_file.j2 | Reviewed clean | smart_content | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/templates/smart_content/smart_content_section.j2 | Reviewed clean | smart_content | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/templates/smart_content/smart_content_type.j2 | Reviewed clean | smart_content | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/mcp/server.py | Reviewed clean | mcp | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_leading_context.py | Needs expansion | tests | Add missing language coverage or equivalent concrete evidence for AC13 |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_leading_context_integration.py | Needs fix | tests | Fix the hash assertion, add AC08/AC09 evidence, and clean Ruff issues |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/embedding/embedding_service.py | Hash the exact raw-embedding payload, not `content + leading_context` | `embedding_hash` must represent the embedded bytes or stale-checks can miss real changes |
| 2 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_leading_context_integration.py | Replace formula-only hash assertions with `EmbeddingService`-level assertions | Current tests encode the same broken hash formula instead of catching it |
| 3 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_leading_context.py | Add coverage for TSX, JavaScript, C++, Ruby, and Bash | AC13 is currently overclaimed |
| 4 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md | Update `ACs verified` once missing evidence is added or stop claiming full verification | Current status says `13/13` without sufficient evidence |
| 5 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/execution.log.md | Record real Ruff/test outputs and remove unsupported AC08/AC09/AC13 claims | The current log overstates verification and lint cleanliness |
| 6 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/tasks.md | Align the expected integration-test path with the committed file | The manifest currently points to a different file than the one reviewed |
| 7 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/tasks.fltplan.md | Align the integration-test path and AC13 completion checkboxes with the actual implementation | The flight plan currently mirrors the same drift |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md | Accurate AC verification count after missing-language evidence is added |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/execution.log.md | Concrete lint/test outputs and corrected evidence claims |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/tasks/implementation/tasks.fltplan.md | Correct integration-test path and AC13 status |

### Next Step

Apply the fixes with `/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md`, then re-run `/plan-7-v2-code-review --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/037-leading-context-capture/leading-context-capture-plan.md`.
