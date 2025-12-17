"""Tests for fs2 init CLI command.

Full TDD tests for the init command covering:
- T014a: Create .fs2/config.yaml with defaults
- T014c: Warn when config already exists
"""

from typer.testing import CliRunner

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
