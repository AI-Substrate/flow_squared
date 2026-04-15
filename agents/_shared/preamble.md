# Agent Preamble

**FIRST**: Run `cd {{REPO_ROOT}}` — your session starts in a run folder, not the project root.

## Project Context

**Flowspace2 (fs2)** — Python Clean Architecture project. Code search and indexing tool using tree-sitter.

- **Package manager**: `uv`
- **Test runner**: `uv run pytest`
- **Architecture**: Clean Architecture — Services compose Adapters/Repos through interface injection
- **Convention**: ABC interfaces, fakes over mocks, actionable errors

## Key Paths

- Source: `src/fs2/`
- Tests: `tests/`
- Plans: `docs/plans/`
- Config: `.fs2/`

## Known Difficulties

| ID | Category | Description | Mitigation | Status |
|----|----------|-------------|------------|--------|
| *(none yet — first run!)* | | | | |

## Feedback — The Self-Improving Loop

You are not just running a task. You are helping build a better system.
Every time you run, you have two responsibilities:

1. Complete your task well
2. Feed back honestly on the experience of doing it

Your output MUST include a `retrospective` with a required `magicWand` field.

**What makes good feedback:**

Bad: "Everything was fine."
Good: "The plan had absolute file paths which helped me navigate immediately, but
the test fixtures were in a different directory than I expected from the plan manifest."

**The retrospective fields:**

- **workedWell**: What about the tools, workflow, or environment was smooth?
- **confusing**: What required trial-and-error? What information was hard to find?
- **magicWand** (REQUIRED): If you could change ONE thing to make your job easier, what would it be? Be concrete.
- **difficulties** (REQUIRED): Structured friction reports with id, category, description, workaround, severity. These feed into the project's difficulty ledger.
