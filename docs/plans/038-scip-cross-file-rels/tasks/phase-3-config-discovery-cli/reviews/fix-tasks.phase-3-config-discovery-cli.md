# Fix Tasks: Phase 3: Config & Discovery CLI

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Restore the stage / discovery contract
- **Severity**: HIGH
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/project_discovery.py`
- **Issue**: `detect_project_roots()` now returns `DiscoveredProject(path, language, marker_file)`, but `CrossFileRelsStage.process()` still deduplicates by path and later dereferences `root.languages` as if it were working with the old `ProjectRoot` shape.
- **Fix**: Choose one contract and make both sides obey it. Either keep the legacy `ProjectRoot(path, languages)` contract alive until Phase 4, or adapt the stage to process one discovered `(path, language)` project at a time and stop dereferencing `.languages`.
- **Patch hint**:
  ```diff
  -        all_project_roots: list[ProjectRoot] = []
  -        seen_paths: set[str] = set()
  -        for root in search_roots:
  -            for pr in detect_project_roots(root):
  -                if pr.path not in seen_paths:
  -                    all_project_roots.append(pr)
  -                    seen_paths.add(pr.path)
  +        all_project_roots = []
  +        for root in search_roots:
  +            all_project_roots.extend(detect_project_roots(root))
  ...
  -        for root in all_project_roots:
  -            ensure_serena_project(root.path, languages=root.languages)
  +        for project in all_project_roots:
  +            ensure_serena_project(project.path, languages=[project.language])
  ```

### FT-002: Resolve the removed Serena config field dependency
- **Severity**: HIGH
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/config/objects.py`
- **Issue**: Phase 3 removed `parallel_instances` and `serena_base_port` from `CrossFileRelsConfig`, but the enabled stage path still reads both fields.
- **Fix**: Either finish the stage migration so it no longer depends on Serena-era config knobs, or restore a temporary compatibility contract until that migration lands. Do not leave the enabled path half-migrated.
- **Patch hint**:
  ```diff
  -        n_instances = min(config.parallel_instances, len(nodes_to_resolve))
  -        if n_instances < 1:
  -            n_instances = 1
  -        base_port = config.serena_base_port
  +        # Use one coherent contract here: either real Phase-4 SCIP config,
  +        # or an explicit temporary compatibility shim for the legacy Serena path.
  +        n_instances = min(getattr(config, "parallel_instances", 20), len(nodes_to_resolve))
  +        if n_instances < 1:
  +            n_instances = 1
  +        base_port = getattr(config, "serena_base_port", 9123)
  ```

### FT-003: Add enabled-path regression coverage and real acceptance evidence
- **Severity**: HIGH
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/integration/test_cross_file_acceptance.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py`
- **Issue**: The changed tests do not exercise the enabled cross-file-rels path, and the current “real SCIP” acceptance test still routes through Serena-era stage logic.
- **Fix**: Add a regression test that runs `CrossFileRelsStage.process()` with enabled config and discovered projects, using a controlled pool/client or monkeypatched stage dependencies. Then align the acceptance test with the runtime path the phase is supposed to validate.
- **Patch hint**:
  ```diff
  +def test_enabled_path_accepts_discovered_project_shape(monkeypatch, tmp_path):
  +    monkeypatch.setattr(stage_mod, "is_serena_available", lambda: True)
  +    monkeypatch.setattr(stage_mod, "ensure_serena_project", lambda *a, **k: False)
  +    ...
  +    ctx.cross_file_rels_config = CrossFileRelsConfig(enabled=True)
  +    result = CrossFileRelsStage(pool_factory=FakePool).process(ctx)
  +    assert result.metrics["cross_file_rels_skipped"] is False
  ```

## Medium / Low Fixes

### FT-004: Complete AC6 / AC7 CLI evidence
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_projects_cli.py`
- **Issue**: Tests do not assert marker / project-file display, indexer status / install hints, comment preservation, or non-default `project_file` persistence.
- **Fix**: Add explicit CLI tests for missing / installed indexers, non-default marker detection, and comment-preserving `ruamel.yaml` writes.
- **Patch hint**:
  ```diff
  +def test_discover_projects_shows_missing_indexer_hint(...):
  +    monkeypatch.setattr("shutil.which", lambda _: None)
  +    result = runner.invoke(app, ["discover-projects", "--json"])
  +    data = json.loads(result.stdout)
  +    assert data["projects"][0]["indexer_installed"] is False
  +    assert data["projects"][0]["install_hint"]
  +
  +def test_add_project_preserves_comments_and_project_file(...):
  +    config_path.write_text("# keep me\nprojects:\n  entries: []\n")
  +    ...
  +    assert "# keep me" in config_path.read_text()
  +    assert "project_file:" in config_path.read_text()
  ```

### FT-005: Move config mutation out of the CLI layer
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/projects.py`
- **Issue**: `add_project()` currently owns YAML parsing, deduplication, and config mutation directly in the presentation layer.
- **Fix**: Extract project selection / config-write logic into a dedicated service or config helper, and keep the CLI limited to argument parsing, invoking the service, and rendering results / errors.
- **Patch hint**:
  ```diff
  -def add_project(...):
  -    ...
  -    yaml = YAML()
  -    ...
  -    existing_entries.append(entry)
  -    ...
  +def add_project(...):
  +    service = ProjectConfigService(root)
  +    result = service.add_discovered_projects(selected)
  +    ...  # render result
  ```

### FT-006: Keep external-tool metadata out of core/services
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/project_discovery.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/projects.py`
- **Issue**: `project_discovery.py` exports SCIP binary names and install commands, which are CLI / infrastructure concerns.
- **Fix**: Move binary / install hint maps to the CLI layer or an infrastructure-facing metadata module, and let the service layer focus only on project detection.
- **Patch hint**:
  ```diff
  -from fs2.core.services.project_discovery import (
  -    INDEXER_BINARIES,
  -    INDEXER_INSTALL,
  -    DiscoveredProject,
  -    detect_project_roots,
  -)
  +from fs2.core.services.project_discovery import DiscoveredProject, detect_project_roots
  +from fs2.cli.project_indexer_metadata import INDEXER_BINARIES, INDEXER_INSTALL
  ```

## Re-Review Checklist

- [ ] All critical / high fixes applied
- [ ] Re-run `/plan-7-v2-code-review --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md --phase 'Phase 3: Config & Discovery CLI'` and achieve zero HIGH / CRITICAL
