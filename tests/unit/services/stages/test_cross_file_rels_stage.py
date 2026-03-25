"""Tests for CrossFileRelsStage — SCIP-based cross-file relationship resolution.

Tests cover: config checks, project resolution, auto-discover,
indexer invocation, incremental resolution, and stage orchestration.
"""

from unittest.mock import patch

import pytest

from fs2.core.models.code_node import CodeNode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_file_node(path: str) -> CodeNode:
    return CodeNode.create_file(path, "python", "module", 0, 100, 1, 10, "# file")


def make_callable_node(
    path: str, name: str, qname: str, parent: str | None = None
) -> CodeNode:
    return CodeNode.create_callable(
        file_path=path,
        language="python",
        ts_kind="function_definition",
        name=name,
        qualified_name=qname,
        start_line=1,
        end_line=5,
        start_column=0,
        end_column=20,
        start_byte=0,
        end_byte=50,
        content=f"def {name}(): pass",
        signature=f"def {name}():",
        parent_node_id=parent,
    )


def make_type_node(
    path: str, name: str, qname: str, parent: str | None = None
) -> CodeNode:
    return CodeNode.create_type(
        file_path=path,
        language="python",
        ts_kind="class_definition",
        name=name,
        qualified_name=qname,
        start_line=1,
        end_line=10,
        start_column=0,
        end_column=20,
        start_byte=0,
        end_byte=100,
        content=f"class {name}: pass",
        signature=f"class {name}:",
        parent_node_id=parent,
    )


# ===========================================================================
# Config checks
# ===========================================================================


@pytest.mark.unit
class TestConfigChecks:
    """Stage skips cleanly for missing/disabled config."""

    def test_skips_when_config_is_none(self):
        from fs2.config.objects import ScanConfig
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.services.stages.cross_file_rels_stage import CrossFileRelsStage

        ctx = PipelineContext(scan_config=ScanConfig())
        stage = CrossFileRelsStage()
        result = stage.process(ctx)
        assert result.metrics["cross_file_rels_skipped"] is True
        assert result.metrics["cross_file_rels_reason"] == "no_config"

    def test_skips_when_disabled(self):
        from fs2.config.objects import CrossFileRelsConfig, ScanConfig
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.services.stages.cross_file_rels_stage import CrossFileRelsStage

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.cross_file_rels_config = CrossFileRelsConfig(enabled=False)
        stage = CrossFileRelsStage()
        result = stage.process(ctx)
        assert result.metrics["cross_file_rels_skipped"] is True
        assert result.metrics["cross_file_rels_reason"] == "disabled"

    def test_skips_when_no_projects(self):
        from fs2.config.objects import CrossFileRelsConfig, ProjectsConfig, ScanConfig
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.services.stages.cross_file_rels_stage import CrossFileRelsStage

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.cross_file_rels_config = CrossFileRelsConfig(enabled=True)
        ctx.projects_config = ProjectsConfig(entries=[], auto_discover=False)
        ctx.nodes = [make_callable_node("src/a.py", "func", "func")]
        stage = CrossFileRelsStage()
        result = stage.process(ctx)
        assert result.metrics["cross_file_rels_skipped"] is True
        assert result.metrics["cross_file_rels_reason"] == "no_projects"


# ===========================================================================
# Protocol compliance
# ===========================================================================


@pytest.mark.unit
class TestCrossFileRelsStageProtocol:
    """CrossFileRelsStage implements PipelineStage protocol."""

    def test_implements_pipeline_stage(self):
        from fs2.core.services.pipeline_stage import PipelineStage
        from fs2.core.services.stages.cross_file_rels_stage import CrossFileRelsStage

        stage = CrossFileRelsStage()
        assert isinstance(stage, PipelineStage)

    def test_name_is_cross_file_rels(self):
        from fs2.core.services.stages.cross_file_rels_stage import CrossFileRelsStage

        assert CrossFileRelsStage().name == "cross_file_rels"


# ===========================================================================
# SCIP indexer invocation
# ===========================================================================


@pytest.mark.unit
class TestRunScipIndexer:
    """Tests for run_scip_indexer() subprocess invocation."""

    def test_returns_false_for_unknown_language(self):
        from fs2.core.services.stages.cross_file_rels_stage import run_scip_indexer

        assert run_scip_indexer("cobol", "/tmp/proj", "/tmp/out.scip") is False

    def test_returns_false_when_binary_missing(self, monkeypatch):
        from fs2.core.services.stages.cross_file_rels_stage import run_scip_indexer

        monkeypatch.setattr("shutil.which", lambda cmd: None)
        assert run_scip_indexer("python", "/tmp/proj", "/tmp/out.scip") is False

    def test_returns_false_for_dotnet_without_build(self, tmp_path, monkeypatch):
        from fs2.core.services.stages.cross_file_rels_stage import run_scip_indexer

        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/scip-dotnet")
        project = tmp_path / "myapp"
        project.mkdir()
        # No obj/ directory = not built
        assert run_scip_indexer("dotnet", str(project), str(tmp_path / "out.scip")) is False

    def test_returns_true_on_success(self, tmp_path, monkeypatch):
        from fs2.core.services.stages.cross_file_rels_stage import run_scip_indexer

        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/scip-python")
        output = tmp_path / "cache" / "index.scip"

        def fake_run(cmd, **kwargs):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fake scip data")

            class FakeResult:
                returncode = 0
                stderr = ""
            return FakeResult()

        monkeypatch.setattr("subprocess.run", fake_run)
        assert run_scip_indexer("python", str(tmp_path), str(output)) is True
        assert output.exists()


# ===========================================================================
# Cache directory
# ===========================================================================


@pytest.mark.unit
class TestCacheDirectory:
    """Tests for cache slug generation and gitignore."""

    def test_project_slug_root(self):
        from fs2.core.services.stages.cross_file_rels_stage import _project_slug

        slug = _project_slug("/repo", "python", "/repo")
        assert slug == "root_python"

    def test_project_slug_subdir(self):
        from fs2.core.services.stages.cross_file_rels_stage import _project_slug

        slug = _project_slug("/repo/frontend", "typescript", "/repo")
        assert slug == "frontend_typescript"

    def test_ensure_cache_gitignore(self, tmp_path):
        from fs2.core.services.stages.cross_file_rels_stage import (
            _ensure_cache_gitignore,
        )

        cache = tmp_path / ".fs2" / "scip"
        _ensure_cache_gitignore(cache)
        gi = cache / ".gitignore"
        assert gi.exists()
        assert "*" in gi.read_text()


# ===========================================================================
# Auto-discover
# ===========================================================================


@pytest.mark.unit
class TestAutoDiscover:
    """Tests for auto-discover fallback."""

    def test_auto_discovers_when_entries_empty(self, tmp_path, monkeypatch):
        from fs2.config.objects import CrossFileRelsConfig, ProjectsConfig, ScanConfig
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.services.stages.cross_file_rels_stage import CrossFileRelsStage

        (tmp_path / "pyproject.toml").write_text("[build-system]")
        monkeypatch.chdir(tmp_path)

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.cross_file_rels_config = CrossFileRelsConfig(enabled=True)
        ctx.projects_config = ProjectsConfig(entries=[], auto_discover=True)
        ctx.scan_root = tmp_path
        ctx.nodes = [make_callable_node("src/a.py", "func", "func")]

        # Mock the indexer (not installed in test env)
        with patch("fs2.core.services.stages.cross_file_rels_stage.run_scip_indexer", return_value=False):
            stage = CrossFileRelsStage()
            result = stage.process(ctx)

        # Stage ran (not skipped) even though indexer failed
        assert result.metrics.get("cross_file_rels_skipped") is False

    def test_skips_when_auto_discover_disabled_and_empty(self):
        from fs2.config.objects import CrossFileRelsConfig, ProjectsConfig, ScanConfig
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.services.stages.cross_file_rels_stage import CrossFileRelsStage

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.cross_file_rels_config = CrossFileRelsConfig(enabled=True)
        ctx.projects_config = ProjectsConfig(entries=[], auto_discover=False)
        ctx.nodes = [make_callable_node("src/a.py", "func", "func")]

        stage = CrossFileRelsStage()
        result = stage.process(ctx)
        assert result.metrics["cross_file_rels_skipped"] is True
        assert result.metrics["cross_file_rels_reason"] == "no_projects"


# ===========================================================================
# Incremental resolution (preserved from prior implementation)
# ===========================================================================


class TestGetChangedFilePaths:
    """Tests for get_changed_file_paths()."""

    def _make_file_node(self, path: str, content_hash: str) -> CodeNode:
        node = CodeNode.create_file(path, "python", "module", 0, 100, 1, 10, "# file")
        object.__setattr__(node, "content_hash", content_hash)
        return node

    def test_all_changed_when_no_prior(self):
        from fs2.core.services.stages.cross_file_rels_stage import (
            get_changed_file_paths,
        )

        current = [self._make_file_node("src/a.py", "hash_a")]
        assert get_changed_file_paths(current, prior_nodes=None) is None

    def test_unchanged_files_excluded(self):
        from fs2.core.services.stages.cross_file_rels_stage import (
            get_changed_file_paths,
        )

        current = [
            self._make_file_node("src/a.py", "hash_a"),
            self._make_file_node("src/b.py", "hash_b"),
        ]
        prior = {
            "file:src/a.py": self._make_file_node("src/a.py", "hash_a"),
            "file:src/b.py": self._make_file_node("src/b.py", "old_hash"),
        }
        result = get_changed_file_paths(current, prior)
        assert result == {"src/b.py"}

    def test_new_files_included(self):
        from fs2.core.services.stages.cross_file_rels_stage import (
            get_changed_file_paths,
        )

        current = [
            self._make_file_node("src/a.py", "hash_a"),
            self._make_file_node("src/new.py", "hash_new"),
        ]
        prior = {"file:src/a.py": self._make_file_node("src/a.py", "hash_a")}
        result = get_changed_file_paths(current, prior)
        assert result == {"src/new.py"}


class TestFilterNodesToChanged:
    """Tests for filtering nodes to only changed files."""

    def test_filters_to_changed_files(self):
        from fs2.core.services.stages.cross_file_rels_stage import (
            filter_nodes_to_changed,
        )

        nodes = [
            make_callable_node("src/a.py", "foo", "A.foo"),
            make_callable_node("src/b.py", "bar", "B.bar"),
        ]
        result = filter_nodes_to_changed(nodes, {"src/b.py"})
        assert len(result) == 1
        assert result[0].node_id == "callable:src/b.py:B.bar"

    def test_returns_all_when_none(self):
        from fs2.core.services.stages.cross_file_rels_stage import (
            filter_nodes_to_changed,
        )

        nodes = [make_callable_node("src/a.py", "foo", "A.foo")]
        assert len(filter_nodes_to_changed(nodes, None)) == 1


class TestReusePriorEdges:
    """Tests for reusing edges from prior scan."""

    def test_reuses_edges_for_unchanged_files(self):
        from fs2.core.services.stages.cross_file_rels_stage import reuse_prior_edges

        prior_edges = [
            ("callable:src/a.py:A.foo", "callable:src/b.py:B.bar", {"edge_type": "references"}),
            ("callable:src/c.py:C.baz", "callable:src/a.py:A.foo", {"edge_type": "references"}),
        ]
        changed_files = {"src/b.py"}
        current_ids = {"callable:src/a.py:A.foo", "callable:src/b.py:B.bar", "callable:src/c.py:C.baz"}

        result = reuse_prior_edges(prior_edges, changed_files, current_ids)
        assert len(result) == 1
        assert result[0][0] == "callable:src/c.py:C.baz"

    def test_returns_empty_when_no_prior(self):
        from fs2.core.services.stages.cross_file_rels_stage import reuse_prior_edges

        assert reuse_prior_edges(None, set(), set()) == []
