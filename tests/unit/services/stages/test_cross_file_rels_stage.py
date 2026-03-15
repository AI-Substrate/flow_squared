"""Tests for CrossFileRelsStage — cross-file relationship resolution.

Phase 2 Tasks: T003-T010
Purpose: Verify Serena detection, project detection, instance pool,
         node sharding, reference resolution, and orchestration.

Uses fakes over mocks per doctrine (FakeSubprocessRunner, FakeSerenaClient).
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from fs2.core.models.code_node import CodeNode


# ---------------------------------------------------------------------------
# Fakes (per doctrine: fakes over mocks)
# ---------------------------------------------------------------------------


class FakeSubprocessRunner:
    """Fake subprocess runner for testing."""

    def __init__(self):
        self.commands_run: list[list[str]] = []
        self.processes_started: list[list[str]] = []
        self.fail_run: bool = False

    def run(self, cmd: list[str], **kwargs: Any):
        self.commands_run.append(cmd)
        if self.fail_run:
            import subprocess

            raise subprocess.CalledProcessError(1, cmd)

        @dataclass
        class FakeResult:
            returncode: int = 0
            stdout: str = ""
            stderr: str = ""

        return FakeResult()

    def popen(self, cmd: list[str], **kwargs: Any):
        self.processes_started.append(cmd)

        @dataclass
        class FakeProcess:
            pid: int = 99999 + len(self.processes_started)

            def poll(self):
                return None

            def wait(self, timeout=None):
                pass

            def kill(self):
                pass

        return FakeProcess()


class FakeSerenaClient:
    """Fake Serena MCP client for testing."""

    def __init__(self):
        self.responses: dict[str, list[dict[str, Any]]] = {}
        self.calls: list[dict[str, str]] = []
        self.fail_for: set[str] = set()

    def set_response(self, name_path: str, refs: list[dict[str, Any]]):
        self.responses[name_path] = refs

    async def find_referencing_symbols(
        self, name_path: str, relative_path: str, port: int
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {"name_path": name_path, "relative_path": relative_path, "port": str(port)}
        )
        if name_path in self.fail_for:
            raise TimeoutError(f"Simulated timeout for {name_path}")
        return self.responses.get(name_path, [])


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
# T003: Serena availability detection
# ===========================================================================


@pytest.mark.unit
class TestSerenaAvailability:
    """Tests for is_serena_available() (T003)."""

    def test_returns_bool(self):
        """Proves is_serena_available returns a boolean."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            is_serena_available,
        )

        result = is_serena_available()
        assert isinstance(result, bool)

    def test_detects_serena_when_on_path(self, monkeypatch):
        """Proves detection works when serena-mcp-server is on PATH."""
        from fs2.core.services.stages import cross_file_rels_stage

        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/serena-mcp-server")
        assert cross_file_rels_stage.is_serena_available() is True

    def test_returns_false_when_not_on_path(self, monkeypatch):
        """Proves False when serena-mcp-server not on PATH."""
        from fs2.core.services.stages import cross_file_rels_stage

        monkeypatch.setattr("shutil.which", lambda cmd: None)
        assert cross_file_rels_stage.is_serena_available() is False


# ===========================================================================
# T004: Project detection
# ===========================================================================


@pytest.mark.unit
class TestProjectDetection:
    """Tests for detect_project_roots() (T004)."""

    def test_detects_python_project(self, tmp_path):
        """Proves pyproject.toml triggers python project detection."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            detect_project_roots,
        )

        (tmp_path / "pyproject.toml").write_text("[build-system]")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert "python" in roots[0].languages

    def test_detects_typescript_project(self, tmp_path):
        """Proves tsconfig.json triggers typescript detection."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            detect_project_roots,
        )

        (tmp_path / "tsconfig.json").write_text("{}")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert "typescript" in roots[0].languages

    def test_detects_multi_language_project(self, tmp_path):
        """Proves a project with both pyproject.toml and package.json gets both languages."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            detect_project_roots,
        )

        (tmp_path / "pyproject.toml").write_text("[build-system]")
        (tmp_path / "package.json").write_text("{}")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert "python" in roots[0].languages
        assert "javascript" in roots[0].languages

    def test_detects_nested_projects(self, tmp_path):
        """Proves child projects nested under a parent root are deduplicated."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            detect_project_roots,
        )

        (tmp_path / "pyproject.toml").write_text("[build-system]")
        sub = tmp_path / "packages" / "sub"
        sub.mkdir(parents=True)
        (sub / "package.json").write_text("{}")
        roots = detect_project_roots(str(tmp_path))
        # Parent-child dedup: only the shallowest root is kept
        assert len(roots) == 1
        assert roots[0].path == str(tmp_path.resolve())

    def test_returns_empty_for_no_markers(self, tmp_path):
        """Proves empty list when no project markers found."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            detect_project_roots,
        )

        (tmp_path / "readme.txt").write_text("hello")
        roots = detect_project_roots(str(tmp_path))
        assert roots == []


# ===========================================================================
# T005: Serena project auto-creation
# ===========================================================================


@pytest.mark.unit
class TestSerenaProjectCreation:
    """Tests for ensure_serena_project() (T005)."""

    def test_creates_project_when_not_exists(self, tmp_path):
        """Proves creates .serena/project.yml via subprocess."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            ensure_serena_project,
        )

        runner = FakeSubprocessRunner()
        result = ensure_serena_project(str(tmp_path), runner=runner)
        assert result is True
        assert len(runner.commands_run) == 1
        assert "serena" in runner.commands_run[0]
        assert "project" in runner.commands_run[0]
        assert "create" in runner.commands_run[0]

    def test_skips_when_already_exists(self, tmp_path):
        """Proves skips creation when .serena/project.yml exists."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            ensure_serena_project,
        )

        serena_dir = tmp_path / ".serena"
        serena_dir.mkdir()
        (serena_dir / "project.yml").write_text("name: test")

        runner = FakeSubprocessRunner()
        result = ensure_serena_project(str(tmp_path), runner=runner)
        assert result is False
        assert len(runner.commands_run) == 0

    def test_handles_creation_failure(self, tmp_path):
        """Proves handles subprocess failure gracefully."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            ensure_serena_project,
        )

        runner = FakeSubprocessRunner()
        runner.fail_run = True
        result = ensure_serena_project(str(tmp_path), runner=runner)
        assert result is False


# ===========================================================================
# T007: Node sharding
# ===========================================================================


@pytest.mark.unit
class TestNodeSharding:
    """Tests for shard_nodes() (T007)."""

    def test_distributes_nodes_round_robin(self):
        """Proves nodes distributed evenly across ports."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            ProjectRoot,
            shard_nodes,
        )

        nodes = [
            make_callable_node("src/a.py", f"func{i}", f"func{i}")
            for i in range(6)
        ]
        ports = [8330, 8331, 8332]
        roots = [ProjectRoot(path="/project", languages=["python"])]

        shards = shard_nodes(nodes, roots, ports)

        assert len(shards) == 3
        assert len(shards[8330]) == 2
        assert len(shards[8331]) == 2
        assert len(shards[8332]) == 2

    def test_filters_to_callable_and_type_only(self):
        """Proves file and block nodes are excluded."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            ProjectRoot,
            shard_nodes,
        )

        nodes = [
            make_file_node("src/a.py"),  # file — excluded
            make_callable_node("src/a.py", "func", "func"),  # callable — included
            make_type_node("src/a.py", "Cls", "Cls"),  # type — included
        ]
        ports = [8330]
        roots = [ProjectRoot(path="/project", languages=["python"])]

        shards = shard_nodes(nodes, roots, ports)
        assert len(shards[8330]) == 2  # func + Cls, not file

    def test_returns_empty_for_no_ports(self):
        """Proves empty dict when no ports available."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            ProjectRoot,
            shard_nodes,
        )

        nodes = [make_callable_node("src/a.py", "func", "func")]
        assert shard_nodes(nodes, [], []) == {}


# ===========================================================================
# T008: Reference resolution
# ===========================================================================


@pytest.mark.unit
class TestReferenceResolution:
    """Tests for resolve_node_batch() and build_node_lookup() (T008)."""

    def test_build_node_lookup_creates_index(self):
        """Proves lookup index maps (file_path, qname) → node_id."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            build_node_lookup,
        )

        node = make_callable_node("src/a.py", "foo", "MyClass.foo")
        lookup = build_node_lookup([node])
        assert ("src/a.py", "MyClass.foo") in lookup
        assert lookup[("src/a.py", "MyClass.foo")] == node.node_id

    def test_resolve_batch_creates_edges(self):
        """Proves resolution maps Serena refs to edge tuples."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            build_node_lookup,
            resolve_node_batch,
        )

        target = make_callable_node("src/b.py", "target", "target")
        source = make_callable_node("src/a.py", "caller", "caller")

        node_lookup = build_node_lookup([target, source])
        known_ids = {target.node_id, source.node_id}

        client = FakeSerenaClient()
        client.set_response("target", [
            {"file": "src/a.py", "kind": "reference", "name_path": "caller"},
        ])

        edges = asyncio.run(
            resolve_node_batch([target], 8330, node_lookup, known_ids, client=client)
        )

        assert len(edges) == 1
        assert edges[0][0] == source.node_id  # source
        assert edges[0][1] == target.node_id  # target
        assert edges[0][2] == {"edge_type": "references"}

    def test_resolve_batch_skips_unknown_refs(self):
        """Proves refs to nodes not in graph are skipped."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            build_node_lookup,
            resolve_node_batch,
        )

        target = make_callable_node("src/b.py", "target", "target")
        node_lookup = build_node_lookup([target])
        known_ids = {target.node_id}

        client = FakeSerenaClient()
        client.set_response("target", [
            {"file": "src/stdlib.py", "kind": "import", "name_path": "os.path.join"},
        ])

        edges = asyncio.run(
            resolve_node_batch([target], 8330, node_lookup, known_ids, client=client)
        )
        assert len(edges) == 0

    def test_resolve_batch_handles_timeout(self):
        """Proves timeout doesn't crash, just skips the node."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            build_node_lookup,
            resolve_node_batch,
        )

        target = make_callable_node("src/b.py", "target", "target")
        node_lookup = build_node_lookup([target])
        known_ids = {target.node_id}

        client = FakeSerenaClient()
        client.fail_for.add("target")

        edges = asyncio.run(
            resolve_node_batch([target], 8330, node_lookup, known_ids, client=client)
        )
        assert len(edges) == 0  # Timeout, no crash

    def test_resolve_batch_skips_self_references(self):
        """Proves self-references (node referencing itself) are filtered."""
        from fs2.core.services.stages.cross_file_rels_stage import (
            build_node_lookup,
            resolve_node_batch,
        )

        target = make_callable_node("src/a.py", "recursive", "recursive")
        node_lookup = build_node_lookup([target])
        known_ids = {target.node_id}

        client = FakeSerenaClient()
        client.set_response("recursive", [
            {"file": "src/a.py", "kind": "reference", "symbol": "recursive"},
        ])

        edges = asyncio.run(
            resolve_node_batch([target], 8330, node_lookup, known_ids, client=client)
        )
        assert len(edges) == 0  # Self-reference filtered


# ===========================================================================
# T010: Graceful skip
# ===========================================================================


@pytest.mark.unit
class TestGracefulSkip:
    """Tests for graceful skip when Serena unavailable (T010)."""

    def test_skips_when_serena_not_available(self, monkeypatch):
        """Proves stage skips cleanly when serena-mcp-server not on PATH."""
        from fs2.config.objects import CrossFileRelsConfig, ScanConfig
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.services.stages.cross_file_rels_stage import (
            CrossFileRelsStage,
        )

        monkeypatch.setattr(
            "fs2.core.services.stages.cross_file_rels_stage.is_serena_available",
            lambda: False,
        )

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.cross_file_rels_config = CrossFileRelsConfig()
        ctx.nodes = [make_callable_node("src/a.py", "func", "func")]

        stage = CrossFileRelsStage()
        result = stage.process(ctx)

        assert result.metrics["cross_file_rels_skipped"] is True
        assert result.metrics["cross_file_rels_reason"] == "serena_not_available"
        assert len(result.cross_file_edges) == 0
        assert len(result.errors) == 0


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
