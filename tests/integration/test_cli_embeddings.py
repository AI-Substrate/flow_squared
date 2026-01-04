"""Integration tests for CLI embedding flags."""

import subprocess
import sys


class TestCLIEmbeddingsFlag:
    """Tests for --no-embeddings flag behavior."""

    def test_given_no_embeddings_flag_when_scan_then_skips_embedding_stage(
        self, tmp_path
    ):
        """
        Purpose: Verifies --no-embeddings skips embedding setup.
        Quality Contribution: Ensures embeddings are opt-out via CLI.
        Acceptance Criteria: Scan succeeds and reports embeddings skipped.
        """
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(f"""scan:
  scan_paths:
    - "{tmp_path}"
  respect_gitignore: true
""")

        (tmp_path / "test.py").write_text("def hello():\n    return 'world'")

        result = subprocess.run(
            [sys.executable, "-m", "fs2", "scan", "--no-embeddings"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={"NO_COLOR": "1", **dict(__import__("os").environ)},
        )

        assert result.returncode == 0, f"Scan failed: {result.stderr}"
        assert "embeddings" in result.stdout.lower()
        assert "skipped" in result.stdout.lower()
