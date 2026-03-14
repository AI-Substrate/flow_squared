"""Tests for fs2 init CLI command.

Full TDD tests for the init command covering:
- T014a: Create .fs2/config.yaml with defaults
- T014c: Warn when config already exists
- T015: Enhanced init tests (local + global, .git warning, .gitignore)
"""

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.slow

runner = CliRunner()


class TestInitCommand:
    """T014a-T014b: Tests for fs2 init command."""

    def test_given_init_when_run_then_creates_config_dir(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies init creates .fs2 directory.
        Quality Contribution: Ensures bootstrap works.
        Acceptance Criteria: .fs2/ directory exists after init.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"
        assert (tmp_path / ".fs2").exists()

    def test_given_init_when_run_then_creates_config_file(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies init creates config.yaml.
        Quality Contribution: Ensures config file is bootstrapped.
        Acceptance Criteria: .fs2/config.yaml exists after init.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"
        config_file = tmp_path / ".fs2" / "config.yaml"
        assert config_file.exists()

    def test_given_init_when_run_then_config_has_defaults(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies config has sensible defaults.
        Quality Contribution: Ensures zero-config scanning works.
        Acceptance Criteria: Config contains scan_paths and respect_gitignore.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        config_file = tmp_path / ".fs2" / "config.yaml"
        content = config_file.read_text()

        assert "scan_paths" in content
        assert "respect_gitignore" in content

    def test_given_init_when_run_then_shows_success_message(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies init shows success message.
        Quality Contribution: Confirms operation to user.
        Acceptance Criteria: Output mentions created.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        stdout_lower = result.stdout.lower()
        assert "created" in stdout_lower or "initialized" in stdout_lower


class TestInitWhenConfigExists:
    """T014c: Tests for init when config already exists."""

    def test_given_existing_config_when_init_then_warns(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies init warns when config exists.
        Quality Contribution: Prevents accidental overwrite.
        Acceptance Criteria: Warning shown, file not overwritten.
        """
        from fs2.cli.main import app

        # Create existing config
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        original_content = "# Original config\nscan:\n  scan_paths: [./original]\n"
        config_file.write_text(original_content)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["init"])

        # Should succeed but warn
        assert result.exit_code == 0
        # Should mention exists/already
        stdout_lower = result.stdout.lower()
        assert "exists" in stdout_lower or "already" in stdout_lower

        # File should NOT be overwritten
        assert config_file.read_text() == original_content

    def test_given_existing_config_when_init_force_then_overwrites(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies --force overwrites existing config.
        Quality Contribution: Allows intentional recreation.
        Acceptance Criteria: File overwritten with --force.
        """
        from fs2.cli.main import app

        # Create existing config
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        original_content = "# Original config\n"
        config_file.write_text(original_content)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["init", "--force"])

        assert result.exit_code == 0
        # File should be overwritten
        new_content = config_file.read_text()
        assert new_content != original_content
        assert "scan_paths" in new_content


class TestMissingConfigError:
    """T013-T014: Tests for missing config error message."""

    def test_given_no_config_when_scan_then_suggests_init(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies helpful error when config missing.
        Quality Contribution: Guides users to run init.
        Acceptance Criteria: Error mentions 'fs2 init'.
        """
        from fs2.cli.main import app

        # No .fs2 directory
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        # Should fail with exit code 1
        assert result.exit_code == 1
        # Should mention init command
        stdout_lower = result.stdout.lower()
        assert "init" in stdout_lower, f"Expected 'init' in: {result.stdout}"


# =============================================================================
# T015: ENHANCED INIT TESTS
# =============================================================================


class TestEnhancedInitLocalAndGlobal:
    """T015: Tests for enhanced init (local + global)."""

    def test_given_init_when_run_then_creates_local_config(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies init creates local .fs2/config.yaml.
        Quality Contribution: Ensures local config works.
        Acceptance Criteria: AC-14 - Creates local .fs2/.
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"
        assert (project_dir / ".fs2" / "config.yaml").exists()

    def test_given_init_when_run_then_creates_global_config(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies init creates global config too.
        Quality Contribution: Ensures user-level config exists.
        Acceptance Criteria: AC-14 - Creates global ~/.config/fs2/.
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"
        global_config = fake_home / ".config" / "fs2" / "config.yaml"
        assert global_config.exists()

    def test_given_global_exists_when_init_then_skips_global(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies init skips existing global config.
        Quality Contribution: Doesn't overwrite user config.
        Acceptance Criteria: AC-15 - Skips global if exists.
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        global_dir = fake_home / ".config" / "fs2"
        global_dir.mkdir(parents=True)
        global_config = global_dir / "config.yaml"
        original_content = "# Original global config\n"
        global_config.write_text(original_content)

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        # Global should NOT be overwritten
        assert global_config.read_text() == original_content
        # Should mention skipped
        assert (
            "skipped" in result.stdout.lower()
            or "already exists" in result.stdout.lower()
        )

    def test_given_init_when_run_then_shows_cwd(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies init displays current directory.
        Quality Contribution: User knows where config is created.
        Acceptance Criteria: AC-20 - Shows current directory path.
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        # Should show current directory
        assert str(project_dir) in result.stdout or "project" in result.stdout

    def test_given_no_git_when_init_then_shows_warning(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies init warns when no .git folder.
        Quality Contribution: Helps identify wrong directory.
        Acceptance Criteria: AC-21 - Shows red warning if no .git.
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        # No .git directory

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0  # Warning, not failure
        stdout_lower = result.stdout.lower()
        assert ".git" in stdout_lower or "git" in stdout_lower

    def test_given_git_exists_when_init_then_no_git_warning(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies no .git warning when .git exists.
        Quality Contribution: No noise when in correct directory.
        Acceptance Criteria: AC-21 - No warning when .git present.
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()  # Git directory exists

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        # Should NOT contain .git warning
        stdout_lower = result.stdout.lower()
        assert "warning" not in stdout_lower or ".git" not in stdout_lower

    def test_given_init_when_run_then_creates_gitignore(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies init creates .fs2/.gitignore.
        Quality Contribution: Secrets excluded from git.
        Acceptance Criteria: AC-22 - Creates .fs2/.gitignore.
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        gitignore = project_dir / ".fs2" / ".gitignore"
        assert gitignore.exists()

    def test_given_init_when_run_then_gitignore_keeps_config_yaml(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies .gitignore ignores all except config.yaml.
        Quality Contribution: Config tracked, secrets ignored.
        Acceptance Criteria: AC-22 - .gitignore ignores all except config.yaml.
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        gitignore = project_dir / ".fs2" / ".gitignore"
        content = gitignore.read_text()
        # Should ignore everything
        assert "*" in content
        # Should NOT ignore config.yaml
        assert "!config.yaml" in content

    def test_given_init_when_run_then_reports_actions(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies init reports what was created.
        Quality Contribution: User knows what happened.
        Acceptance Criteria: AC-18 - Reports created/skipped.
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        stdout_lower = result.stdout.lower()
        # Should report both local and global
        assert "local" in stdout_lower or ".fs2" in stdout_lower
        assert "global" in stdout_lower or ".config" in stdout_lower

    def test_given_git_worktree_when_init_then_no_git_warning(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies .git file (worktree) doesn't trigger warning.
        Quality Contribution: Supports git worktrees.
        Acceptance Criteria: AC-21 - Uses .exists() not .is_dir().
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        # Git worktree has .git as a file, not directory
        (project_dir / ".git").write_text("gitdir: /some/other/path")

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        # Should NOT contain .git warning (worktree is valid)
        stdout_lower = result.stdout.lower()
        # Check for absence of warning about .git specifically
        assert not ("no .git" in stdout_lower and "warning" in stdout_lower)


# =============================================================================
# CONFIG TEMPLATE CONTENT TESTS (Plan 025)
# =============================================================================


class TestDefaultConfigTemplate:
    """Tests for DEFAULT_CONFIG template content (AC1-AC6)."""

    def test_given_default_config_when_checked_then_contains_azure_key_llm_example(
        self,
    ):
        """
        Purpose: Proves template has Azure API key LLM example.
        Quality Contribution: New users see Azure key-based auth path.
        Acceptance Criteria: AC1 — commented section includes provider: azure + api_key.
        """
        from fs2.cli.init import DEFAULT_CONFIG

        assert "# llm:" in DEFAULT_CONFIG
        assert "#   provider: azure" in DEFAULT_CONFIG
        assert "#   api_key: ${AZURE_OPENAI_API_KEY}" in DEFAULT_CONFIG

    def test_given_default_config_when_checked_then_contains_azure_ad_llm_example(
        self,
    ):
        """
        Purpose: Proves template has Azure AD (az login) LLM example.
        Quality Contribution: Keyless auth shown as first-class option.
        Acceptance Criteria: AC3 — Azure AD section present with install instructions.
        """
        from fs2.cli.init import DEFAULT_CONFIG

        assert "az login" in DEFAULT_CONFIG
        assert "pip install fs2[azure-ad]" in DEFAULT_CONFIG

    def test_given_default_config_when_checked_then_contains_openai_llm_example(self):
        """
        Purpose: Proves template has OpenAI LLM example.
        Quality Contribution: OpenAI users can configure quickly.
        Acceptance Criteria: AC1 — OpenAI provider section with API key placeholder.
        """
        from fs2.cli.init import DEFAULT_CONFIG

        assert "#   provider: openai" in DEFAULT_CONFIG
        assert "#   api_key: ${OPENAI_API_KEY}" in DEFAULT_CONFIG

    def test_given_default_config_when_checked_then_contains_embedding_examples(self):
        """
        Purpose: Proves template has embedding configuration examples.
        Quality Contribution: Users see how to enable semantic search.
        Acceptance Criteria: AC2 — Azure and OpenAI-compatible embedding sections present.
        """
        from fs2.cli.init import DEFAULT_CONFIG

        assert "# embedding:" in DEFAULT_CONFIG
        assert "#   mode: azure" in DEFAULT_CONFIG
        assert "#   mode: openai_compatible" in DEFAULT_CONFIG

    def test_given_default_config_when_checked_then_api_versions_are_quoted(self):
        """
        Purpose: Proves all api_version values are quoted strings.
        Quality Contribution: Prevents YAML date-parsing gotcha.
        Acceptance Criteria: AC4 — api_version lines use quoted values.
        """
        from fs2.cli.init import DEFAULT_CONFIG

        for line in DEFAULT_CONFIG.splitlines():
            stripped = line.lstrip("# ").strip()
            if "api_version" in stripped and ":" in stripped:
                value = stripped.split(":", 1)[1].strip()
                assert value.startswith('"') and value.endswith('"'), (
                    f"api_version not quoted: {line.strip()}"
                )

    def test_given_default_config_when_scan_section_parsed_then_valid_yaml_with_defaults(
        self,
    ):
        """
        Purpose: Proves active scan section is valid YAML with expected defaults.
        Quality Contribution: Config won't fail on first use.
        Acceptance Criteria: AC6 — scan section parses and has same defaults as before.
        """
        import yaml

        from fs2.cli.init import DEFAULT_CONFIG

        parsed = yaml.safe_load(DEFAULT_CONFIG)
        assert parsed is not None
        assert "scan" in parsed
        assert parsed["scan"]["scan_paths"] == ["."]
        assert parsed["scan"]["respect_gitignore"] is True
        assert parsed["scan"]["max_file_size_kb"] == 500
        assert parsed["scan"]["follow_symlinks"] is False


class TestInitCrossFileRelsGuidance:
    """DYK-P3-05: DEFAULT_CONFIG includes cross-file rels guidance."""

    def test_default_config_mentions_serena(self):
        """Config template mentions Serena installation."""
        from fs2.cli.init import DEFAULT_CONFIG

        assert "serena" in DEFAULT_CONFIG.lower()

    def test_default_config_mentions_serena_gitignore(self):
        """Config template warns about .serena/ gitignore."""
        from fs2.cli.init import DEFAULT_CONFIG

        assert ".serena/" in DEFAULT_CONFIG

    def test_default_config_mentions_cross_file_rels(self):
        """Config template shows cross_file_rels section."""
        from fs2.cli.init import DEFAULT_CONFIG

        assert "cross_file_rels" in DEFAULT_CONFIG
