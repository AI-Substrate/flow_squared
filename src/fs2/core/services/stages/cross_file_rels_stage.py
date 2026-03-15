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
DEFAULT_PARALLEL_INSTANCES = 15
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


_SKIP_DIRS = frozenset({
    ".venv", "venv", ".env", "env",
    "node_modules",
    ".git", ".hg", ".svn",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".tox", ".nox",
    "site-packages",
    "dist", "build", ".eggs",
})


def detect_project_roots(scan_root: str) -> list[ProjectRoot]:
    """Detect project roots by walking for marker files.

    Walks the scan_root directory tree looking for project marker files
    (pyproject.toml, package.json, go.mod, etc.). Returns detected roots
    sorted deepest-first so child projects match before parents.

    Skips vendored/dependency directories (.venv, node_modules, etc.)
    to avoid detecting projects inside installed packages.

    Args:
        scan_root: Root directory to scan.

    Returns:
        List of ProjectRoot with path and detected languages.
        Sorted deepest-first.
    """
    root_path = Path(scan_root).resolve()
    found: dict[str, set[str]] = {}  # path → set of languages

    # Collect all marker filenames and glob patterns
    plain_markers: dict[str, str] = {}  # filename → language
    glob_markers: list[tuple[str, str]] = []  # (pattern, language)
    for language, markers in PROJECT_MARKERS.items():
        for marker in markers:
            if "*" in marker:
                glob_markers.append((marker, language))
            else:
                plain_markers[marker] = language

    # Single walk with directory pruning
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune vendored/dependency directories in-place
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

        for fname in filenames:
            if fname in plain_markers:
                found.setdefault(dirpath, set()).add(plain_markers[fname])
            else:
                for pattern, language in glob_markers:
                    if Path(fname).match(pattern):
                        found.setdefault(dirpath, set()).add(language)

    # Deduplicate: if a root is a subdirectory of another root, drop the child.
    # The parent's LSP covers children, and child "projects" are often
    # test fixtures or vendored code (e.g. tests/fixtures/samples/json/package.json).
    all_paths = sorted(found.keys())
    kept: set[str] = set()
    for p in all_paths:
        if not any(p.startswith(parent + os.sep) for parent in kept):
            kept.add(p)

    roots = [
        ProjectRoot(path=p, languages=sorted(langs))
        for p, langs in found.items()
        if p in kept
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
    languages: list[str] | None = None,
    runner: SubprocessRunnerProtocol | None = None,
    timeout: float = 120.0,
) -> bool:
    """Create Serena project if .serena/project.yml doesn't exist.

    Args:
        project_root: Path to the project root.
        languages: Explicit languages to enable (skips interactive prompts).
        runner: Subprocess runner (injectable for testing).
        timeout: Maximum seconds to wait for project creation.

    Returns:
        True if project was created, False if already existed.
    """
    runner = runner or DefaultSubprocessRunner()
    serena_config = Path(project_root) / ".serena" / "project.yml"

    if serena_config.exists():
        logger.debug("Serena project already exists at %s", project_root)
        return False

    logger.info("Creating Serena project for %s (one-time setup)...", project_root)
    cmd = [
        "serena",
        "project",
        "create",
        project_root,
        "--index",
        "--log-level",
        "ERROR",
    ]
    # Pass explicit languages to avoid interactive prompts
    for lang in (languages or []):
        cmd.extend(["--language", lang])

    try:
        runner.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            input="\n" * 20,  # Fallback: answer any remaining prompts with defaults
        )
        return True
    except subprocess.TimeoutExpired:
        logger.warning("Timed out creating Serena project at %s (%.0fs)", project_root, timeout)
        return False
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
                    project_root,
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
        import urllib.error
        import urllib.request

        deadline = time.time() + timeout
        ready = set()

        while time.time() < deadline and len(ready) < len(self._ports):
            for port in self._ports:
                if port in ready:
                    continue
                try:
                    url = f"http://127.0.0.1:{port}/mcp"
                    req = urllib.request.Request(url, method="GET")
                    try:
                        urllib.request.urlopen(req, timeout=2)
                    except urllib.error.HTTPError:
                        pass  # Any HTTP response means server is up
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
    """Production Serena MCP client using FastMCP.

    Reuses a single HTTP session per port for performance.
    Must be used as an async context manager or have connect()/disconnect() called.
    """

    def __init__(self):
        self._clients: dict[int, Any] = {}  # port → connected Client

    async def _get_client(self, port: int):
        """Get or create a persistent client for a port."""
        if port not in self._clients:
            from fastmcp import Client

            url = f"http://127.0.0.1:{port}/mcp/"
            client = Client(url)
            await client.__aenter__()
            self._clients[port] = client
        return self._clients[port]

    async def close(self):
        """Close all persistent connections."""
        for client in self._clients.values():
            try:
                await client.__aexit__(None, None, None)
            except Exception:
                pass
        self._clients.clear()

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
        client = await self._get_client(port)
        refs: list[dict[str, Any]] = []

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
                        # Each ref is a dict with name_path, body_location, etc.
                        for file_path, kinds in data.items():
                            if isinstance(kinds, dict):
                                for kind, symbols in kinds.items():
                                    if isinstance(symbols, list):
                                        for sym in symbols:
                                            sym_name = ""
                                            if isinstance(sym, dict):
                                                sym_name = sym.get("name_path", "")
                                            elif isinstance(sym, str):
                                                sym_name = sym
                                            if sym_name:
                                                refs.append(
                                                    {
                                                        "file": file_path,
                                                        "kind": kind,
                                                        "name_path": sym_name,
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

            logger.debug(
                "Serena refs for %s (%s): %d refs found",
                node.node_id, name_path, len(refs),
            )

            for ref in refs:
                ref_file = ref.get("file", "")
                ref_name_path = ref.get("name_path", "")

                # Convert Serena's "/" name_path to "." qualified_name for lookup
                ref_qualified = ref_name_path.replace("/", ".")

                # Try to find the referencing node in our graph
                source_id = node_lookup.get((ref_file, ref_qualified))
                if source_id and source_id in known_node_ids:
                    target_id = node.node_id
                    if source_id != target_id:  # no self-references
                        edges.append(
                            (source_id, target_id, {"edge_type": "references"})
                        )
                else:
                    logger.debug(
                        "  ref not matched: file=%s name_path=%r qualified=%r (lookup_hit=%s)",
                        ref_file, ref_name_path, ref_qualified, source_id is not None,
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
    Per DYK-P4-01: Accepts pool_factory for testability (fakes over mocks).
    Per DYK-P4-02: Checks config.enabled before serena availability.
    """

    def __init__(self, pool_factory: type | None = None):
        """Initialize stage with optional pool factory for DI.

        Args:
            pool_factory: Class to use for creating Serena pools.
                          Defaults to SerenaPool. Tests pass FakeSerenaPool.
        """
        self._pool_factory = pool_factory or SerenaPool

    @property
    def name(self) -> str:
        """Human-readable stage name."""
        return "cross_file_rels"

    def process(self, context: "PipelineContext") -> "PipelineContext":
        """Resolve cross-file references and collect edges.

        Full flow: config check → serena check → detect → projects →
        incremental filter → pool → shard → resolve → merge → collect → stop.

        Args:
            context: Pipeline context with nodes from ParsingStage.

        Returns:
            Context with cross_file_edges populated.
        """
        start_time = time.time()

        # Get progress callback for user-visible output
        progress_cb = getattr(context, "cross_file_rels_progress_callback", None)

        # DYK-P4-02: Check config FIRST (before serena check and orphan cleanup)
        config = getattr(context, "cross_file_rels_config", None)
        if config is None:
            logger.info("No cross_file_rels_config in context. Skipping cross-file relationships.")
            context.metrics["cross_file_rels_skipped"] = True
            context.metrics["cross_file_rels_reason"] = "no_config"
            if progress_cb:
                progress_cb("skipped", "no config provided")
            return context

        if not config.enabled:
            logger.info("Cross-file relationships disabled by config.")
            context.metrics["cross_file_rels_skipped"] = True
            context.metrics["cross_file_rels_reason"] = "disabled"
            if progress_cb:
                progress_cb("skipped", "disabled by config")
            return context

        # T010: Graceful skip if Serena not available
        if not is_serena_available():
            logger.info(
                "serena-mcp-server not found. Skipping cross-file relationships. "
                "Install with: uv tool install serena-agent"
            )
            context.metrics["cross_file_rels_skipped"] = True
            context.metrics["cross_file_rels_reason"] = "serena_not_available"
            if progress_cb:
                progress_cb("skipped", "serena-mcp-server not found")
            return context

        # Show banner immediately so user knows the stage is active
        if progress_cb:
            progress_cb("preparing", "cleaning up prior processes")

        # Clean up orphans from prior crashed scan
        SerenaPool.cleanup_orphans()

        # DYK-P4-04: Detect project roots from scan_root + scan_paths (not graph_path hack)
        if progress_cb:
            progress_cb("preparing", "detecting project roots")

        scan_root = str(getattr(context, "scan_root", Path.cwd().resolve()))
        search_roots = {scan_root}
        if hasattr(context, "scan_config") and hasattr(context.scan_config, "scan_paths"):
            for sp in context.scan_config.scan_paths:
                resolved = str(Path(sp).resolve())
                search_roots.add(resolved)

        all_project_roots: list[ProjectRoot] = []
        seen_paths: set[str] = set()
        for root in search_roots:
            for pr in detect_project_roots(root):
                if pr.path not in seen_paths:
                    all_project_roots.append(pr)
                    seen_paths.add(pr.path)

        if not all_project_roots:
            logger.info("No project roots detected. Skipping cross-file relationships.")
            context.metrics["cross_file_rels_skipped"] = True
            context.metrics["cross_file_rels_reason"] = "no_project_roots"
            if progress_cb:
                progress_cb("skipped", "no project roots detected")
            return context

        logger.info(
            "Detected %d project root(s): %s",
            len(all_project_roots),
            [r.path for r in all_project_roots],
        )

        # T005: Ensure Serena projects exist
        if progress_cb:
            progress_cb("preparing", f"setting up LSP for {len(all_project_roots)} project(s)")

        for root in all_project_roots:
            ensure_serena_project(root.path, languages=root.languages)

        # Incremental resolution: determine changed files
        changed_files = get_changed_file_paths(context.nodes, context.prior_nodes)
        reused_edges = reuse_prior_edges(
            getattr(context, "prior_cross_file_edges", None),
            changed_files,
            {n.node_id for n in context.nodes},
        )

        # Filter nodes to only those from changed files
        resolvable = [n for n in context.nodes if n.category in ("callable", "type")]
        nodes_to_resolve = filter_nodes_to_changed(resolvable, changed_files)

        if not nodes_to_resolve:
            # All files unchanged — reuse all prior edges
            context.cross_file_edges = reused_edges
            elapsed = time.time() - start_time
            context.metrics["cross_file_rels_time_s"] = round(elapsed, 2)
            context.metrics["cross_file_rels_edges"] = len(reused_edges)
            context.metrics["cross_file_rels_preserved"] = len(reused_edges)
            context.metrics["cross_file_rels_resolved"] = 0
            context.metrics["cross_file_rels_skipped"] = False
            logger.info(
                "Cross-file resolution: all files unchanged, reused %d prior edges (%.1fs)",
                len(reused_edges),
                elapsed,
            )
            if progress_cb:
                progress_cb("reused", f"all files unchanged, reused {len(reused_edges)} edges")
            return context

        logger.info(
            "Cross-file resolution: %d nodes to resolve (%d unchanged files, %d reused edges)",
            len(nodes_to_resolve),
            len(resolvable) - len(nodes_to_resolve),
            len(reused_edges),
        )
        if progress_cb:
            progress_cb(
                "starting",
                f"{len(nodes_to_resolve)} nodes to resolve ({len(reused_edges)} edges reused)",
            )

        # Read config values (with defaults fallback)
        n_instances = min(config.parallel_instances, len(nodes_to_resolve))
        if n_instances < 1:
            n_instances = 1
        base_port = config.serena_base_port

        # T006: Start instance pool
        pool = self._pool_factory()

        try:
            if progress_cb:
                progress_cb("preparing", f"starting {n_instances} LSP instance(s)")

            pool.start(n_instances, base_port, all_project_roots[0].path)
            if not pool.wait_ready(timeout=60.0):
                logger.warning("Some Serena instances failed to start. Continuing with available.")

            # T007: Shard nodes
            shards = shard_nodes(nodes_to_resolve, all_project_roots, pool.ports)

            # T008: Resolve with all ports running concurrently
            node_lookup = build_node_lookup(context.nodes)
            known_ids = {n.node_id for n in context.nodes}
            total_nodes = sum(len(v) for v in shards.values())

            # Shared mutable counter for cross-port progress
            progress_state = {"resolved": 0, "edges": 0, "last_time": time.time()}

            async def _resolve_port(p_nodes, p_port):
                client = DefaultSerenaClient()
                try:
                    port_edges = []
                    for node in p_nodes:
                        try:
                            np = node.qualified_name.replace(".", "/")
                            refs = await client.find_referencing_symbols(
                                name_path=np,
                                relative_path=node.file_path,
                                port=p_port,
                            )
                            logger.debug(
                                "Serena refs for %s (%s): %d refs found",
                                node.node_id, np, len(refs),
                            )
                            for ref in refs:
                                ref_file = ref.get("file", "")
                                ref_name_path = ref.get("name_path", "")
                                ref_qualified = ref_name_path.replace("/", ".")
                                source_id = node_lookup.get((ref_file, ref_qualified))
                                if source_id and source_id in known_ids:
                                    if source_id != node.node_id:
                                        port_edges.append(
                                            (source_id, node.node_id, {"edge_type": "references"})
                                        )
                                else:
                                    logger.debug(
                                        "  ref not matched: file=%s name_path=%r qualified=%r",
                                        ref_file, ref_name_path, ref_qualified,
                                    )
                        except TimeoutError:
                            logger.warning("Timeout resolving %s (port %d)", node.node_id, p_port)
                        except Exception as e:
                            logger.warning("Error resolving %s (port %d): %s", node.node_id, p_port, e)
                            try:
                                await client.close()
                            except Exception:
                                pass
                            client = DefaultSerenaClient()

                        # Update shared progress counter
                        progress_state["resolved"] += 1
                        progress_state["edges"] += len(port_edges) - progress_state.get(f"_last_{p_port}", 0)
                        progress_state[f"_last_{p_port}"] = len(port_edges)

                        done = progress_state["resolved"]
                        if progress_cb and (done % 50 == 0 or done == total_nodes):
                            now = time.time()
                            pct = (done / total_nodes * 100) if total_nodes else 0
                            remaining = total_nodes - done
                            elapsed_batch = now - progress_state["last_time"]
                            if elapsed_batch > 0:
                                rate = 50 / elapsed_batch if done >= 50 else done / elapsed_batch
                                eta_s = remaining / rate if rate > 0 else 0
                                if eta_s >= 60:
                                    eta_str = f" ~{eta_s / 60:.1f}m remaining"
                                else:
                                    eta_str = f" ~{eta_s:.0f}s remaining"
                            else:
                                eta_str = ""
                            progress_state["last_time"] = now
                            progress_cb(
                                "progress",
                                f"{done}/{total_nodes} nodes ({pct:.0f}%), "
                                f"{progress_state['edges']} edges{eta_str}",
                            )

                    return port_edges
                finally:
                    await client.close()

            async def _resolve_all():
                tasks = [
                    _resolve_port(p_nodes, p_port)
                    for p_port, p_nodes in shards.items()
                ]
                return await asyncio.gather(*tasks)

            all_port_edges = asyncio.run(_resolve_all())
            fresh_edges: list[tuple[str, str, dict[str, Any]]] = []
            for port_edges in all_port_edges:
                fresh_edges.extend(port_edges)
            total_resolved = total_nodes

            # Merge reused + fresh edges
            context.cross_file_edges = reused_edges + fresh_edges

        finally:
            pool.stop()

        elapsed = time.time() - start_time
        context.metrics["cross_file_rels_time_s"] = round(elapsed, 2)
        context.metrics["cross_file_rels_edges"] = len(context.cross_file_edges)
        context.metrics["cross_file_rels_preserved"] = len(reused_edges)
        context.metrics["cross_file_rels_resolved"] = total_resolved
        context.metrics["cross_file_rels_instances"] = n_instances
        context.metrics["cross_file_rels_skipped"] = False

        logger.info(
            "Cross-file resolution complete: %d edges (%d fresh + %d reused) from %d nodes in %.1fs",
            len(context.cross_file_edges),
            len(fresh_edges),
            len(reused_edges),
            total_resolved,
            elapsed,
        )
        if progress_cb:
            progress_cb(
                "complete",
                f"{len(context.cross_file_edges)} edges ({len(fresh_edges)} fresh + {len(reused_edges)} reused) in {elapsed:.1f}s",
            )

        return context
