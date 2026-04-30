# Flight Plan: Config UX Cleanup — GraphConfig Optional + Batch Size Comments

**Status**: Specifying
**Plan**: `052-graph-config-optional`
**Branch**: `052-graph-config-optional`
**Mode**: Simple
**Issues**: [#14](https://github.com/AI-Substrate/flow_squared/issues/14), [#15](https://github.com/AI-Substrate/flow_squared/issues/15)

---

## What & Why

Two recently filed issues report related config-UX footguns. **Issue #14**: MCP `tree`/`search`/`get_node` raise an error when the optional `graph:` config section is absent, even though every field on `GraphConfig` has a default. **Issue #15**: docs and validator messages mislead Azure users about safe `batch_size` values, causing 400 errors on real configs. Fix: 3 one-line code swaps + comment/doc edits.

## Scope

| Aspect | Details |
|---|---|
| **In** | Make `GraphConfig` optional in 3 services; add `graph:` block to `fs2 init` template; new "Graph Configuration" docs section; 2 troubleshooting rows; clearer `batch_size` comments in 3 doc copies; updated validator error text |
| **Out** | Token-aware batching (logged as follow-up); refactoring `ConfigurationService.require()` globally; `--graph-file` flag changes; renaming fields |

## Complexity

CS-1 (trivial). All changes local; no external deps; no migrations.

## Phases (initial sketch)

1. **Code change** — 3 services + init template
2. **Doc updates** — Graph Configuration section, troubleshooting rows, batch_size comments
3. **Regression tests** — one per fixed service + init template sweep

## Acceptance Highlights

- Fresh `fs2 init` → MCP `tree`/`search`/`get_node` work without manual config edits
- Existing configs with `graph:` block keep working unchanged
- `batch_size` doc comment names the 300k-token-per-request Azure limit
- All existing tests pass; new tests cover the three previously-broken services

## Links

- Spec: `graph-config-optional-spec.md`
- Research: `research-dossier.md`
- Branch: `052-graph-config-optional`
