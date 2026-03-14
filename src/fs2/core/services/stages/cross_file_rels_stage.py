"""CrossFileRelsStage - Pipeline stage for cross-file relationship resolution.

Uses Serena (LSP/Pyright) as the resolution engine, running as a pool of
parallel MCP server instances during scan. Resolves references between
callable/type nodes and collects edges for StorageStage to write.

Architecture:
- Implements PipelineStage protocol (.name, .process())
- Detects project roots via marker files (multi-language support)
- Spawns N parallel Serena MCP server instances
- Shards nodes round-robin across instances
- Resolves references via FastMCP client
- Collects edges into context.cross_file_edges

Per DYK-P2-02: Sync process() bridges to async via asyncio.run().
Per DYK-P2-04: Zero-arg constructor, hardcoded defaults until Phase 3/4 wires config.
"""

import asyncio
import atexit
import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

# Project marker files for language detection (per workshop 004)
PROJECT_MARKERS: dict[str, list[str]] = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg", "Pipfile"],
    "typescript": ["tsconfig.json"],
    "javascript": ["package.json"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
}

# Defaults (Phase 3 adds CrossFileRelsConfig, Phase 4 wires through context)
DEFAULT_PARALLEL_INSTANCES = 20
DEFAULT_BASE_PORT = 8330
DEFAULT_TIMEOUT_PER_NODE = 10.0
DEFAULT_MICRO_BATCH_SIZE = 10
PID_FILE_NAME = ".serena-pool.pid"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectRoot:
    """Detected project root with its languages."""

    path: str
    languages: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Protocols for testability (fakes over mocks per doctrine)
# ---------------------------------------------------------------------------


class SubprocessRunnerProtocol(Protocol):
    """Protocol for subprocess operations."""

    def run(
        self, cmd: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]: ...

    def popen(self, cmd: list[str], **kwargs: Any) -> subprocess.Popen[str]: ...


class SerenaPoolProtocol(Protocol):
    """Protocol for Serena instance pool management."""

    def start(
        self, n: int, base_port: int, project_root: str
    ) -> list[int]: ...

    def wait_ready(self, timeout: float) -> bool: ...

    def stop(self) -> None: ...

    @property
    def ports(self) -> list[int]: ...


class SerenaClientProtocol(Protocol):
    """Protocol for Serena MCP reference resolution."""

    async def find_referencing_symbols(
        self, name_path: str, relative_path: str, port: int
    ) -> list[dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# T003: Serena availability detection
# ---------------------------------------------------------------------------


def is_serena_available() -> bool:
    """Check if serena-mcp-server is on PATH.

    Returns:
        True if serena-mcp-server executable is found.
    """
    return shutil.which("serena-mcp-server") is not None


# ---------------------------------------------------------------------------
# T004: Project detection (marker file walk)
# ---------------------------------------------------------------------------


def detect_project_roots(scan_root: str) -> list[ProjectRoot]:
    """Detect project roots by walking for marker files.

    Walks the scan_root directory tree looking for project marker files
    (pyproject.toml, package.json, go.mod, etc.). Returns detected roots
    sorted deepest-first so child projects match before parents.

    Args:
        scan_root: Root directory to scan.

    Returns:
        List of ProjectRoot with path and detected languages.
        Sorted deepest-first.
    """
    root_path = Path(scan_root).resolve()
    found: dict[str, set[str]] = {}  # path → set of languages

    for language, markers in PROJECT_MARKERS.items():
        for marker in markers:
            # Handle glob patterns (e.g., *.csproj)
            if "*" in marker:
                for match in root_path.rglob(marker):
                    proj_dir = str(match.parent)
                    found.setdefault(proj_dir, set()).add(language)
            else:
                for match in root_path.rglob(marker):
                    proj_dir = str(match.parent)
                    found.setdefault(proj_dir, set()).add(language)

    # Sort deepest-first so child projects match before parents
    roots = [
        ProjectRoot(path=p, languages=sorted(langs))
        for p, langs in found.items()
    ]
    roots.sort(key=lambda r: r.path.count(os.sep), reverse=True)
    return roots


# ---------------------------------------------------------------------------
# T005: Serena project auto-creation
# ---------------------------------------------------------------------------


class DefaultSubprocessRunner:
    """Production subprocess runner."""

    def run(
        self, cmd: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, **kwargs)

    def popen(self, cmd: list[str], **kwargs: Any) -> subprocess.Popen[str]:
        return subprocess.Popen(cmd, **kwargs)


def ensure_serena_project(
    project_root: str,
    runner: SubprocessRunnerProtocol | None = None,
) -> bool:
    """Create Serena project if .serena/project.yml doesn't exist.

    Args:
        project_root: Path to the project root.
        runner: Subprocess runner (injectable for testing).

    Returns:
        True if project was created, False if already existed.
    """
    runner = runner or DefaultSubprocessRunner()
    serena_config = Path(project_root) / ".serena" / "project.yml"

    if serena_config.exists():
        logger.debug("Serena project already exists at %s", project_root)
        return False

    logger.info("Creating Serena project for %s (one-time setup)...", project_root)
    try:
        runner.run(
            [
                "serena",
                "project",
                "create",
                project_root,
                "--index",
                "--log-level",
                "ERROR",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning("Failed to create Serena project at %s: %s", project_root, e)
        return False


# ---------------------------------------------------------------------------
# T006: Serena instance pool
# ---------------------------------------------------------------------------


class SerenaPool:
    """Manages a pool of Serena MCP server instances.

    Per DYK-P2-05: Uses atexit handler + PID file for crash cleanup.
    Each instance spawns 3 processes (Python MCP + Python Pyright + Node Pyright).
    """

    def __init__(
        self,
        runner: SubprocessRunnerProtocol | None = None,
        pid_dir: str | None = None,
    ):
        self._runner = runner or DefaultSubprocessRunner()
        self._pid_dir = pid_dir or ".fs2"
        self._processes: list[subprocess.Popen[str]] = []
        self._ports: list[int] = []
        self._cleanup_registered = False

    @property
    def ports(self) -> list[int]:
        return list(self._ports)

    def start(
        self, n: int, base_port: int, project_root: str
    ) -> list[int]:
        """Start N Serena MCP server instances on consecutive ports.

        Args:
            n: Number of instances.
            base_port: First port number.
            project_root: Path to the Serena project.

        Returns:
            List of ports the instances are listening on.
        """
        self._ports = list(range(base_port, base_port + n))

        for port in self._ports:
            proc = self._runner.popen(
                [
                    "serena-mcp-server",
                    "--project",
                    Path(project_root).name,
                    "--transport",
                    "streamable-http",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._processes.append(proc)

        # Register cleanup handler
        if not self._cleanup_registered:
            atexit.register(self.stop)
            self._cleanup_registered = True

        # Write PID file for orphan detection
        self._write_pid_file()

        logger.info(
            "Started %d Serena instances on ports %d-%d",
            n,
            self._ports[0],
            self._ports[-1],
        )
        return self._ports

    def wait_ready(self, timeout: float = 30.0) -> bool:
        """Wait for all instances to respond to HTTP requests.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            True if all instances ready, False if timeout.
        """
        import urllib.request

        deadline = time.time() + timeout
        ready = set()

        while time.time() < deadline and len(ready) < len(self._ports):
            for port in self._ports:
                if port in ready:
                    continue
                try:
                    url = f"http://127.0.0.1:{port}/mcp/"
                    req = urllib.request.Request(url, method="GET")
                    urllib.request.urlopen(req, timeout=2)
                    ready.add(port)
                except Exception:
                    pass
            if len(ready) < len(self._ports):
                time.sleep(0.5)

        if len(ready) < len(self._ports):
            missing = set(self._ports) - ready
            logger.warning(
                "%d Serena instances failed to start: ports %s",
                len(missing),
                missing,
            )
            return False

        logger.info("All %d Serena instances ready", len(self._ports))
        return True

    def stop(self) -> None:
        """Stop all Serena instances. Safe to call multiple times."""
        import signal as sig

        for proc in self._processes:
            try:
                if proc.poll() is None:
                    os.kill(proc.pid, sig.SIGTERM)
            except (OSError, ProcessLookupError):
                pass

        # Wait for graceful shutdown
        for proc in self._processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except (OSError, ProcessLookupError):
                    pass

        self._processes.clear()
        self._remove_pid_file()

        if self._ports:
            logger.info("Stopped Serena pool (ports %d-%d)", self._ports[0], self._ports[-1])
        self._ports.clear()

    def _write_pid_file(self) -> None:
        """Write instance PIDs for orphan detection."""
        pid_path = Path(self._pid_dir) / PID_FILE_NAME
        try:
            pid_path.parent.mkdir(parents=True, exist_ok=True)
            pids = [str(p.pid) for p in self._processes]
            pid_path.write_text("\n".join(pids))
        except OSError:
            pass

    def _remove_pid_file(self) -> None:
        """Remove PID file after clean shutdown."""
        pid_path = Path(self._pid_dir) / PID_FILE_NAME
        try:
            pid_path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def cleanup_orphans(pid_dir: str = ".fs2") -> int:
        """Kill orphaned Serena instances from a prior crashed scan.

        Args:
            pid_dir: Directory containing the PID file.

        Returns:
            Number of orphaned processes killed.
        """
        import signal as sig

        pid_path = Path(pid_dir) / PID_FILE_NAME
        if not pid_path.exists():
            return 0

        killed = 0
        try:
            pids = pid_path.read_text().strip().split("\n")
            for pid_str in pids:
                try:
                    pid = int(pid_str)
                    os.kill(pid, sig.SIGTERM)
                    killed += 1
                except (ValueError, OSError, ProcessLookupError):
                    pass
            pid_path.unlink(missing_ok=True)
        except OSError:
            pass

        if killed:
            logger.info("Cleaned up %d orphaned Serena processes", killed)
        return killed


# ---------------------------------------------------------------------------
# T007: Node sharding
# ---------------------------------------------------------------------------


def get_project_for_node(
    node_file_path: str,
    project_roots: list[ProjectRoot],
) -> ProjectRoot | None:
    """Find which project root a node belongs to.

    Args:
        node_file_path: The node's file path (from CodeNode.file_path).
        project_roots: List of detected project roots (deepest-first).

    Returns:
        The matching ProjectRoot, or None if no match.
    """
    abs_path = str(Path(node_file_path).resolve())
    for root in project_roots:
        if abs_path.startswith(root.path):
            return root
    return None


def shard_nodes(
    nodes: list["CodeNode"],
    project_roots: list[ProjectRoot],
    ports: list[int],
) -> dict[int, list["CodeNode"]]:
    """Shard nodes round-robin across Serena instance ports.

    Level 1: Group by project root.
    Level 2: Round-robin within each group across available ports.
    Nodes not matching any project root are skipped.

    Args:
        nodes: All callable/type nodes to resolve.
        project_roots: Detected project roots.
        ports: Available Serena instance ports.

    Returns:
        Dict mapping port → list of nodes assigned to that port.
    """
    if not ports:
        return {}

    result: dict[int, list["CodeNode"]] = {port: [] for port in ports}
    skipped = 0

    # Filter to callable/type nodes only (file, block, section nodes don't need resolution)
    resolvable = [n for n in nodes if n.category in ("callable", "type")]

    for i, node in enumerate(resolvable):
        port = ports[i % len(ports)]
        result[port].append(node)

    return result


# ---------------------------------------------------------------------------
# T008: Reference resolution
# ---------------------------------------------------------------------------


def build_node_lookup(
    nodes: list["CodeNode"],
) -> dict[tuple[str, str], str]:
    """Build a lookup index from (file_path, qualified_name) → node_id.

    Per DYK-P2-03: This index is the key data structure for mapping
    Serena responses back to fs2 node_ids.

    Args:
        nodes: All nodes in the graph.

    Returns:
        Dict mapping (file_path, qualified_name) to node_id.
    """
    lookup: dict[tuple[str, str], str] = {}
    for node in nodes:
        lookup[(node.file_path, node.qualified_name)] = node.node_id
    return lookup


class DefaultSerenaClient:
    """Production Serena MCP client using FastMCP."""

    async def find_referencing_symbols(
        self, name_path: str, relative_path: str, port: int
    ) -> list[dict[str, Any]]:
        """Query a Serena instance for symbols that reference a given symbol.

        Args:
            name_path: Symbol path with "/" separators (e.g., "MyClass/method").
            relative_path: File path relative to project root.
            port: Serena instance port.

        Returns:
            List of reference dicts with file and symbol info.
        """
        from fastmcp import Client

        url = f"http://127.0.0.1:{port}/mcp/"
        refs: list[dict[str, Any]] = []

        async with Client(url) as client:
            result = await asyncio.wait_for(
                client.call_tool(
                    "find_referencing_symbols",
                    {
                        "name_path": name_path,
                        "relative_path": relative_path,
                    },
                ),
                timeout=DEFAULT_TIMEOUT_PER_NODE,
            )

            if hasattr(result, "content"):
                for item in result.content:
                    text = getattr(item, "text", "")
                    if text:
                        try:
                            data = json.loads(text)
                            # Serena returns {file_path: {kind: [refs]}}
                            for file_path, kinds in data.items():
                                if isinstance(kinds, dict):
                                    for kind, symbols in kinds.items():
                                        if isinstance(symbols, list):
                                            for sym in symbols:
                                                refs.append(
                                                    {
                                                        "file": file_path,
                                                        "kind": kind,
                                                        "symbol": sym
                                                        if isinstance(sym, str)
                                                        else str(sym),
                                                    }
                                                )
                        except (json.JSONDecodeError, TypeError):
                            pass

        return refs


async def resolve_node_batch(
    batch: list["CodeNode"],
    port: int,
    node_lookup: dict[tuple[str, str], str],
    known_node_ids: set[str],
    client: SerenaClientProtocol | None = None,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Resolve references for a batch of nodes on one Serena instance.

    Args:
        batch: Nodes to resolve.
        port: Serena instance port.
        node_lookup: (file_path, qualified_name) → node_id index.
        known_node_ids: Set of all node_ids in the graph.
        client: Injectable client (for testing).

    Returns:
        List of (source_node_id, target_node_id, edge_data) tuples.
    """
    client = client or DefaultSerenaClient()
    edges: list[tuple[str, str, dict[str, Any]]] = []

    for node in batch:
        try:
            # Convert qualified_name to Serena's name_path format
            name_path = node.qualified_name.replace(".", "/")
            refs = await client.find_referencing_symbols(
                name_path=name_path,
                relative_path=node.file_path,
                port=port,
            )

            for ref in refs:
                ref_file = ref.get("file", "")
                ref_symbol = ref.get("symbol", "")

                # Try to find the referencing node in our graph
                source_id = node_lookup.get((ref_file, ref_symbol))
                if source_id and source_id in known_node_ids:
                    target_id = node.node_id
                    if source_id != target_id:  # no self-references
                        edges.append(
                            (source_id, target_id, {"edge_type": "references"})
                        )

        except asyncio.TimeoutError:
            logger.warning(
                "Timeout resolving %s (port %d)", node.node_id, port
            )
        except Exception as e:
            logger.warning(
                "Error resolving %s (port %d): %s", node.node_id, port, e
            )

    return edges


# ---------------------------------------------------------------------------
# T008: Incremental resolution helpers
# ---------------------------------------------------------------------------


def get_changed_file_paths(
    current_nodes: list["CodeNode"],
    prior_nodes: "dict[str, CodeNode] | None",
) -> set[str] | None:
    """Identify file paths that have changed since prior scan.

    Compares content_hash of file-category nodes between current and prior.
    Same pattern as SmartContentStage._merge_prior_smart_content().

    Args:
        current_nodes: Fresh nodes from ParsingStage.
        prior_nodes: Prior node dict (None on first scan).

    Returns:
        Set of changed file paths, or None if all files should be processed
        (first scan — no prior data).
    """
    if prior_nodes is None:
        return None

    changed: set[str] = set()
    for node in current_nodes:
        if node.category != "file":
            continue
        file_path = node.file_path
        prior = prior_nodes.get(node.node_id)
        if prior is None or node.content_hash != prior.content_hash:
            changed.add(file_path)

    return changed


def filter_nodes_to_changed(
    nodes: list["CodeNode"],
    changed_files: set[str] | None,
) -> list["CodeNode"]:
    """Filter nodes to only those from changed files.

    Args:
        nodes: All resolvable nodes.
        changed_files: Set of changed file paths, or None for all.

    Returns:
        Filtered list of nodes from changed files only.
    """
    if changed_files is None:
        return nodes

    return [n for n in nodes if n.file_path in changed_files]


def reuse_prior_edges(
    prior_edges: "list[tuple[str, str, dict[str, Any]]] | None",
    changed_files: set[str] | None,
    current_node_ids: set[str],
) -> list[tuple[str, str, dict[str, Any]]]:
    """Reuse edges from prior scan for unchanged files.

    An edge is reusable when:
    1. Both endpoints still exist in the current graph
    2. Neither endpoint's file has changed

    Args:
        prior_edges: Edges from prior scan (None on first scan).
        changed_files: Set of changed file paths (None = all changed).
        current_node_ids: Set of node_ids in current scan.

    Returns:
        List of edges to carry forward from prior scan.
    """
    if prior_edges is None or changed_files is None:
        return []

    reused: list[tuple[str, str, dict[str, Any]]] = []
    for source_id, target_id, edge_data in prior_edges:
        # Both endpoints must still exist
        if source_id not in current_node_ids or target_id not in current_node_ids:
            continue

        # Extract file paths from node_ids
        source_file = source_id.split(":", 2)[1] if ":" in source_id else ""
        target_file = target_id.split(":", 2)[1] if ":" in target_id else ""

        # Skip if either file changed (will be re-resolved)
        if source_file in changed_files or target_file in changed_files:
            continue

        reused.append((source_id, target_id, edge_data))

    return reused


# ---------------------------------------------------------------------------
# T009 + T010: CrossFileRelsStage
# ---------------------------------------------------------------------------


class CrossFileRelsStage:
    """Pipeline stage for cross-file relationship resolution using Serena.

    Per DYK-P2-02: Sync process() bridges to async via asyncio.run().
    Per DYK-P2-04: Zero-arg constructor; uses hardcoded defaults.
    Phase 3 adds CrossFileRelsConfig, Phase 4 wires through context.
    """

    @property
    def name(self) -> str:
        """Human-readable stage name."""
        return "cross_file_rels"

    def process(self, context: "PipelineContext") -> "PipelineContext":
        """Resolve cross-file references and collect edges.

        Full flow: detect → projects → pool → shard → resolve → collect → stop.

        Args:
            context: Pipeline context with nodes from ParsingStage.

        Returns:
            Context with cross_file_edges populated.
        """
        start_time = time.time()

        # T010: Graceful skip if Serena not available
        if not is_serena_available():
            logger.info(
                "serena-mcp-server not found. Skipping cross-file relationships. "
                "Install with: uv tool install serena-agent"
            )
            context.metrics["cross_file_rels_skipped"] = True
            context.metrics["cross_file_rels_reason"] = "serena_not_available"
            return context

        # Clean up orphans from prior crashed scan
        SerenaPool.cleanup_orphans()

        # T004: Detect project roots
        scan_root = str(Path(context.graph_path).parent.parent)
        project_roots = detect_project_roots(scan_root)
        if not project_roots:
            logger.info("No project roots detected. Skipping cross-file relationships.")
            context.metrics["cross_file_rels_skipped"] = True
            context.metrics["cross_file_rels_reason"] = "no_project_roots"
            return context

        logger.info(
            "Detected %d project root(s): %s",
            len(project_roots),
            [r.path for r in project_roots],
        )

        # T005: Ensure Serena projects exist
        for root in project_roots:
            ensure_serena_project(root.path)

        # T006: Start instance pool
        pool = SerenaPool()
        n_instances = min(DEFAULT_PARALLEL_INSTANCES, len(context.nodes))
        if n_instances < 1:
            n_instances = 1

        try:
            pool.start(n_instances, DEFAULT_BASE_PORT, project_roots[0].path)
            if not pool.wait_ready(timeout=60.0):
                logger.warning("Some Serena instances failed to start. Continuing with available.")

            # T007: Shard nodes
            shards = shard_nodes(context.nodes, project_roots, pool.ports)

            # T008: Resolve in micro-batches
            node_lookup = build_node_lookup(context.nodes)
            known_ids = {n.node_id for n in context.nodes}
            all_edges: list[tuple[str, str, dict[str, Any]]] = []
            total_resolved = 0

            for port, port_nodes in shards.items():
                # Process in micro-batches of DEFAULT_MICRO_BATCH_SIZE
                for batch_start in range(0, len(port_nodes), DEFAULT_MICRO_BATCH_SIZE):
                    batch = port_nodes[batch_start : batch_start + DEFAULT_MICRO_BATCH_SIZE]

                    batch_edges = asyncio.run(
                        resolve_node_batch(
                            batch, port, node_lookup, known_ids
                        )
                    )
                    all_edges.extend(batch_edges)
                    total_resolved += len(batch)

                    if total_resolved % 100 == 0:
                        logger.info(
                            "Cross-file resolution: %d/%d nodes processed, %d edges found",
                            total_resolved,
                            sum(len(v) for v in shards.values()),
                            len(all_edges),
                        )

            context.cross_file_edges = all_edges

        finally:
            pool.stop()

        elapsed = time.time() - start_time
        context.metrics["cross_file_rels_time_s"] = round(elapsed, 2)
        context.metrics["cross_file_rels_edges"] = len(context.cross_file_edges)
        context.metrics["cross_file_rels_nodes_resolved"] = total_resolved
        context.metrics["cross_file_rels_instances"] = n_instances
        context.metrics["cross_file_rels_skipped"] = False

        logger.info(
            "Cross-file resolution complete: %d edges from %d nodes in %.1fs",
            len(context.cross_file_edges),
            total_resolved,
            elapsed,
        )

        return context
