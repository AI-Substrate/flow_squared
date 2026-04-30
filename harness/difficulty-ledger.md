# Difficulty Ledger

Tracks friction reported by minih agents and development sessions.
Maintained per the minih philosophy: every unresolved difficulty costs the next agent hours.

## Active Difficulties

| ID | Category | Description | Workaround | Severity | Source | Status |
|----|----------|-------------|------------|----------|--------|--------|
| MH-001 | tooling | Running `uv run fs2 ...` from a scratch validation directory produces misleading results — not bound to the target repo's worktree | Rerun validation from repo root with `uv run python` and `CliRunner` | degrading | code-review agent (2026-04-15) | open |
| MH-002 | delegation | Background integration subagent reported markdown sections missing even though local reproduction showed scan/tree/search working correctly — subagent result was untrustworthy | Treated subagent output as advisory only; verified behavior manually | degrading | code-review agent (2026-04-15) | open |
| MH-003 | knowledge | minih anchored review on the most recent merge commit (PR #13) instead of the active branch's diff, causing it to review plans 049-051 when asked to review plan 052. The relevant finding (F002) still landed by lucky overlap with `init.py`, but the rest of the review was off-target. | Cross-reference `git log --oneline` with `docs/plans/` directory and explicitly tell the agent which plan + branch to review | degrading | code-review agent (2026-04-30, plan 052) | open |
| MH-004 | test | The default targeted `pytest` invocation silently skipped CLI coverage because `pytest.ini` excludes `slow` tests by default. Review missed CLI-side issues until re-run with `-m slow`. | Read `pytest.ini`, then rerun the relevant CLI/integration suites with `-m slow` (or `-m ""` to disable marker filter entirely) | degrading | code-review agent (2026-04-30, plan 052) | open |

## Resolved Difficulties

*(none yet)*

## Magic Wands

| Date | Agent | Target | Wand |
|------|-------|--------|------|
| 2026-04-15 | code-review | minih | Give minih a built-in 'run this repository's current worktree in a scratch cwd' wrapper so live CLI validation against temp projects never accidentally resolves to an installed tool or a different environment |
| 2026-04-30 | code-review | minih | Have minih inject the exact phase/plan path or commit range into code-review runs so merge commits do not require manual scope reconstruction from git history and docs/plans directories |
