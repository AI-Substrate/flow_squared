# Expand Language Support for Scanner

**Mode**: Simple

> This specification incorporates findings from research-dossier.md

## Research Context

The research dossier identified critical gaps in fs2's language support:

- **Components affected**: `src/fs2/core/adapters/ast_parser_impl.py` (single file)
- **Critical dependencies**: tree-sitter-language-pack (already available, grammars exist)
- **Modification risks**: Low - additive changes only to static dictionaries
- **Key discovery**: 7 languages in CODE_LANGUAGES have no extension mapping (completely broken)
- **Scope expansion**: Research revealed 116 unmapped languages; prioritized 29 for this plan

See `research-dossier.md` for full analysis including language classification system.

## Summary

**WHAT**: Add file extension mappings for 29 additional programming languages so fs2 can detect and index files written in these languages.

**WHY**: Users scanning projects with GDScript (Godot), Vue/Svelte components, shader files (GLSL/HLSL), hardware description languages (Verilog/VHDL), and other common languages currently get zero indexing for these files. The tree-sitter grammars already exist - fs2 just needs to map file extensions to language names.

## Goals

1. **Enable GDScript indexing** - Immediate user need; Godot game projects should have .gd files searchable
2. **Fix broken CODE_LANGUAGES** - 7 languages claim to support callable extraction but have no extension mapping
3. **Support high-demand languages** - Vue, Svelte, Astro, Solidity, Verilog, VHDL, Nix, Protocol Buffers
4. **Support medium-demand languages** - Fortran, COBOL, Pascal, Ada, LaTeX, Typst for legacy/academic users
5. **Add test coverage** - Representative fixtures for new language categories

## Non-Goals

- Adding all 172 tree-sitter languages (only prioritized 29)
- Creating custom language handlers (DefaultHandler sufficient initially)
- Resolving ambiguous extensions (.v for V vs Verilog, .m for MATLAB vs Objective-C)
- Adding low-demand or internal-only languages (comment, jsdoc, markdown_inline, etc.)
- Performance optimization of parsing

## Complexity

**Score**: CS-2 (small)

**Breakdown**:
| Factor | Score | Rationale |
|--------|-------|-----------|
| Surface Area (S) | 1 | Single source file + test fixtures |
| Integration (I) | 0 | Internal only, no external deps |
| Data/State (D) | 0 | No schema or migration changes |
| Novelty (N) | 0 | Well-specified from research |
| Non-Functional (F) | 0 | No perf/security concerns |
| Testing/Rollout (T) | 1 | Need fixtures + regenerate graph |

**Total**: P = 2 → CS-2

**Confidence**: 0.95 (research was thorough, changes are additive and low-risk)

**Assumptions**:
- tree-sitter grammars work correctly for all added languages
- DefaultHandler produces reasonable node extraction
- No tree-sitter-language-pack version incompatibilities

**Dependencies**:
- Azure OpenAI credentials for full fixture regeneration (optional - quick mode available)

**Risks**:
- Some languages may produce unexpected AST structures (mitigated: can add handlers later)
- Extension conflicts remain unresolved (.v, .m, .pp)

**Phases**:
1. Add extension mappings to EXTENSION_TO_LANGUAGE
2. Add languages to CODE_LANGUAGES where appropriate
3. Add filename mappings (BUILD, meson.build, etc.)
4. Create test fixtures (GDScript + CUDA samples)
5. Regenerate fixture graph
6. Verify with dig-game rescan

## Acceptance Criteria

1. **AC1**: Running `fs2 scan` on a directory containing `.gd` files produces nodes with `language: gdscript` in the graph
2. **AC2**: GDScript files classified as `ContentType.CODE` with callable/type extraction (functions, classes visible)
3. **AC3**: All 7 previously-broken CODE_LANGUAGES (commonlisp, cuda, fortran, glsl, hlsl, matlab, wgsl) have working extension mappings
4. **AC4**: Web framework files (.vue, .svelte, .astro) are detected and indexed
5. **AC5**: Hardware description files (.sv, .svh, .vhd, .vhdl) are detected and indexed
6. **AC6**: `scripts/graph_report.py` shows gdscript language with node count > 0 when run against dig-game
7. **AC7**: `just test` passes after changes
8. **AC8**: Test fixtures include at least one GDScript and one CUDA sample file
9. **AC9**: `just generate-fixtures-quick` completes without error after adding samples

## Risks & Assumptions

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| tree-sitter grammar bugs | Low | Medium | Test with real-world files; can exclude problematic languages |
| Extension conflicts cause confusion | Medium | Low | Document conflicts; defer resolution to future plan |
| Fixture regeneration fails | Low | Medium | Quick mode available without Azure credentials |

**Assumptions**:
- tree-sitter-language-pack includes working grammars for all 29 languages (verified in research)
- Existing scan pipeline handles new languages without modification
- Users with these file types will benefit from indexing (reasonable given research demand analysis)

## Open Questions

1. **Q1**: Should we resolve the `.v` extension conflict (V language vs Verilog)?
   - Current: `.v` maps to V language
   - Option A: Keep as V, use `.sv`/`.svh` for Verilog only
   - Option B: Change to Verilog (more common in industry)
   - **Recommendation**: Option A (non-breaking)

2. **Q2**: Should we add `.m` for MATLAB or Objective-C?
   - Both are valid uses
   - Currently unmapped
   - **Recommendation**: Skip for now, document as known limitation

3. **Q3**: How many test fixture samples to add?
   - Minimum: 1 high-demand (GDScript), 1 medium-demand (CUDA)
   - Maximum: 1 per language category
   - **Recommendation**: Minimum (2 samples) - keeps fixtures lean

## ADR Seeds (Optional)

**Decision Drivers**:
- Minimize breaking changes
- Prioritize commonly-used languages
- Maintain test fixture quality without bloat

**Candidate Alternatives**:
- A: Add only GDScript (minimal fix)
- B: Add GDScript + fix broken CODE_LANGUAGES (7 languages)
- C: Add all high + medium demand languages (29 languages) ← **Selected**
- D: Add all 116 unmapped languages (maximum coverage)

**Stakeholders**:
- fs2 users with Godot/game development projects
- fs2 users with web component frameworks (Vue, Svelte)
- fs2 users with hardware/FPGA projects
- fs2 users with scientific/legacy codebases

---

## Clarifications

### Session 2026-01-02

**Q1: Workflow Mode**
- **Answer**: A (Simple)
- **Rationale**: CS-2 complexity, additive changes only, single source file, high confidence from research

**Q2: Testing Strategy**
- **Answer**: A (Full TDD)
- **Rationale**: Ensure all new language mappings work correctly with comprehensive test coverage

**Q3: Mock Usage**
- **Answer**: A (Avoid mocks entirely)
- **Rationale**: Use test fixture graph pickle only; regenerate if needed; align with existing search/tree tests

---

## Testing Strategy

**Approach**: Full TDD

**Rationale**: Comprehensive testing ensures all 29 new language mappings work correctly and catches any tree-sitter grammar issues early.

**Focus Areas**:
- Language detection for all new extensions
- CODE_LANGUAGES classification (ContentType.CODE vs CONTENT)
- Callable/type extraction for code languages
- Fixture graph regeneration

**Excluded**:
- Performance benchmarking
- Grammar-level parsing correctness (tree-sitter's responsibility)

**Mock Usage**: Avoid mocks entirely
- Use test fixture graph pickle (`tests/fixtures/fixture_graph.pkl`)
- Regenerate fixtures with `just generate-fixtures` when adding new samples
- Align test patterns with existing search and tree tests in codebase

---

**Specification Complete**: 2026-01-02
**Next Step**: Run `/plan-3-architect` to generate the implementation plan
