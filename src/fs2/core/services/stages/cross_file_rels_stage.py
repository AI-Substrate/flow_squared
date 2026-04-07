"""CrossFileRelsStage - Pipeline stage for cross-file relationship resolution.

Uses SCIP (Source Code Intelligence Protocol) indexers for offline, batch
cross-file reference extraction.

Architecture:
- Implements PipelineStage protocol (.name, .process())
- Reads ProjectsConfig for project entries (or auto-discovers from markers)
- Invokes per-language SCIP indexers via subprocess
- Parses index.scip with language-specific SCIPAdapter
- Collects edges into context.cross_file_edges
- Supports incremental resolution (reuse edges for unchanged files)
"""

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SCIP indexer command templates (per Workshop 001)
# ---------------------------------------------------------------------------


def _python_cmd(project_path: str, output_path: str) -> list[str]:
    slug = Path(project_path).name or "project"
    return ["scip-python", "index", ".", f"--project-name={slug}", f"--output={output_path}"]


def _typescript_cmd(project_path: str, output_path: str) -> list[str]:
    return ["scip-typescript", "index", "--output", output_path]


def _javascript_cmd(project_path: str, output_path: str) -> list[str]:
    return ["scip-typescript", "index", "--infer-tsconfig", "--output", output_path]


def _go_cmd(project_path: str, output_path: str) -> list[str]:
    return ["scip-go", f"--output={output_path}", "./..."]


def _dotnet_cmd(project_path: str, output_path: str) -> list[str]:
    return ["scip-dotnet", "index", f"--output={output_path}"]


INDEXER_COMMANDS: dict[str, tuple[str, Any]] = {
    "python": ("scip-python", _python_cmd),
    "typescript": ("scip-typescript", _typescript_cmd),
    "javascript": ("scip-typescript", _javascript_cmd),
    "go": ("scip-go", _go_cmd),
    "dotnet": ("scip-dotnet", _dotnet_cmd),
}

PRE_BUILD_REQUIRED: dict[str, str] = {
    "dotnet": "dotnet build",
}


# ---------------------------------------------------------------------------
# SCIP indexer invocation
# ---------------------------------------------------------------------------


def run_scip_indexer(
    language: str,
    project_path: str,
    output_path: str,
) -> bool:
    """Run the SCIP indexer for a language project.

    Runs the indexer subprocess in the project directory.

    Returns:
        True if indexing succeeded, False otherwise.
    """
    entry = INDEXER_COMMANDS.get(language)
    if entry is None:
        logger.warning("No SCIP indexer configured for language: %s", language)
        return False

    binary_name, cmd_builder = entry

    if shutil.which(binary_name) is None:
        from fs2.core.services.project_discovery import INDEXER_INSTALL

        hint = INDEXER_INSTALL.get(language, f"install {binary_name}")
        logger.info(
            "SCIP indexer '%s' not found for %s. Install with: %s",
            binary_name, language, hint,
        )
        return False

    # Pre-build check (e.g., C# needs dotnet build first)
    if language in PRE_BUILD_REQUIRED:
        build_cmd = PRE_BUILD_REQUIRED[language]
        if language == "dotnet" and not (Path(project_path) / "obj").exists():
            logger.warning(
                "C# project at %s needs building first. Run '%s' in the project directory.",
                project_path, build_cmd,
            )
            return False

    cmd = cmd_builder(project_path, output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info("Running SCIP indexer: %s (cwd=%s)", " ".join(cmd), project_path)

    try:
        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            logger.warning(
                "SCIP indexer failed for %s (exit %d): %s",
                language, result.returncode, result.stderr[:500],
            )
            return False

        if not Path(output_path).exists():
            logger.warning("SCIP indexer ran but no index.scip produced at %s", output_path)
            return False

        size = Path(output_path).stat().st_size
        logger.info("SCIP index produced: %s (%d bytes)", output_path, size)
        return True

    except subprocess.TimeoutExpired:
        logger.warning("SCIP indexer timed out for %s at %s", language, project_path)
        return False
    except FileNotFoundError:
        logger.warning("SCIP indexer binary not found: %s", binary_name)
        return False
    except Exception as e:
        logger.warning("SCIP indexer error for %s: %s", language, e)
        return False


# ---------------------------------------------------------------------------
# Cache directory management
# ---------------------------------------------------------------------------


def _project_slug(project_path: str, language: str, repo_root: str) -> str:
    """Generate a cache slug for a project."""
    try:
        rel = str(Path(project_path).relative_to(repo_root))
    except ValueError:
        rel = project_path
    slug = rel.replace(os.sep, "_").replace(".", "_").strip("_")
    if not slug or slug == "_":
        slug = "root"
    return f"{slug}_{language}"


def _ensure_cache_gitignore(cache_dir: Path) -> None:
    """Create .gitignore in cache directory if it doesn't exist."""
    gitignore = cache_dir / ".gitignore"
    if not gitignore.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        gitignore.write_text("# SCIP index cache\n*\n!.gitignore\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Incremental resolution helpers
# ---------------------------------------------------------------------------


def get_changed_file_paths(
    current_nodes: list["CodeNode"],
    prior_nodes: "dict[str, CodeNode] | None",
) -> set[str] | None:
    """Identify file paths that have changed since prior scan."""
    if prior_nodes is None:
        return None

    changed: set[str] = set()
    for node in current_nodes:
        if node.category != "file":
            continue
        prior = prior_nodes.get(node.node_id)
        if prior is None or node.content_hash != prior.content_hash:
            changed.add(node.file_path)

    return changed


def filter_nodes_to_changed(
    nodes: list["CodeNode"],
    changed_files: set[str] | None,
) -> list["CodeNode"]:
    """Filter nodes to only those from changed files."""
    if changed_files is None:
        return nodes
    return [n for n in nodes if n.file_path in changed_files]


def reuse_prior_edges(
    prior_edges: "list[tuple[str, str, dict[str, Any]]] | None",
    changed_files: set[str] | None,
    current_node_ids: set[str],
) -> list[tuple[str, str, dict[str, Any]]]:
    """Reuse edges from prior scan for unchanged files."""
    if prior_edges is None or changed_files is None:
        return []

    reused: list[tuple[str, str, dict[str, Any]]] = []
    for source_id, target_id, edge_data in prior_edges:
        if source_id not in current_node_ids or target_id not in current_node_ids:
            continue
        source_file = source_id.split(":", 2)[1] if ":" in source_id else ""
        target_file = target_id.split(":", 2)[1] if ":" in target_id else ""
        if source_file in changed_files or target_file in changed_files:
            continue
        reused.append((source_id, target_id, edge_data))

    return reused


# ---------------------------------------------------------------------------
# CrossFileRelsStage
# ---------------------------------------------------------------------------


class CrossFileRelsStage:
    """Pipeline stage for cross-file relationship resolution using SCIP."""

    @property
    def name(self) -> str:
        return "cross_file_rels"

    def process(self, context: "PipelineContext") -> "PipelineContext":
        """Resolve cross-file references via SCIP indexers."""
        start_time = time.time()
        progress_cb = getattr(context, "cross_file_rels_progress_callback", None)

        # --- Config checks ---
        config = getattr(context, "cross_file_rels_config", None)
        if config is None:
            context.metrics["cross_file_rels_skipped"] = True
            context.metrics["cross_file_rels_reason"] = "no_config"
            if progress_cb:
                progress_cb("skipped", "no config provided")
            return context

        if not config.enabled:
            context.metrics["cross_file_rels_skipped"] = True
            context.metrics["cross_file_rels_reason"] = "disabled"
            if progress_cb:
                progress_cb("skipped", "disabled by config")
            return context

        # --- Load project entries ---
        projects_config = getattr(context, "projects_config", None)
        projects = self._resolve_projects(projects_config, context)

        if not projects:
            context.metrics["cross_file_rels_skipped"] = True
            context.metrics["cross_file_rels_reason"] = "no_projects"
            if progress_cb:
                progress_cb("skipped", "no projects configured or discovered")
            return context

        # --- Incremental resolution ---
        changed_files = get_changed_file_paths(context.nodes, context.prior_nodes)
        reused_edges = reuse_prior_edges(
            getattr(context, "prior_cross_file_edges", None),
            changed_files,
            {n.node_id for n in context.nodes},
        )

        # TODO: Per-project incremental (see suggestions.md)
        resolvable = [n for n in context.nodes if n.category in ("callable", "type")]
        nodes_to_resolve = filter_nodes_to_changed(resolvable, changed_files)

        if not nodes_to_resolve:
            context.cross_file_edges = reused_edges
            elapsed = time.time() - start_time
            context.metrics.update({
                "cross_file_rels_time_s": round(elapsed, 2),
                "cross_file_rels_edges": len(reused_edges),
                "cross_file_rels_preserved": len(reused_edges),
                "cross_file_rels_resolved": 0,
                "cross_file_rels_skipped": False,
            })
            if progress_cb:
                progress_cb("reused", f"all files unchanged, reused {len(reused_edges)} edges")
            return context

        if progress_cb:
            progress_cb("starting", f"{len(projects)} project(s), {len(nodes_to_resolve)} resolvable nodes")

        # --- Run SCIP indexers and extract edges ---
        known_ids = {n.node_id for n in context.nodes}
        fresh_edges: list[tuple[str, str, dict[str, Any]]] = []
        repo_root = str(getattr(context, "scan_root", Path.cwd().resolve()))
        cache_dir = Path(projects_config.scip_cache_dir if projects_config else ".fs2/scip")

        if not cache_dir.is_absolute():
            cache_dir = Path(repo_root) / cache_dir

        _ensure_cache_gitignore(cache_dir)

        from fs2.core.adapters.scip_adapter import create_scip_adapter

        for i, (language, project_path) in enumerate(projects):
            if progress_cb:
                progress_cb("progress", f"[{i + 1}/{len(projects)}] indexing {language} @ {project_path}")

            slug = _project_slug(project_path, language, repo_root)
            index_path = str(cache_dir / slug / "index.scip")

            success = run_scip_indexer(language, project_path, index_path)
            if not success:
                continue

            try:
                adapter = create_scip_adapter(language)
                # Compute path prefix: SCIP paths are project-relative,
                # but fs2 node IDs are repo-relative. Prepend the project
                # subdirectory so paths align.
                project_root_p = Path(project_path).resolve()
                repo_root_p = Path(repo_root).resolve()
                try:
                    prefix = project_root_p.relative_to(repo_root_p).as_posix()
                    path_prefix = f"{prefix}/" if prefix and prefix != "." else ""
                except ValueError:
                    path_prefix = ""

                project_edges = adapter.extract_cross_file_edges(
                    index_path, known_ids, path_prefix=path_prefix,
                )
                fresh_edges.extend(project_edges)
                logger.info("SCIP %s: %d edges from %s", language, len(project_edges), project_path)
            except Exception as e:
                logger.warning("SCIP adapter error for %s at %s: %s", language, project_path, e)
                continue

        # --- Merge, dedup, and report ---
        merged = reused_edges + fresh_edges
        seen: set[tuple[str, str]] = set()
        deduped: list[tuple[str, str, dict[str, Any]]] = []
        for src, tgt, data in merged:
            key = (src, tgt)
            if key not in seen:
                seen.add(key)
                deduped.append((src, tgt, data))
        context.cross_file_edges = deduped

        elapsed = time.time() - start_time
        context.metrics.update({
            "cross_file_rels_time_s": round(elapsed, 2),
            "cross_file_rels_edges": len(context.cross_file_edges),
            "cross_file_rels_preserved": len(reused_edges),
            "cross_file_rels_resolved": len(fresh_edges),
            "cross_file_rels_skipped": False,
        })

        if progress_cb:
            progress_cb(
                "complete",
                f"{len(context.cross_file_edges)} edges ({len(fresh_edges)} fresh + {len(reused_edges)} reused) in {elapsed:.1f}s",
            )

        return context

    def _resolve_projects(
        self, projects_config: Any, context: "PipelineContext"
    ) -> list[tuple[str, str]]:
        """Resolve project entries to (language, abs_project_path) pairs."""
        repo_root = str(getattr(context, "scan_root", Path.cwd().resolve()))
        result: list[tuple[str, str]] = []

        if projects_config and projects_config.entries:
            for entry in projects_config.entries:
                if not entry.enabled:
                    continue
                project_path = str((Path(repo_root) / entry.path).resolve())
                result.append((entry.type, project_path))
            return result

        # Auto-discover fallback (AC9)
        auto_discover = True
        if projects_config is not None:
            auto_discover = projects_config.auto_discover

        if auto_discover:
            from fs2.core.services.project_discovery import detect_project_roots

            discovered = detect_project_roots(repo_root)
            for dp in discovered:
                result.append((dp.language, dp.path))

        return result
