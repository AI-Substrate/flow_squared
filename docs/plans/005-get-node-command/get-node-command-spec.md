# Get Node Command

**Mode**: Simple

> Retrieve a single code node by ID and output as JSON for scripting and tool integration.

---

## Research Context

This specification incorporates findings from `research-dossier.md` (60 findings across 6 subagents).

| Aspect | Summary |
|--------|---------|
| **Components Affected** | `src/fs2/cli/get_node.py` (new), `src/fs2/cli/main.py` (register) |
| **Critical Dependencies** | GraphStore.get_node(), CodeNode, TreeConfig, dataclasses.asdict() |
| **Modification Risks** | Low - isolated new command, no changes to existing behavior |
| **Key Insight** | Clean piping requires bypassing Rich Console; use raw `print()` for JSON |

See `research-dossier.md` for full analysis.

---

## Summary

**WHAT**: A new CLI command `fs2 get-node` that retrieves a single CodeNode from the graph store by its node_id and outputs the complete node data as JSON.

**WHY**: Users need programmatic access to individual code nodes for:
- Scripting and automation (CI/CD pipelines)
- Integration with JSON-processing tools (`jq`, `yq`)
- Debugging and inspection of indexed code structures
- Building custom tooling on top of the fs2 graph

The command must produce clean stdout output (no logging, no Rich formatting) so it can be piped directly to tools like `jq`.

---

## Goals

1. **Retrieve any node by ID**: Given a valid node_id, output the complete CodeNode as JSON
2. **Clean stdout for piping**: Zero non-error output besides the JSON data, enabling `fs2 get-node ... | jq`
3. **File output option**: Optionally save JSON to a file instead of stdout
4. **Clear error messages**: Informative errors to stderr for missing nodes, missing graph, or corrupted data
5. **Consistent exit codes**: Follow existing convention (0=success, 1=user error, 2=system error)

---

## Non-Goals

1. **Batch retrieval**: This command retrieves ONE node; batch operations are out of scope
2. **Query/search**: No pattern matching or filtering; use `fs2 tree` for that
3. **Node modification**: Read-only; no editing or updating nodes
4. **Graph traversal**: No following relationships; returns single node only
5. **Verbose/debug mode**: Contradicts clean piping requirement; not supported
6. **Custom output formats**: JSON only (no YAML, no plain text summaries)

---

## Complexity

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| **Surface Area (S)** | 1 | New file + main.py registration |
| **Integration (I)** | 0 | Internal APIs only (GraphStore, CodeNode) |
| **Data/State (D)** | 0 | No schema changes, reads existing graph |
| **Novelty (N)** | 0 | Very well-specified from research |
| **Non-Functional (F)** | 1 | Strict stdout discipline for piping |
| **Testing/Rollout (T)** | 1 | Integration tests for piping behavior |

**Score**: CS-2 (small)
**Total Points**: 3 (S=1 + I=0 + D=0 + N=0 + F=1 + T=1)
**Confidence**: 0.95
**Assumptions**:
- GraphStore.get_node() exists and works correctly (verified in research)
- dataclasses.asdict() handles all CodeNode fields (verified in research)
- Existing test infrastructure (CliRunner, fixtures) is reusable

**Dependencies**: None external; all dependencies are internal

**Risks**:
- Low: Well-understood problem with clear solution from research
- Piping discipline must be maintained (no accidental console.print)

**Phases**: Single phase (CS-2 does not require staged rollout)

---

## Acceptance Criteria

### AC1: Basic Node Retrieval
**Given** a scanned project with a graph containing nodes
**When** the user runs `fs2 get-node "file:src/main.py"`
**Then** the command outputs the complete CodeNode as valid JSON to stdout
**And** exits with code 0

### AC2: Clean Stdout for Piping
**Given** a valid node_id
**When** the user runs `fs2 get-node "<node_id>"`
**Then** stdout contains ONLY the JSON object (no logs, no Rich formatting)
**And** the output is directly parseable by `json.loads()`

### AC3: Pipe to jq
**Given** a valid node_id
**When** the user runs `fs2 get-node "<node_id>" | jq '.signature'`
**Then** jq successfully parses the output and extracts the field

### AC4: File Output Option
**Given** a valid node_id and `--file output.json` flag
**When** the user runs `fs2 get-node "<node_id>" --file output.json`
**Then** the JSON is written to `output.json`
**And** a success message appears on stderr (not stdout)
**And** exits with code 0

### AC5: Node Not Found Error
**Given** a node_id that does not exist in the graph
**When** the user runs `fs2 get-node "nonexistent:node"`
**Then** an error message is printed to stderr
**And** exits with code 1

### AC6: Missing Graph Error
**Given** a project without a scanned graph (no `.fs2/graph.pickle`)
**When** the user runs `fs2 get-node "<node_id>"`
**Then** an error message instructs the user to run `fs2 scan` first
**And** exits with code 1

### AC7: Corrupted Graph Error
**Given** a corrupted graph file
**When** the user runs `fs2 get-node "<node_id>"`
**Then** an error message indicates the graph is corrupted
**And** exits with code 2

### AC8: Help Text
**Given** the user runs `fs2 get-node --help`
**Then** usage information is displayed including:
- Description of the command
- node_id argument explanation
- --file option explanation
- Example usage

### AC9: Essential CodeNode Fields Present
**Given** a valid node_id
**When** the JSON is output
**Then** essential CodeNode fields are present in the JSON object (node_id, category, content, start_line, language)

**Note**: Per Insight #2 from clarification session - testing essential fields (not hardcoded 22) makes tests resilient to CodeNode schema changes. All fields are serialized; tests verify key fields are present.

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Accidental stdout pollution | Low | High | Use raw `print()` not `console.print()`; test with `json.loads()` |
| Large node content | Low | Medium | CodeNode already handles truncation; `content` field can be large |
| Invalid node_id format | Low | Low | Treat as "not found"; no special validation needed |

### Assumptions

1. **GraphStore.get_node() is reliable**: O(1) lookup, returns None for missing nodes
2. **CodeNode is JSON-serializable**: All fields can be serialized via `asdict()` + `json.dumps(default=str)`
3. **TreeConfig.graph_path is reusable**: Same config key as `fs2 tree` command
4. **Test infrastructure exists**: CliRunner, FakeGraphStore, session fixtures available

---

## Open Questions

None. The research phase thoroughly explored the implementation approach and resolved all technical questions.

---

## ADR Seeds (Optional)

### ADR-SEED-001: Stdout Discipline for Machine-Readable Output

**Decision Drivers**:
- Command output must be directly pipeable to JSON tools (`jq`, `yq`)
- Errors must be visible to users but not pollute stdout
- No feature flags or verbose modes that could break piping

**Candidate Alternatives**:
- A: Raw `print()` for JSON, `Console(stderr=True)` for errors (RECOMMENDED)
- B: `--quiet` flag to suppress non-JSON output (complexity for simple use case)
- C: Detect TTY and switch behavior (inconsistent, breaks scripting)

**Stakeholders**: CLI users, script authors, CI/CD pipeline integrators

---

## Testing Strategy

**Approach**: Full TDD
**Rationale**: User specified "full TDD" - tests written before implementation for all acceptance criteria
**Focus Areas**:
- AC1-AC3: Core retrieval and piping behavior (critical path)
- AC4: File output option
- AC5-AC7: Error handling scenarios
- AC8: Help text verification
- AC9: Essential CodeNode fields (resilient to schema changes)

**Excluded**: None - Full TDD covers all acceptance criteria

**Mock Usage**: Avoid mocks entirely
**Mock Rationale**: Use real data/fixtures only; leverage existing session-scoped graph fixtures

---

## Documentation Strategy

**Location**: No new documentation
**Rationale**: Command is self-documenting via `--help`; usage is straightforward
**Target Audience**: N/A - CLI help text sufficient
**Maintenance**: Update `--help` text if behavior changes

---

## Clarifications

### Session 2025-12-17

**Q1: What workflow mode fits this task?**

| Option | Mode | Best For | What Changes |
|--------|------|----------|--------------|
| A | Simple | CS-1/CS-2 tasks, single phase, quick path to implementation | Single-phase plan, inline tasks, plan-4/plan-5 optional |
| B | Full | CS-3+ features, multiple phases, comprehensive gates | Multi-phase plan, required dossiers, all gates |

**Answer**: A (Simple)
**Rationale**: CS-2 complexity, well-researched, single-phase implementation

---

**Q2: What testing approach best fits this feature's complexity and risk profile?**

| Option | Approach | Best For | Test Coverage |
|--------|----------|----------|---------------|
| A | Full TDD | Complex logic, algorithms, APIs | Comprehensive unit/integration/e2e tests |
| B | TAD (Test-Assisted Development) | Features needing executable documentation | Tests as high-fidelity docs; iterative refinement |
| C | Lightweight | Simple operations, config changes | Core functionality validation only |
| D | Manual Only | One-time scripts, trivial changes | Document manual verification steps |
| E | Hybrid | Mixed complexity features | TDD for complex, TAD/lightweight for others |

**Answer**: A (Full TDD)
**Rationale**: User specified "full TDD" - ensures comprehensive test coverage for all ACs

---

**Q3: How should mocks/stubs/fakes be used during implementation?**

| Option | Policy | Typical Use |
|--------|--------|-------------|
| A | Avoid mocks entirely | Real data/fixtures only |
| B | Allow targeted mocks | Limited to external systems or slow dependencies |
| C | Allow liberal mocking | Any component may be mocked when beneficial |

**Answer**: A (Avoid mocks entirely)
**Rationale**: Use real data/fixtures only; leverage existing session-scoped graph fixtures

---

**Q4: Where should this feature's documentation live?**

| Option | Location | Best For |
|--------|----------|----------|
| A | README.md only | Quick-start essentials, simple features |
| B | docs/how/ only | Detailed guides, complex workflows |
| C | Hybrid (README + docs/how/) | Features needing both quick-start and depth |
| D | No new documentation | Internal/trivial changes, self-documenting |

**Answer**: D (No new documentation)
**Rationale**: Command is self-documenting via `--help`; usage is straightforward

---

### Clarification Summary

| Category | Status | Notes |
|----------|--------|-------|
| Mode | Resolved | Simple |
| Testing Strategy | Resolved | Full TDD |
| Mock Policy | Resolved | Avoid mocks entirely |
| Documentation | Resolved | No new docs needed |
| FRs | Complete | 9 ACs defined |
| NFRs | Complete | Clean stdout for piping |
| Edge Cases | Complete | AC5-AC7 cover errors |

**Outstanding**: None
**Deferred**: None

---

## Specification Complete

| Check | Status |
|-------|--------|
| WHAT/WHY defined | Yes |
| Goals are user-value focused | Yes |
| Non-goals explicitly stated | Yes |
| Acceptance criteria are testable | Yes |
| Complexity scored | CS-2 (small) |
| No implementation details | Yes (spec is tech-agnostic) |
| Research incorporated | Yes |

---

**Spec Location**: `docs/plans/005-get-node-command/get-node-command-spec.md`
**Research**: `docs/plans/005-get-node-command/research-dossier.md`
**Next Step**: Run `/plan-3-architect` to generate single-phase implementation plan
