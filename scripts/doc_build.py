#!/usr/bin/env python3
"""Build bundled documentation for MCP server.

Copies all markdown files and registry.yaml from docs/how/user/ to src/fs2/docs/.
The registry.yaml in docs/how/user/ is the source of truth.

Usage:
    python scripts/doc_build.py
    just doc-build
"""

import shutil
import sys
from pathlib import Path


def main() -> int:
    """Copy user docs to bundled package location."""
    # Resolve paths relative to script location
    repo_root = Path(__file__).parent.parent
    source_dir = repo_root / "docs" / "how" / "user"
    target_dir = repo_root / "src" / "fs2" / "docs"

    if not source_dir.exists():
        print(f"ERROR: Source directory not found: {source_dir}", file=sys.stderr)
        return 1

    # Ensure target exists
    target_dir.mkdir(parents=True, exist_ok=True)

    # Clean target directory (remove old .md and .yaml files, preserve __init__.py)
    for old_file in target_dir.glob("*.md"):
        old_file.unlink()
    for old_file in target_dir.glob("*.yaml"):
        old_file.unlink()
    for old_dir in target_dir.iterdir():
        if old_dir.is_dir() and old_dir.name != "__pycache__":
            shutil.rmtree(old_dir)

    # Track what we copy
    copied_files = []
    copied_dirs = []

    # Copy registry.yaml first
    registry_src = source_dir / "registry.yaml"
    if registry_src.exists():
        shutil.copy2(registry_src, target_dir / "registry.yaml")
        copied_files.append("registry.yaml")
    else:
        print(f"WARNING: No registry.yaml found in {source_dir}", file=sys.stderr)

    # Copy all .md files (top-level)
    for md_file in source_dir.glob("*.md"):
        # Normalize AGENTS.md -> agents.md for consistency
        target_name = md_file.name.lower() if md_file.name == "AGENTS.md" else md_file.name
        shutil.copy2(md_file, target_dir / target_name)
        copied_files.append(f"{md_file.name} -> {target_name}")

    # Copy subdirectories (like embeddings/)
    for subdir in source_dir.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            target_subdir = target_dir / subdir.name
            if target_subdir.exists():
                shutil.rmtree(target_subdir)
            shutil.copytree(subdir, target_subdir)
            copied_dirs.append(subdir.name)

    # Report
    print(f"Copied {len(copied_files)} files and {len(copied_dirs)} directories to {target_dir}")
    for f in copied_files:
        print(f"  - {f}")
    for d in copied_dirs:
        print(f"  - {d}/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
