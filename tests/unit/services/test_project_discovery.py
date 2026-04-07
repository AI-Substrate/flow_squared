"""Tests for project_discovery module.

Validates marker detection, skip dirs, no child dedup,
extended markers (C#, Ruby), and one entry per (path, language).
"""

from fs2.core.services.project_discovery import (
    PROJECT_MARKERS,
    detect_project_roots,
)


class TestDetectProjectRoots:
    """Core detection tests."""

    def test_detects_python(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[build-system]")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "python"
        assert roots[0].marker_file == "pyproject.toml"

    def test_detects_typescript(self, tmp_path):
        (tmp_path / "tsconfig.json").write_text("{}")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "typescript"

    def test_detects_go(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/test")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "go"

    def test_detects_csharp_csproj(self, tmp_path):
        (tmp_path / "MyApp.csproj").write_text("<Project/>")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "dotnet"

    def test_detects_csharp_sln(self, tmp_path):
        (tmp_path / "MyApp.sln").write_text("Microsoft Visual Studio Solution File")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "dotnet"

    def test_detects_ruby(self, tmp_path):
        (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "ruby"

    def test_detects_rust(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"')
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "rust"

    def test_detects_java_maven(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project/>")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 1
        assert roots[0].language == "java"

    def test_empty_when_no_markers(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        assert detect_project_roots(str(tmp_path)) == []


class TestNoChildDedup:
    """Nested projects are preserved (no child dedup)."""

    def test_nested_projects_kept(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[build-system]")
        sub = tmp_path / "packages" / "sub"
        sub.mkdir(parents=True)
        (sub / "package.json").write_text("{}")
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 2

    def test_deeply_nested_all_kept(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[build-system]")
        sub1 = tmp_path / "a"
        sub1.mkdir()
        (sub1 / "go.mod").write_text("module a")
        sub2 = tmp_path / "a" / "b"
        sub2.mkdir()
        (sub2 / "Cargo.toml").write_text('[package]\nname = "b"')
        roots = detect_project_roots(str(tmp_path))
        assert len(roots) == 3


class TestOneEntryPerLanguage:
    """Multi-language roots produce separate entries."""

    def test_multi_lang_separate_entries(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[build-system]")
        (tmp_path / "package.json").write_text("{}")
        roots = detect_project_roots(str(tmp_path))
        languages = {r.language for r in roots}
        assert languages == {"python", "javascript"}
        assert len(roots) == 2

    def test_dedup_same_path_same_language(self, tmp_path):
        """Multiple markers for same language → one entry."""
        (tmp_path / "pyproject.toml").write_text("[build-system]")
        (tmp_path / "setup.py").write_text("from setuptools import setup")
        roots = detect_project_roots(str(tmp_path))
        python_roots = [r for r in roots if r.language == "python"]
        assert len(python_roots) == 1


class TestSkipDirs:
    """Vendored/dependency directories are skipped."""

    def test_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "package.json").write_text("{}")
        assert detect_project_roots(str(tmp_path)) == []

    def test_skips_venv(self, tmp_path):
        venv = tmp_path / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "pyproject.toml").write_text("[build-system]")
        assert detect_project_roots(str(tmp_path)) == []

    def test_skips_obj(self, tmp_path):
        obj = tmp_path / "obj" / "Debug"
        obj.mkdir(parents=True)
        (obj / "MyApp.csproj").write_text("<Project/>")
        assert detect_project_roots(str(tmp_path)) == []

    def test_skips_build(self, tmp_path):
        build = tmp_path / "build"
        build.mkdir()
        (build / "package.json").write_text("{}")
        assert detect_project_roots(str(tmp_path)) == []


class TestProjectMarkers:
    """Verify marker registry completeness."""

    def test_has_required_languages(self):
        required = {
            "python",
            "typescript",
            "javascript",
            "go",
            "rust",
            "java",
            "dotnet",
            "ruby",
        }
        assert required.issubset(set(PROJECT_MARKERS.keys()))

    def test_dotnet_has_csproj_and_sln(self):
        markers = PROJECT_MARKERS["dotnet"]
        assert any(".csproj" in m for m in markers)
        assert any(".sln" in m for m in markers)

    def test_ruby_has_gemfile(self):
        assert "Gemfile" in PROJECT_MARKERS["ruby"]
