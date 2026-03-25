#!/usr/bin/env python3
"""
Test multi-language Serena resolution against tests/fixtures/samples/.

This tests the project detection + multi-language resolution flow:
1. Detect project roots (marker files) in the samples area
2. Create Serena projects per detected root
3. Start Serena instances
4. Query find_referencing_symbols for symbols in each language
5. Report results

Usage:
    uv run python scripts/serena-explore/test_multi_lang.py
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from fnmatch import fnmatch
from pathlib import Path

from fastmcp import Client

SAMPLES_DIR = Path("tests/fixtures/samples")
BASE_PORT = 8370

# Project markers — if any of these exist in a directory, it's a project root
PROJECT_MARKERS: dict[str, list[str]] = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"],
    "typescript": ["package.json", "tsconfig.json"],
    "javascript": ["package.json"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "csharp": ["*.csproj", "*.sln"],
    "java": ["pom.xml", "build.gradle"],
}

# Language detection from file extension
EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "typescript",  # Serena uses typescript LS for JS too
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".java": "java",
    ".rb": "ruby",
    ".c": "cpp",  # Serena uses cpp for C
    ".cpp": "cpp",
    ".cu": "cuda",
}


def detect_project_roots(scan_root: Path) -> list[dict]:
    """Detect project roots by looking for marker files."""
    roots = []
    for dirpath, dirnames, filenames in os.walk(scan_root):
        languages = set()
        for lang, markers in PROJECT_MARKERS.items():
            for marker in markers:
                if any(fnmatch(f, marker) for f in filenames):
                    languages.add(lang)
        if languages:
            roots.append({
                "path": dirpath,
                "languages": sorted(languages),
                "marker_files": [f for f in filenames if any(
                    fnmatch(f, m) for markers in PROJECT_MARKERS.values() for m in markers
                )],
            })
    roots.sort(key=lambda r: r["path"].count(os.sep), reverse=True)
    return roots


def detect_languages_from_files(scan_root: Path) -> dict[str, list[str]]:
    """Group files by detected language."""
    by_lang: dict[str, list[str]] = {}
    for dirpath, _, filenames in os.walk(scan_root):
        for fname in filenames:
            ext = os.path.splitext(fname)[1]
            lang = EXT_TO_LANG.get(ext)
            if lang:
                fpath = os.path.join(dirpath, fname)
                by_lang.setdefault(lang, []).append(fpath)
    return by_lang


def create_serena_project(project_path: str, languages: list[str], name: str) -> bool:
    """Create a Serena project if not exists."""
    project_yml = Path(project_path) / ".serena" / "project.yml"
    if project_yml.exists():
        print(f"    Project already exists: {project_yml}")
        return True

    lang_args = []
    for lang in languages:
        lang_args.extend(["--language", lang])

    print(f"    Creating Serena project: {name} ({', '.join(languages)})")
    result = subprocess.run(
        ["serena", "project", "create", project_path,
         "--name", name, "--index", "--log-level", "ERROR"] + lang_args,
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"    ⚠ Project creation failed: {result.stderr[:200]}")
        return False
    print(f"    ✓ Project created")
    return True


def start_serena(project_path: str, port: int) -> subprocess.Popen:
    """Start a Serena instance."""
    proc = subprocess.Popen(
        ["serena-mcp-server",
         "--project", project_path,
         "--transport", "streamable-http",
         "--host", "127.0.0.1",
         "--port", str(port),
         "--open-web-dashboard", "false",
         "--enable-web-dashboard", "false",
         "--log-level", "ERROR"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return proc


def wait_for_ready(port: int, timeout: float = 30) -> bool:
    """Wait for Serena to respond."""
    import urllib.request
    import urllib.error
    start = time.monotonic()
    url = f"http://127.0.0.1:{port}/mcp/"
    while time.monotonic() - start < timeout:
        try:
            req = urllib.request.Request(url, method="POST", data=b"{}")
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=2)
            return True
        except urllib.error.HTTPError:
            return True  # Server is up, just rejecting our bad request
        except Exception:
            time.sleep(0.5)
    return False


def kill_serena_processes():
    """Kill all serena processes."""
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if "serena-mcp-server" in line and "grep" not in line:
            parts = line.split()
            if len(parts) > 1:
                try:
                    os.kill(int(parts[1]), signal.SIGTERM)
                except ProcessLookupError:
                    pass
    time.sleep(1)
    # Kill pyright children
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if ("pyright" in line or "langserver" in line) and "grep" not in line:
            parts = line.split()
            if len(parts) > 1:
                try:
                    os.kill(int(parts[1]), signal.SIGKILL)
                except ProcessLookupError:
                    pass


async def query_symbols(port: int, file_path: str, project_root: str) -> dict:
    """Query Serena for symbols and references in a file."""
    url = f"http://127.0.0.1:{port}/mcp/"
    rel_path = os.path.relpath(file_path, project_root)

    result_data = {"file": rel_path, "symbols": [], "references": [], "errors": []}

    try:
        async with Client(url) as client:
            # Get symbols overview
            r = await client.call_tool("get_symbols_overview", {
                "relative_path": rel_path,
                "depth": 2,
            })
            if hasattr(r, "content"):
                for item in r.content:
                    text = getattr(item, "text", "")
                    if text:
                        try:
                            symbols = json.loads(text)
                            result_data["symbols"] = symbols
                        except json.JSONDecodeError:
                            pass

            # Try to find references for first symbol found
            if result_data["symbols"]:
                # Extract first symbol name
                first_symbol = _extract_first_symbol(result_data["symbols"])
                if first_symbol:
                    r2 = await client.call_tool("find_referencing_symbols", {
                        "name_path": first_symbol,
                        "relative_path": rel_path,
                    })
                    if hasattr(r2, "content"):
                        for item in r2.content:
                            text = getattr(item, "text", "")
                            if text:
                                try:
                                    refs = json.loads(text)
                                    ref_count = sum(
                                        len(kind_refs)
                                        for file_refs in refs.values()
                                        for kind_refs in file_refs.values()
                                    )
                                    result_data["references"] = {
                                        "symbol": first_symbol,
                                        "count": ref_count,
                                    }
                                except json.JSONDecodeError:
                                    pass

    except Exception as e:
        result_data["errors"].append(str(e)[:100])

    return result_data


def _extract_first_symbol(symbols_data) -> str | None:
    """Extract the first symbol name from get_symbols_overview output."""
    if isinstance(symbols_data, dict):
        for kind, items in symbols_data.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, str):
                        return item
                    if isinstance(item, dict):
                        for name in item.keys():
                            return name
    return None


async def main():
    samples_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else SAMPLES_DIR
    samples_dir = samples_dir.resolve()

    print(f"═══ Multi-Language Serena Resolution Test ═══")
    print(f"Samples: {samples_dir}\n")

    # Phase 1: Detect
    print("Phase 1: Detecting project roots...")
    roots = detect_project_roots(samples_dir)
    if roots:
        print(f"  Found {len(roots)} project root(s):")
        for r in roots:
            print(f"    {r['path']} → {r['languages']} (markers: {r['marker_files']})")
    else:
        print("  No project markers found (expected for fixture samples)")

    print("\nPhase 1b: Detecting languages from file extensions...")
    by_lang = detect_languages_from_files(samples_dir)
    for lang, files in sorted(by_lang.items()):
        print(f"  {lang}: {len(files)} files")
        for f in files:
            print(f"    {os.path.relpath(f, samples_dir)}")

    # Phase 2: Create Serena project for the whole samples dir
    # Since there are no project markers, we'll create one project per language subdir
    print("\nPhase 2: Creating Serena projects...")

    # Strategy: create a project for each language that Serena supports
    serena_languages = {"python", "typescript", "go", "rust", "csharp", "java", "cpp", "ruby"}
    projects_to_test = []

    for lang, files in by_lang.items():
        if lang not in serena_languages:
            print(f"  Skipping {lang} (not supported by Serena)")
            continue

        # Find the directory containing these files
        lang_dir = os.path.dirname(files[0])
        name = f"samples-{lang}"
        ok = create_serena_project(lang_dir, [lang], name)
        if ok:
            projects_to_test.append({
                "name": name,
                "path": lang_dir,
                "language": lang,
                "files": files,
            })

    print(f"\n  {len(projects_to_test)} projects ready")

    # Phase 3: Test each project
    print("\nPhase 3: Testing resolution per language...")
    port = BASE_PORT
    all_results = []

    for project in projects_to_test:
        print(f"\n  ── {project['language'].upper()} ({project['name']}) ──")

        # Start Serena
        proc = start_serena(project["path"], port)
        print(f"    Starting Serena on port {port}...")

        if wait_for_ready(port):
            print(f"    ✓ Ready")

            # Query each file
            for fpath in project["files"]:
                t0 = time.monotonic()
                result = await query_symbols(port, fpath, project["path"])
                elapsed = time.monotonic() - t0

                sym_count = _count_symbols(result["symbols"])
                ref_info = result.get("references", {})
                errors = result.get("errors", [])

                status = "✓" if not errors else "✗"
                ref_str = f", refs={ref_info.get('count', 0)} for '{ref_info.get('symbol', '?')}'" if ref_info else ""
                err_str = f" ERROR: {errors[0]}" if errors else ""

                print(f"    {status} {os.path.basename(fpath)}: {sym_count} symbols{ref_str} ({elapsed*1000:.0f}ms){err_str}")

                all_results.append({
                    "language": project["language"],
                    "file": os.path.basename(fpath),
                    "symbols": sym_count,
                    "refs": ref_info.get("count", 0) if ref_info else 0,
                    "errors": len(errors),
                    "elapsed_ms": elapsed * 1000,
                })
        else:
            print(f"    ✗ Failed to start")
            all_results.append({
                "language": project["language"],
                "file": "*",
                "symbols": 0,
                "refs": 0,
                "errors": 1,
                "elapsed_ms": 0,
            })

        # Kill this instance
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(1)
        port += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Language':<12} {'File':<20} {'Symbols':>8} {'Refs':>6} {'Time':>8} {'Status'}")
    print(f"  {'-'*12} {'-'*20} {'-'*8} {'-'*6} {'-'*8} {'-'*6}")
    for r in all_results:
        status = "✓" if r["errors"] == 0 else "✗"
        print(f"  {r['language']:<12} {r['file']:<20} {r['symbols']:>8} {r['refs']:>6} {r['elapsed_ms']:>7.0f}ms {status}")

    # Cleanup
    print(f"\nCleaning up...")
    kill_serena_processes()
    print("Done.")


def _count_symbols(symbols_data) -> int:
    """Count total symbols in overview data."""
    if isinstance(symbols_data, dict):
        count = 0
        for kind, items in symbols_data.items():
            if isinstance(items, list):
                count += len(items)
        return count
    return 0


if __name__ == "__main__":
    asyncio.run(main())
