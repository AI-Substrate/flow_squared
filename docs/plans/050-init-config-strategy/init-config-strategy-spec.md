# Init Config Split: Project gets commented-out defaults, Global gets full template

**Mode**: Simple

📚 This specification incorporates findings from research-dossier.md

## Research Context

Research found that `fs2 init` writes the same 138-line template to both project (`.fs2/config.yaml`) and user (`~/.config/fs2/config.yaml`) configs. Active `smart_content:` and `embedding:` sections confuse users who just want to scan. The scan CLI already handles missing LLM/embedding config gracefully — skipping those stages with "not configured" messages. Project config overrides user config in the merge pipeline, so provider settings in the project config can override a user's personal setup.

## Summary

**What**: Change `fs2 init` so the project config (`.fs2/config.yaml`) has only `scan:` active with everything else commented out, while the global config (`~/.config/fs2/config.yaml`) keeps the full template as-is (including Ollama auto-detection).

**Why**: Users shouldn't have to edit their config just to get a basic scan working. The project config should be minimal and team-friendly (committed to git), while the global config is the user's personal provider setup.

## Goals

- **Project config is scan-only by default**: Only the `scan:` section is active. LLM, smart_content, embedding, and cross-file-rels are present but fully commented out as reference documentation.
- **Global config keeps current behavior**: Full template with active smart_content/embedding, Ollama auto-detection — this is the user's personal setup.
- **Zero-edit first scan**: Running `fs2 init && fs2 scan` works immediately without editing config — scans files, skips smart content and embeddings with clean "not configured" messages.
- **Config as documentation**: The commented-out sections in the project config serve as a reference for what's available, so users can uncomment what they need.

## Non-Goals

- Changing the config merge precedence logic
- Adding interactive provider setup (`fs2 init --provider azure`)
- Changing what `fs2 scan` does when config sections are missing (it already handles this)
- Modifying the global config if it already exists (current skip-if-exists behavior stays)
- Changing Ollama detection logic itself

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| cli | existing | **modify** | init.py: split DEFAULT_CONFIG into project vs global templates |

No new domains. Single file change.

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=0, I=0, D=0, N=0, F=0, T=1
  - Surface Area (0): One file (`init.py`)
  - Integration (0): No external deps
  - Data/State (0): No schema changes
  - Novelty (0): Well-understood from research — exact template identified
  - Non-Functional (0): No perf/security concerns
  - Testing (1): Need to verify both config outputs
- **Confidence**: 0.90
- **Assumptions**: Ollama detection control flow needs restructuring (not just template swap)
- **Dependencies**: None
- **Risks**: None significant

## Acceptance Criteria

1. **AC1 — Project config is scan-only**: `fs2 init` creates `.fs2/config.yaml` with only the `scan:` section uncommented. All LLM, smart_content, embedding, and cross-file-rels sections are present but commented out.

2. **AC2 — Global config keeps full template**: `fs2 init` creates `~/.config/fs2/config.yaml` with the current full template (smart_content and embedding active, Ollama auto-detection).

3. **AC3 — Zero-edit first scan**: After `fs2 init` in a fresh project (no global config), `fs2 scan` completes successfully — discovers files, skips smart content and embeddings with "not configured" messages.

4. **AC4 — Ollama auto-detection targets global only**: When Ollama is detected, the LLM block is auto-uncommented in the GLOBAL config only, not the project config.

5. **AC5 — Force flag still works**: `fs2 init --force` overwrites the project config with the new minimal template.

6. **AC6 — Existing tests pass**: All existing init tests continue to pass.

## Risks & Assumptions

- **Assumption**: Users who have already run `fs2 init` won't be affected — init skips existing configs unless `--force` is used.
- **Assumption**: Commenting out the non-scan sections is a string transformation of the existing template, not a separate maintained template.

## Open Questions

None — user direction is clear: "global gets default as now, local gets it but all commented out."

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| None identified | — | Single file, clear transformation | — |
