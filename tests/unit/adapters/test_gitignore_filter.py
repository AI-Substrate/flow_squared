"""Tests for GitignoreFilter.

Task: T009
Purpose: Verify GitignoreFilter correctly filters files based on .gitignore and additional patterns.
Per Finding 09: Gitignore Reuse via pathspec library.
"""

from pathlib import Path

import pytest
from watchfiles import Change


@pytest.mark.unit
class TestGitignoreFilter:
    """Tests for GitignoreFilter (T009).

    GitignoreFilter extends watchfiles.DefaultFilter to:
    - Load and respect .gitignore patterns from a directory
    - Apply additional_ignores patterns from WatchConfig
    - Return False for paths that should be ignored (watchfiles convention)
    """

    def test_gitignore_filter_ignores_pyc_files_from_gitignore(self, tmp_path: Path):
        """
        Given: A directory with .gitignore containing *.pyc
        When: Filtering a .pyc file
        Then: Returns False (ignored)

        Purpose: Verifies .gitignore patterns are respected.
        Quality Contribution: Core gitignore functionality.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import GitignoreFilter

        # Create .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")

        # Create a .pyc file
        pyc_file = tmp_path / "test.pyc"
        pyc_file.write_text("")

        filter_ = GitignoreFilter(root_path=tmp_path)

        # False means "don't include" (ignored) in watchfiles convention
        assert filter_(Change.modified, str(pyc_file)) is False

    def test_gitignore_filter_allows_python_files(self, tmp_path: Path):
        """
        Given: A directory with .gitignore containing *.pyc
        When: Filtering a .py file
        Then: Returns True (not ignored)

        Purpose: Verifies non-ignored files pass through.
        Quality Contribution: Filter doesn't over-exclude.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import GitignoreFilter

        # Create .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")

        # Create a .py file
        py_file = tmp_path / "test.py"
        py_file.write_text("")

        filter_ = GitignoreFilter(root_path=tmp_path)

        # True means "include" (not ignored) in watchfiles convention
        assert filter_(Change.modified, str(py_file)) is True

    def test_gitignore_filter_ignores_pycache_directory(self, tmp_path: Path):
        """
        Given: A directory with .gitignore containing __pycache__/
        When: Filtering a file inside __pycache__
        Then: Returns False (ignored)

        Purpose: Verifies directory patterns work.
        Quality Contribution: Common Python gitignore pattern.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import GitignoreFilter

        # Create .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("__pycache__/\n")

        # Create __pycache__ directory and file
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        cached_file = pycache / "module.cpython-312.pyc"
        cached_file.write_text("")

        filter_ = GitignoreFilter(root_path=tmp_path)

        assert filter_(Change.modified, str(cached_file)) is False

    def test_gitignore_filter_respects_additional_ignores(self, tmp_path: Path):
        """
        Given: Additional ignore patterns ["*.tmp", ".cache/"]
        When: Filtering matching files
        Then: Returns False (ignored)

        Purpose: Verifies additional_ignores from WatchConfig work.
        Quality Contribution: Config-driven exclusions.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import GitignoreFilter

        # Create files
        tmp_file = tmp_path / "test.tmp"
        tmp_file.write_text("")

        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "data.json"
        cache_file.write_text("")

        filter_ = GitignoreFilter(
            root_path=tmp_path, additional_ignores=["*.tmp", ".cache/"]
        )

        assert filter_(Change.modified, str(tmp_file)) is False
        assert filter_(Change.modified, str(cache_file)) is False

    def test_gitignore_filter_combines_gitignore_and_additional(self, tmp_path: Path):
        """
        Given: Both .gitignore and additional_ignores patterns
        When: Filtering files matching either
        Then: Both are ignored

        Purpose: Verifies patterns combine correctly.
        Quality Contribution: Layered exclusion patterns.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import GitignoreFilter

        # Create .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")

        # Create files
        pyc_file = tmp_path / "test.pyc"
        pyc_file.write_text("")
        tmp_file = tmp_path / "test.tmp"
        tmp_file.write_text("")
        py_file = tmp_path / "test.py"
        py_file.write_text("")

        filter_ = GitignoreFilter(root_path=tmp_path, additional_ignores=["*.tmp"])

        assert filter_(Change.modified, str(pyc_file)) is False  # gitignore
        assert filter_(Change.modified, str(tmp_file)) is False  # additional
        assert filter_(Change.modified, str(py_file)) is True  # neither

    def test_gitignore_filter_handles_missing_gitignore(self, tmp_path: Path):
        """
        Given: A directory without .gitignore
        When: Creating GitignoreFilter
        Then: Filter works with additional_ignores only

        Purpose: Verifies graceful handling of missing .gitignore.
        Quality Contribution: Robustness for projects without gitignore.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import GitignoreFilter

        # No .gitignore created
        tmp_file = tmp_path / "test.tmp"
        tmp_file.write_text("")
        py_file = tmp_path / "test.py"
        py_file.write_text("")

        filter_ = GitignoreFilter(root_path=tmp_path, additional_ignores=["*.tmp"])

        assert filter_(Change.modified, str(tmp_file)) is False
        assert filter_(Change.modified, str(py_file)) is True

    def test_gitignore_filter_handles_nested_gitignore(self, tmp_path: Path):
        """
        Given: Nested directories with their own .gitignore
        When: Filtering files in subdirectories
        Then: Root .gitignore patterns apply throughout

        Purpose: Verifies root gitignore applies recursively.
        Quality Contribution: Correct handling of project structure.

        Note: For simplicity, we only load root .gitignore, not nested ones.
        This is the common fs2 pattern (per FileSystemScanner).
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import GitignoreFilter

        # Create root .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n*.log\n")

        # Create nested structure
        subdir = tmp_path / "src"
        subdir.mkdir()
        pyc_in_subdir = subdir / "test.pyc"
        pyc_in_subdir.write_text("")
        py_in_subdir = subdir / "test.py"
        py_in_subdir.write_text("")

        filter_ = GitignoreFilter(root_path=tmp_path)

        assert filter_(Change.modified, str(pyc_in_subdir)) is False
        assert filter_(Change.modified, str(py_in_subdir)) is True

    def test_gitignore_filter_change_types(self, tmp_path: Path):
        """
        Given: GitignoreFilter with patterns
        When: Filtering different change types (added, modified, deleted)
        Then: All change types are filtered the same way

        Purpose: Verifies filter applies to all change types.
        Quality Contribution: Consistent filtering across events.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import GitignoreFilter

        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")

        pyc_file = tmp_path / "test.pyc"
        pyc_file.write_text("")

        filter_ = GitignoreFilter(root_path=tmp_path)

        assert filter_(Change.added, str(pyc_file)) is False
        assert filter_(Change.modified, str(pyc_file)) is False
        assert filter_(Change.deleted, str(pyc_file)) is False

    def test_gitignore_filter_empty_additional_ignores(self, tmp_path: Path):
        """
        Given: Empty additional_ignores list
        When: Creating GitignoreFilter
        Then: Only .gitignore patterns apply

        Purpose: Verifies empty list is handled correctly.
        Quality Contribution: Edge case handling.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import GitignoreFilter

        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")

        pyc_file = tmp_path / "test.pyc"
        pyc_file.write_text("")

        filter_ = GitignoreFilter(root_path=tmp_path, additional_ignores=[])

        assert filter_(Change.modified, str(pyc_file)) is False
