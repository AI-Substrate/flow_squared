"""Tests for CrossFileRelsStage — cross-file relationship resolution.

Purpose: Verify project detection, incremental resolution, and orchestration.

Uses fakes over mocks per doctrine.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
# T004: Project detection
# ===========================================================================


@pytest.mark.unit
class TestProjectDetection:
    """Tests for detect_project_roots() — now in project_discovery module."""

    def test_detects_python_project(self, tmp_path):
        """Proves pyproject.toml triggers python project detection."""
        from fs2.core.services.project_discovery import detect_project_roots

        (tmp_path / "pyproject.toml").write_text("[build-system]")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "python"

    def test_detects_typescript_project(self, tmp_path):
        """Proves tsconfig.json triggers typescript detection."""
        from fs2.core.services.project_discovery import detect_project_roots

        (tmp_path / "tsconfig.json").write_text("{}")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "typescript"

    def test_multi_language_produces_separate_entries(self, tmp_path):
        """Multi-language root produces one entry per language."""
        from fs2.core.services.project_discovery import detect_project_roots

        (tmp_path / "pyproject.toml").write_text("[build-system]")
        (tmp_path / "package.json").write_text("{}")
        roots = detect_project_roots(str(tmp_path))
        languages = {r.language for r in roots}
        assert "python" in languages
        assert "javascript" in languages
        assert len(roots) == 2  # separate entries, not combined

    def test_nested_projects_not_deduped(self, tmp_path):
        """Nested projects are preserved (no child dedup)."""
        from fs2.core.services.project_discovery import detect_project_roots

        (tmp_path / "pyproject.toml").write_text("[build-system]")
        sub = tmp_path / "packages" / "sub"
        sub.mkdir(parents=True)
        (sub / "package.json").write_text("{}")
        roots = detect_project_roots(str(tmp_path))
        # Both parent and child kept (no dedup)
        assert len(roots) == 2

    def test_returns_empty_for_no_markers(self, tmp_path):
        """Proves empty list when no project markers found."""
        from fs2.core.services.project_discovery import detect_project_roots

        (tmp_path / "readme.txt").write_text("hello")
        roots = detect_project_roots(str(tmp_path))
        assert roots == []

    def test_detects_csharp_project(self, tmp_path):
        """Proves .csproj triggers dotnet detection (new marker)."""
        from fs2.core.services.project_discovery import detect_project_roots

        (tmp_path / "MyApp.csproj").write_text("<Project/>")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "dotnet"

    def test_detects_ruby_project(self, tmp_path):
        """Proves Gemfile triggers ruby detection (new marker)."""
        from fs2.core.services.project_discovery import detect_project_roots

        (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "ruby"

    def test_skips_obj_directory(self, tmp_path):
        """Proves obj/ build output is skipped."""
        from fs2.core.services.project_discovery import detect_project_roots

        obj_dir = tmp_path / "obj" / "Debug"
        obj_dir.mkdir(parents=True)
        (obj_dir / "MyApp.csproj").write_text("<Project/>")
        roots = detect_project_roots(str(tmp_path))
        assert roots == []

    def test_backward_compat_import_from_stage(self, tmp_path):
        """Proves detect_project_roots is importable from stage module."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            detect_project_roots,
        )

        (tmp_path / "pyproject.toml").write_text("[build-system]")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) >= 1


# ===========================================================================
# T009: Orchestration (CrossFileRelsStage protocol compliance)
# ===========================================================================


@pytest.mark.unit
class TestCrossFileRelsStageProtocol:
    """Tests for CrossFileRelsStage protocol compliance (T009)."""

    def test_implements_pipeline_stage(self):
        """Proves CrossFileRelsStage implements PipelineStage protocol."""
        from fs2.core.services.pipeline_stage import PipelineStage
        from fs2.core.services.stages.cross_file_rels_stage import (
            CrossFileRelsStage,
        )

        stage = CrossFileRelsStage()
        assert isinstance(stage, PipelineStage)

    def test_name_is_cross_file_rels(self):
        """Proves stage name is 'cross_file_rels'."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            CrossFileRelsStage,
        )

        assert CrossFileRelsStage().name == "cross_file_rels"


class TestGetChangedFilePaths:
    """Tests for incremental resolution — skip unchanged files (T008)."""

    def _make_file_node(self, path: str, content_hash: str) -> CodeNode:
        node = CodeNode.create_file(path, "python", "module", 0, 100, 1, 10, "# file")
        # Override content_hash for testing
        object.__setattr__(node, "content_hash", content_hash)
        return node

    def test_all_changed_when_no_prior(self):
        """First scan (no prior) — all files are 'changed'."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            get_changed_file_paths,
        )

        current = [
            self._make_file_node("src/a.py", "hash_a"),
            self._make_file_node("src/b.py", "hash_b"),
        ]
        result = get_changed_file_paths(current, prior_nodes=None)
        assert result is None  # None means "all files changed"

    def test_unchanged_files_excluded(self):
        """Files with matching content_hash are excluded."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            get_changed_file_paths,
        )

        current = [
            self._make_file_node("src/a.py", "hash_a"),
            self._make_file_node("src/b.py", "hash_b"),
        ]
        prior = {
            "file:src/a.py": self._make_file_node("src/a.py", "hash_a"),  # same
            "file:src/b.py": self._make_file_node("src/b.py", "old_hash"),  # changed
        }
        result = get_changed_file_paths(current, prior)
        assert result == {"src/b.py"}

    def test_new_files_included(self):
        """New files (not in prior) are included."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            get_changed_file_paths,
        )

        current = [
            self._make_file_node("src/a.py", "hash_a"),
            self._make_file_node("src/new.py", "hash_new"),
        ]
        prior = {
            "file:src/a.py": self._make_file_node("src/a.py", "hash_a"),
        }
        result = get_changed_file_paths(current, prior)
        assert result == {"src/new.py"}

    def test_all_unchanged_returns_empty(self):
        """When all files unchanged, returns empty set."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            get_changed_file_paths,
        )

        current = [
            self._make_file_node("src/a.py", "hash_a"),
        ]
        prior = {
            "file:src/a.py": self._make_file_node("src/a.py", "hash_a"),
        }
        result = get_changed_file_paths(current, prior)
        assert result == set()


class TestFilterNodesToChanged:
    """Tests for filtering nodes to only changed files (T008)."""

    def test_filters_nodes_to_changed_files(self):
        """Only nodes from changed files pass through."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            filter_nodes_to_changed,
        )

        nodes = [
            make_callable_node("src/a.py", "foo", "A.foo"),
            make_callable_node("src/b.py", "bar", "B.bar"),
            make_callable_node("src/a.py", "baz", "A.baz"),
        ]
        changed_files = {"src/b.py"}

        result = filter_nodes_to_changed(nodes, changed_files)
        assert len(result) == 1
        assert result[0].node_id == "callable:src/b.py:B.bar"

    def test_returns_all_when_changed_is_none(self):
        """None means first scan — return all nodes."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            filter_nodes_to_changed,
        )

        nodes = [
            make_callable_node("src/a.py", "foo", "A.foo"),
            make_callable_node("src/b.py", "bar", "B.bar"),
        ]
        result = filter_nodes_to_changed(nodes, None)
        assert len(result) == 2


class TestReusePriorEdges:
    """Tests for reusing edges from prior scan for unchanged files (T008)."""

    def test_reuses_edges_for_unchanged_files(self):
        """Edges from unchanged files are carried forward."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            reuse_prior_edges,
        )

        prior_edges = [
            ("callable:src/a.py:A.foo", "callable:src/b.py:B.bar", {"edge_type": "references"}),
            ("callable:src/c.py:C.baz", "callable:src/a.py:A.foo", {"edge_type": "references"}),
        ]
        changed_files = {"src/b.py"}
        current_node_ids = {
            "callable:src/a.py:A.foo",
            "callable:src/b.py:B.bar",
            "callable:src/c.py:C.baz",
        }

        result = reuse_prior_edges(prior_edges, changed_files, current_node_ids)
        # Only the edge from c.py→a.py should be reused (both files unchanged)
        # The edge a.py→b.py should NOT be reused (b.py changed)
        assert len(result) == 1
        assert result[0][0] == "callable:src/c.py:C.baz"

    def test_skips_edges_with_missing_nodes(self):
        """Edges referencing deleted nodes are dropped."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            reuse_prior_edges,
        )

        prior_edges = [
            ("callable:src/a.py:A.foo", "callable:src/deleted.py:X", {"edge_type": "references"}),
        ]
        changed_files: set[str] = set()
        current_node_ids = {"callable:src/a.py:A.foo"}

        result = reuse_prior_edges(prior_edges, changed_files, current_node_ids)
        assert len(result) == 0  # deleted node no longer exists

    def test_returns_empty_when_no_prior(self):
        """None prior edges → empty list."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            reuse_prior_edges,
        )

        result = reuse_prior_edges(None, set(), set())
        assert result == []
