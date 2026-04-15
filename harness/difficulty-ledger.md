# Difficulty Ledger

Tracks friction reported by minih agents and development sessions.
Maintained per the minih philosophy: every unresolved difficulty costs the next agent hours.

## Active Difficulties

| ID | Category | Description | Workaround | Severity | Source | Status |
|----|----------|-------------|------------|----------|--------|--------|
| MH-001 | tooling | Running `uv run fs2 ...` from a scratch validation directory produces misleading results — not bound to the target repo's worktree | Rerun validation from repo root with `uv run python` and `CliRunner` | degrading | code-review agent (2026-04-15) | open |
| MH-002 | delegation | Background integration subagent reported markdown sections missing even though local reproduction showed scan/tree/search working correctly — subagent result was untrustworthy | Treated subagent output as advisory only; verified behavior manually | degrading | code-review agent (2026-04-15) | open |

## Resolved Difficulties

*(none yet)*

## Magic Wands

| Date | Agent | Target | Wand |
|------|-------|--------|------|
| 2026-04-15 | code-review | minih | Give minih a built-in 'run this repository's current worktree in a scratch cwd' wrapper so live CLI validation against temp projects never accidentally resolves to an installed tool or a different environment |
