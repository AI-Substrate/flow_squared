# Smart Content Generation Service

**Mode**: Full

> **This specification incorporates findings from the smart content research session (2025-12-18)**

---

## Research Context

| Aspect | Finding |
|--------|---------|
| **Reference Implementation** | Flowspace `src/modules/smart_content/` (SmartContentService, Jinja2 templates, parallel workers) |
| **Components affected** | `core/models/code_node.py` (add hash field), `core/services/`, `core/adapters/`, new templates |
| **Critical dependencies** | LLMService (007-llm-service plan), existing `CodeNode` model with `smart_content` placeholder |
| **Modification risks** | CodeNode is frozen dataclass - hash field addition is additive; LLMService dependency must be complete |

**Key Flowspace Patterns**:
- Jinja2 templates per node type with token limits (200 file/type, 150 callable)
- SHA-256 hash of raw content triggers regeneration
- Async queue-based parallel processing with configurable workers
- Provenance tracking for future embedding integration

---

## Summary

**WHAT**: Add a SmartContentService that generates AI-powered summaries for every node in the code graph (files, types, callables, sections, blocks, etc.) using the LLMService and Jinja2 templates.

**WHY**: Enable semantic understanding of code at every level of granularity. Smart content transforms raw code into searchable, human-readable descriptions that:
- Power intelligent code search (beyond keyword matching)
- Provide instant context for developers exploring unfamiliar codebases
- Enable AI agents to understand code structure and purpose

---

## Goals

1. **Universal Coverage**: Generate smart content for ALL node categories (file, type, callable, section, block, definition, statement, expression, other)
2. **Template-Driven Generation**: Use Jinja2 templates with category-specific prompts and token limits
3. **Graceful Fallback**: Generic template handles categories without specialized templates
4. **Hash-Based Regeneration**: Only regenerate when source content changes (SHA-256 of `content` field)
5. **Future-Proof Storage**: Store `content_hash` alongside `smart_content` for future embedding regeneration
6. **Batch Processing**: Process multiple nodes efficiently using asyncio Queue + Worker Pool pattern with configurable parallelism (default 50 workers)
7. **Clean Architecture**: Service composes LLMAdapter through LLMService; no direct SDK dependencies
8. **CLI Integration**: Enhance `get-node` command to retrieve raw content or smart content for any node
9. **Strict Exception Layering**: Adapter exceptions stay in the adapter layer; SmartContent service exceptions live in the service layer and may catch/wrap adapter exceptions without duplication

---

## Non-Goals

1. **Embeddings**: Smart content embeddings deferred to future phase (store hash now for compatibility)
2. **Relationship Context**: Initial templates don't inject call graphs or import relationships (Flowspace's `_extract_relationships()` deferred)
3. **Streaming**: Complete responses only; no streaming token output
4. **Cost Tracking**: Token usage reported but not budgeted/enforced
5. **Incremental File Scanning**: Full graph traversal; delta-based updates deferred
6. ~~**CLI Commands**: Service-layer only; CLI integration deferred~~ → **Moved to Goals** (get-node enhancement)

---

## Complexity

**Score**: CS-3 (medium)

**Breakdown**:

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | Multiple files: service, templates (6-9), config, hash utilities |
| Integration (I) | 1 | Internal dependency on LLMService (in progress); no new external deps |
| Data/State (D) | 1 | Add `content_hash` field to CodeNode; no database but model change |
| Novelty (N) | 1 | Well-specified from Flowspace; tree-sitter category mapping needs analysis |
| Non-Functional (F) | 1 | Performance-sensitive (many nodes); configurable parallelism |
| Testing/Rollout (T) | 1 | Integration tests with FakeLLMAdapter; template testing |

**Total**: S(1) + I(1) + D(1) + N(1) + F(1) + T(1) = **6** → **CS-3**

**Confidence**: 0.80 (Flowspace reference strong; tree-sitter category mapping is the main unknown)

**Assumptions**:
- LLMService (007) is complete or near-complete when this work begins
- Jinja2 can be added as dependency (lightweight, no conflicts)
- All 9 CodeNode categories have meaningful content worth summarizing
- Parallel async processing is acceptable (no sync-only constraints)

**Dependencies**:
- **007-llm-service**: Must provide working LLMService with FakeLLMAdapter
- `jinja2` package for template rendering
- `tiktoken` package for token counting (OpenAI tokenizer)
- Existing test fixtures in `tests/fixtures/ast_samples/`

**Risks**:
- Tree-sitter categories may produce nodes where smart content adds no value (e.g., `expression`)
- Template tuning may require iteration to get useful summaries
- Large codebases may have thousands of nodes; parallelism tuning needed

**Phases** (suggested):
1. **Foundation**: CodeNode hash field, template infrastructure, SmartContentService skeleton
2. **Core Templates**: Templates for file, type, callable (the "big three")
3. **Extended Templates**: Templates for section, block, definition + fallback
4. **Processing Engine**: Parallel batch processing with hash-based skip logic
5. **Integration**: Wire to scan pipeline, end-to-end testing

---

## Acceptance Criteria

### AC1: CodeNode Hash Field
**Given** a `CodeNode` with `content` field populated
**When** the node is created or updated
**Then** a `content_hash` field contains the SHA-256 hex digest of `content`

### AC2: Template Selection by Category
**Given** a `CodeNode` with `category="callable"`
**When** SmartContentService generates smart content
**Then** it uses `smart_content_callable.j2` template (not the generic fallback)

### AC3: Fallback Template for Unknown Categories
**Given** a `CodeNode` with `category="other"` or any category without a specific template
**When** SmartContentService generates smart content
**Then** it uses `smart_content_base.j2` (generic fallback) template

### AC4: Token Limits by Category
**Given** templates for different categories
**When** rendering prompts
**Then** token limits are enforced: `file`=200, `type`=200, `callable`=150, others=150 (default)

### AC5: Hash-Based Skip Logic
**Given** a `CodeNode` where `content_hash` matches the hash used to generate existing `smart_content`
**When** SmartContentService processes the node
**Then** it skips regeneration (no LLM call made)

### AC6: Hash-Based Regeneration
**Given** a `CodeNode` where `content` has changed (hash mismatch)
**When** SmartContentService processes the node
**Then** it regenerates `smart_content` and updates the stored hash

### AC7: Batch Processing
**Given** a collection of 100 nodes requiring smart content
**When** `SmartContentService.process(nodes)` is called
**Then** nodes are processed in parallel using asyncio Queue + Worker Pool pattern (configurable workers, default 50) with progress tracking

### AC8: Template Context Variables
**Given** a Jinja2 template
**When** rendering for a CodeNode
**Then** these variables are available: `name`, `qualified_name`, `category`, `ts_kind`, `language`, `content`, `signature`, `max_tokens`

### AC9: Clean Architecture Compliance
**Given** the SmartContentService
**When** it needs LLM capabilities
**Then** it receives LLMService via dependency injection (not direct adapter/SDK access)

### AC10: Integration with FakeLLMAdapter
**Given** tests using `FakeLLMAdapter`
**When** SmartContentService generates smart content
**Then** tests can verify prompts sent and control responses returned

### AC11: Category-to-Template Mapping
**Given** the CodeNode classification system
**When** mapping to templates
**Then** the following mapping applies:
| Category | Template | Token Limit |
|----------|----------|-------------|
| `file` | `smart_content_file.j2` | 200 |
| `type` | `smart_content_type.j2` | 200 |
| `callable` | `smart_content_callable.j2` | 150 |
| `section` | `smart_content_section.j2` | 150 |
| `block` | `smart_content_block.j2` | 150 |
| `definition` | `smart_content_base.j2` (fallback) | 150 |
| `statement` | `smart_content_base.j2` (fallback) | 100 |
| `expression` | `smart_content_base.j2` (fallback) | 100 |
| `other` | `smart_content_base.j2` (fallback) | 100 |

### AC12: CLI get-node Enhancement
**Given** the `get-node` CLI command
**When** called with `--content` or `--smart-content` flag
**Then** it outputs the raw content or smart content (respectively) for the specified node

### AC13: Token-Based Truncation
**Given** a `CodeNode` with content exceeding `smart_content_max_input_tokens` (default 50000)
**When** SmartContentService prepares the prompt
**Then** content is truncated with `[TRUNCATED]` marker and a WARNING is logged with node_id and original token count

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLMService not ready | Medium | High | Can develop templates and service skeleton independently; mock LLMService |
| Low-value summaries for some categories | Medium | Low | Skip or use minimal templates for `statement`, `expression` |
| Template prompt engineering iteration | High | Medium | Start with Flowspace templates as baseline; iterate based on output quality |
| Large codebase performance | Medium | Medium | Configurable parallelism; hash-based skip avoids redundant calls |
| Token limit exceeded by large nodes | Low | Low | Truncate content in template context; note truncation in prompt |

### Assumptions

1. LLMService provides async `generate(prompt, max_tokens)` interface
2. Jinja2 is acceptable as a dependency (standard, no conflicts)
3. All CodeNode instances have populated `content` field
4. SHA-256 hashing is fast enough for inline computation
5. Smart content quality is acceptable with simple single-shot prompts (no multi-turn refinement)

---

## Open Questions

1. ~~**[RESOLVED: Category Skip List]**~~ Process all categories - no skip logic (Q5)

2. ~~**[RESOLVED: Content Truncation]**~~ Token-based truncation with tiktoken at 50k tokens; log WARNING (Q6)

3. ~~**[RESOLVED: Hash Storage Location]**~~ Computed at CodeNode creation/update time by scanner (Q7)

---

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Hash logic, template selection, and parallel processing require comprehensive coverage; FakeLLMAdapter enables isolated testing
- **Focus Areas**:
  - Hash computation and comparison logic
  - Template selection by category
  - Token-based truncation with tiktoken
  - Parallel batch processing
  - CLI flag handling (`--content`, `--smart-content`)
- **Excluded**: Real LLM API calls in automated tests
- **Mock Usage**: Targeted mocks (B)
  - **Policy**: Use FakeLLMAdapter for all automated tests; real LLM reserved for manual validation
  - **Location**: FakeLLMAdapter from 007-llm-service
  - **Manual Testing**: Real LLM calls before release to validate prompt quality

---

## Documentation Strategy

- **Location**: docs/how/ only (B)
- **Rationale**: Infrastructure feature with CLI enhancement; detailed guides more appropriate than README
- **Target Audience**: Developers using smart content features, template customizers
- **Planned Content**:
  - `docs/how/smart-content.md` — Service usage, template customization, CLI flags, configuration
- **Maintenance**: Update when adding new templates or changing token limits

---

## ADR Seeds (Optional)

### Decision: Template System

**Decision Drivers**:
- Need customizable prompts per node category
- Must support token limit injection
- Should be maintainable without code changes

**Candidate Alternatives**:
- A) **Jinja2 Templates** (recommended): File-based templates, powerful templating, widely known
- B) **Python f-strings**: Simpler but less flexible; prompts in code
- C) **Mako/Django Templates**: More complex than needed; less common in non-web Python

**Stakeholders**: Core maintainers, prompt engineers tuning smart content quality

### Decision: Hash Storage Strategy

**Decision Drivers**:
- Need to detect content changes efficiently
- Must support future embedding regeneration
- Should not require rescanning to detect changes

**Candidate Alternatives**:
- A) **Inline `content_hash` field** (recommended): Hash stored on CodeNode; computed at creation
- B) **Separate provenance tracking**: More complex; needed for multi-source hashes
- C) **Recompute on demand**: No storage; slower comparison

---

## Template Directory Structure

```
src/fs2/core/templates/smart_content/
├── smart_content_file.j2       # File-level summaries
├── smart_content_type.j2       # Class/struct/interface summaries
├── smart_content_callable.j2   # Function/method summaries
├── smart_content_section.j2    # Markdown heading summaries
├── smart_content_block.j2      # IaC block summaries
└── smart_content_base.j2       # Fallback for other categories
```

---

## Category Analysis (from test fixtures)

Based on `tests/fixtures/ast_samples/` and `classify_node()`:

| Category | Example ts_kind | Smart Content Value | Template Priority |
|----------|-----------------|---------------------|-------------------|
| `file` | `module`, `program` | High - file purpose | P1 |
| `type` | `class_definition` | High - class responsibility | P1 |
| `callable` | `function_definition` | High - function purpose | P1 |
| `section` | `atx_heading` | Medium - section topic | P2 |
| `block` | `block`, `FROM_instruction` | Medium - IaC purpose | P2 |
| `definition` | `variable_definition` | Low - what it stores | P3 (fallback) |
| `statement` | `if_statement` | Low - control flow | P3 (fallback) |
| `expression` | `call_expression` | Very Low - may skip | P3 (fallback) |
| `other` | unknown types | Varies - generic summary | P3 (fallback) |

---

---

## Clarifications

### Session 2025-12-18

**Q1: Workflow Mode**
- **Answer**: B (Full)
- **Rationale**: CS-3 complexity with 5 phases and LLMService dependency warrants comprehensive gates
- **Impact**: Multi-phase plan with required dossiers; all gates (plan-4, plan-5) required

**Q2: Testing Strategy**
- **Answer**: A (Full TDD)
- **Rationale**: Hash logic, template selection, and parallel processing require comprehensive coverage; FakeLLMAdapter enables isolated testing
- **Impact**: Tests written before/alongside implementation; all ACs have corresponding tests

**Q3: Mock/Stub Policy**
- **Answer**: B (Targeted mocks)
- **Rationale**: Use FakeLLMAdapter for automated tests (regeneration, hash logic, template selection); real LLM calls reserved for manual validation
- **Impact**: Unit/integration tests use FakeLLMAdapter; manual testing with real LLM before release

**Q4: Documentation Strategy**
- **Answer**: B (docs/how/ only)
- **Rationale**: Infrastructure feature with CLI enhancement; detailed guides more appropriate than README
- **Impact**: Create `docs/how/smart-content.md` covering service usage, template customization, and CLI flags

**Q5: Category Skip List**
- **Answer**: A (Process all)
- **Rationale**: Universal coverage - every node gets smart content regardless of category
- **Impact**: No skip logic needed; all 9 categories processed with appropriate templates

**Q6: Content Truncation Strategy**
- **Answer**: Token-based truncation with tiktoken
- **Rationale**: Use tiktoken (OpenAI tokenizer) for accurate token counting; configurable limit starting at 50k tokens
- **Impact**: Add `tiktoken` dependency; truncate content exceeding token limit with marker; config option `smart_content_max_input_tokens` (default: 50000); log WARNING when truncation occurs
  - `tiktoken` is a required dependency in this repo and is installed via `uv` for dev/CI.

**Q7: Hash Storage Location**
- **Answer**: A (Creation/update time - scanner responsibility)
- **Rationale**: Hash computed when CodeNode is created or updated; scanner owns data integrity; hash always present
- **Impact**: Scanner computes `content_hash` at node creation; SmartContentService only reads/compares hashes

**Q8: Config Key Path for Smart Content**
- **Answer**: Use YAML key `smart_content:` (and env prefix `FS2_SMART_CONTENT__...`)
- **Rationale**: `ConfigurationService` binds config objects by `__config_path__`; SmartContentConfig must set `__config_path__ = "smart_content"` to match docs/examples
- **Impact**: All documentation and examples use `smart_content:` as the canonical YAML section for Smart Content settings

---

## Coverage Summary

| Category | Status | Details |
|----------|--------|---------|
| Workflow Mode | **Resolved** | Full mode (multi-phase, all gates) |
| Testing Strategy | **Resolved** | Full TDD with FakeLLMAdapter |
| Mock Policy | **Resolved** | Targeted mocks; real LLM for manual testing |
| Documentation | **Resolved** | docs/how/ only |
| Category Skip List | **Resolved** | Process all categories |
| Content Truncation | **Resolved** | tiktoken at 50k tokens + WARNING log |
| Hash Storage | **Resolved** | Scanner computes at creation/update |

**All critical ambiguities resolved. Specification ready for architecture.**

---

**Specification Status**: Ready for architecture
**Next Step**: Run `/plan-3-architect` to generate the phase-based plan
