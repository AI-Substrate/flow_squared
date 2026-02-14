# Agent Onboarding CLI Commands

**Mode**: Simple

> This specification incorporates findings from `research-dossier.md` and the workshop `workshops/agent-onboarding-experience.md`.

---

## Research Context

- **Components affected**: CLI layer (`main.py`, new command modules), Docs layer (`registry.yaml`, optional new bundled doc)
- **Critical dependencies**: `DocsService` (existing, stable), `Rich Console`, `Typer`, config path checks
- **Modification risks**: Low -- extending CLI with new unguarded commands follows established patterns. No changes to existing commands or services.
- **Key discoveries**: Bootstrap paradox (docs only accessible via MCP, but agents need docs to set up MCP). Doctor spec (Plan 017) explicitly deferred "interactive wizard" as a separate feature. Config template (Plan 025) already has worked provider examples.
- **Link**: See `research-dossier.md` for full analysis

---

## Summary

Add two new CLI commands -- `fs2 agents-start-here` and `fs2 docs` -- that let AI agents self-serve the entire fs2 setup journey from the terminal. Today, an agent cannot discover fs2 documentation without an already-working MCP connection. These commands break that bootstrap paradox: a human installs fs2, tells their agent "help me set up fs2," and the agent can orient itself, read configuration guides, set up providers, scan the codebase, and connect MCP -- all by running shell commands and reading their output.

**Why**: MCP is the destination -- once connected, agents have native tool access (`tree()`, `search()`, `docs_get()`). But to get there, the agent needs a CLI bootstrap path. These two commands are that path.

---

## Goals

- **G1**: An agent with zero prior knowledge of fs2 can run `fs2 agents-start-here` and understand what fs2 is, what's currently set up, and exactly what to do next.
- **G2**: An agent can browse and read all bundled documentation via `fs2 docs` / `fs2 docs <id>` without MCP being connected.
- **G3**: The `agents-start-here` output adapts based on project state (nothing set up, initialized, configured, scanned) so the "next step" guidance is always relevant.
- **G4**: The complete journey from zero to MCP-connected agent takes no more than ~10 CLI commands for a full setup (with providers) or ~5 for a basic setup (no providers).
- **G5**: Both commands work before `fs2 init` -- they are unguarded and have zero dependencies on config or graph.
- **G6**: The `fs2 docs` command output mirrors the MCP `docs_list`/`docs_get` response format in JSON mode, creating consistency between CLI and MCP access paths.

---

## Non-Goals

- **NG1**: Interactive configuration wizard -- the command displays guidance, it does not prompt for input or edit files.
- **NG2**: Auto-detection of provider credentials -- the agent reads the configuration guide and makes decisions based on what the human tells it.
- **NG3**: Replacing or duplicating the existing `agents.md` bundled doc -- the new command complements it by covering the setup journey (agents.md covers tool usage after setup).
- **NG4**: Supporting non-agent users as the primary audience -- the commands are optimized for LLM agent consumption (parseable text output, JSON mode) though humans can use them too.
- **NG5**: Automatic MCP setup -- the agent reads the MCP server guide and follows the instructions; the command does not run `claude mcp add` or modify MCP config files.

---

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=1, I=0, D=0, N=0, F=0, T=1
  - **S=1** (Surface Area): Two new CLI modules, main.py registration, two test files, optional registry.yaml + bundled doc
  - **I=0** (Integration): All internal dependencies (DocsService, Rich, Typer) -- no external services
  - **D=0** (Data/State): No schema changes, no migrations, no new models
  - **N=0** (Novelty): Well-specified from workshop + research; CLI patterns thoroughly established
  - **F=0** (Non-Functional): Standard CLI output, no performance/security concerns
  - **T=1** (Testing): Integration tests with CliRunner across 5 project states, both commands, JSON mode, error paths
- **Confidence**: 0.90
- **Assumptions**:
  - DocsService API is stable and sufficient (list_documents, get_document)
  - The existing dual console pattern (stdout vs stderr) works for agent-parseable output
  - Registry.yaml structure supports adding new documents without schema changes
- **Dependencies**: None external. Builds on existing DocsService, Rich, Typer infrastructure.
- **Risks**: Minimal. Biggest risk is state detection logic having edge cases (e.g., partially configured YAML).
- **Phases**: Single phase (Simple mode) -- implement both commands, tests, and optional bundled doc together

---

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Well-established CliRunner + monkeypatch patterns exist in the codebase; tests are straightforward to write first. Workshop defines expected output formats precisely enough for test-first development.
- **Focus Areas**: State detection across 5 project states, JSON output format parity with MCP, error handling for unknown doc IDs, unguarded access (no config required)
- **Mock Usage**: Avoid mocks -- use real DocsService with real bundled docs, use `tmp_path` + `monkeypatch` for filesystem isolation
- **Key Patterns**: `pytestmark = pytest.mark.slow` on all CLI test files, import `app` inside test methods, use `NO_COLOR=1` for stable Rich output assertions

---

## Acceptance Criteria

### AC-1: `fs2 agents-start-here` works before init
Run `fs2 agents-start-here` in a directory with no `.fs2/` folder. The command exits 0 and outputs: a description of fs2, a project status checklist showing nothing is set up, and a "Next Step" pointing to `fs2 init`.

### AC-2: `fs2 agents-start-here` adapts to project state
Run the command in 5 different states (no init, initialized without providers, initialized with providers, scanned without providers, fully configured). Each state produces different "Next Step" and "Browse Documentation" recommendations. When scanned, the output always points to MCP setup as the next step.

### AC-3: `fs2 docs` lists all documents
Run `fs2 docs` with no arguments. The command exits 0 and outputs a grouped list of all bundled documents (grouped by category: Getting Started, How-To, Reference) with document IDs, titles, and a usage hint.

### AC-4: `fs2 docs <id>` displays document content
Run `fs2 docs agents`. The command exits 0 and outputs the full content of the agents.md document rendered to the terminal.

### AC-5: `fs2 docs <id>` with unknown ID shows error
Run `fs2 docs nonexistent`. The command exits 1 and shows an error message listing available document IDs.

### AC-6: `fs2 docs --json` outputs structured JSON
Run `fs2 docs --json`. The output is valid JSON matching the structure `{"docs": [...], "count": N}` -- the same shape as MCP `docs_list`.

### AC-7: `fs2 docs <id> --json` outputs document as JSON
Run `fs2 docs agents --json`. The output is valid JSON with `id`, `title`, `content`, and `metadata` fields -- the same shape as MCP `docs_get`.

### AC-8: Both commands are unguarded
Neither command has a `require_init` guard. Both work in a directory with no `.fs2/config.yaml`.

### AC-9: `fs2 docs` supports category and tag filtering
Run `fs2 docs --category reference`. Only reference documents appear. Run `fs2 docs --tags config`. Only config-tagged documents appear.

### AC-10: State 5 (fully configured) points to MCP as next step
When the project is fully configured (config + graph + providers), `agents-start-here` outputs "Next Step: Set up MCP for native tool access" with a pointer to `fs2 docs mcp-server-guide`.

---

## Risks & Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| State detection has edge cases (partial YAML, corrupted config) | Medium | Low | Follow doctor's approach: catch exceptions, fall back to "not configured" |
| Rich rendering of markdown produces noisy output for agents | Low | Medium | Agents can use `--json` mode; also use simple formatting (no panels/boxes) |
| DocsService API changes | Very Low | Medium | DocsService is stable since Plan 014; pin to existing interface |
| New bundled doc drifts from actual capabilities | Medium | Low | Follow `just doc-build` pipeline; include "Last Updated" metadata (PL-05) |
| YAML date parsing gotcha in config detection | Medium | Low | Quote date-like values; follow PL-08 pattern |

**Assumptions**:
- The dual console pattern (`Console()` for stdout, `Console(stderr=True)` for errors) is the correct approach for agent-parseable output.
- `NO_COLOR=1` environment variable is sufficient for agents that want plain text without ANSI codes.
- The `fs2 docs` command name does not conflict with any planned future commands.
- Agents will discover `agents-start-here` via `fs2 --help` or by being told by the human.

---

## Open Questions

### OQ-1: Should `agents-start-here` also exist as a bundled doc?
Creating `src/fs2/docs/agents-start-here.md` would let MCP-connected agents revisit the setup guide via `docs_get(id="agents-start-here")`. The CLI command shows the state-adaptive version; the doc would be the static reference. **Leaning yes** per workshop Q1.

### OQ-2: Should `fs2 docs` use Rich Markdown rendering or raw text?
Rich Markdown provides syntax highlighting and structure for human readers. Agents that prefer raw text can use `--json` mode. **Leaning Rich** per workshop Q2.

### OQ-3: Should state detection read the YAML config or just check file existence?
File existence alone can't distinguish "initialized without providers" from "initialized with providers." Reading YAML to detect `llm:` and `embedding:` sections enables better guidance. **Leaning YAML read** per workshop Q3.

### OQ-4: Should the existing `agents.md` get a setup pointer?
Adding a brief "Getting Started" section at the top of `agents.md` pointing to `fs2 agents-start-here` and `fs2 docs configuration-guide` would help agents who find the doc via MCP. **Leaning yes** per workshop Q5.

---

## ADR Seeds (Optional)

- **Decision Drivers**: Commands must work pre-init (unguarded); output must be parseable by LLM agents; CLI is the bootstrap path to MCP (the destination).
- **Candidate Alternatives**:
  - A: Two separate commands (`agents-start-here` + `docs`) -- modular, each has clear purpose
  - B: Single `agents-start-here` command that also embeds docs browsing -- simpler discovery but overloaded
  - C: Enhance `fs2 --help` with state detection -- lowest effort but wrong abstraction (help is for syntax, not onboarding)
- **Stakeholders**: Agent developers, fs2 maintainers, end users who tell their agents "set up fs2"

---

## Workshop Opportunities

All key topics have already been workshopped:

| Topic | Type | Status | Workshop |
|-------|------|--------|----------|
| Agent Onboarding Experience | CLI Flow | Complete | `workshops/agent-onboarding-experience.md` |

The workshop covers: 3-phase agent journey, command signatures, state detection logic (5 states), output format design, worked examples (2 scenarios), and implementation summary. No additional workshops needed.

---

**Spec Complete**: 2026-02-14
**Plan**: 026-agents-start-here
**Next**: Run `/plan-2-clarify` for high-impact questions, or proceed to `/plan-3-architect`
