"""Tests for fs2 docs CLI command.

Full TDD tests covering:
- AC-3: fs2 docs lists all documents grouped by category
- AC-4: fs2 docs <id> displays document content
- AC-5: fs2 docs <id> with unknown ID exits 1 with helpful error
- AC-6: fs2 docs --json outputs {"docs": [...], "count": N}
- AC-7: fs2 docs <id> --json outputs {id, title, content, metadata}
- AC-8: Command is unguarded (no require_init)
- AC-9: Category and tag filtering
"""

import json

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.slow
runner = CliRunner()


class TestDocsCommandRegistered:
    """AC-8: Command is unguarded and registered."""

    def test_given_app_when_inspected_then_docs_command_registered(self):
        """
        Purpose: Proves docs command is registered in the CLI app.
        Quality Contribution: Command must be discoverable.
        Acceptance Criteria: "docs" appears in registered command names.
        """
        from fs2.cli.main import app

        names = [c.name for c in app.registered_commands]
        assert "docs" in names

    def test_given_no_config_when_docs_invoked_then_exits_zero(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves docs works before fs2 init (unguarded).
        Quality Contribution: Agents can browse docs without init.
        Acceptance Criteria: AC-8 - exit code 0 with no .fs2/ directory.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs"])
        assert result.exit_code == 0


class TestDocsListMode:
    """AC-3: Lists all documents grouped by category."""

    def test_given_no_args_when_docs_then_lists_all_documents(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves listing mode shows all bundled documents.
        Quality Contribution: Agents can discover available docs.
        Acceptance Criteria: AC-3 - output contains known doc IDs.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs"])
        assert result.exit_code == 0
        # Should contain known doc IDs
        assert "agents" in result.output
        assert "configuration-guide" in result.output
        assert "mcp-server-guide" in result.output

    def test_given_no_args_when_docs_then_shows_categories(self, tmp_path, monkeypatch):
        """
        Purpose: Proves listing mode groups docs by category.
        Quality Contribution: Organized output helps agents find relevant docs.
        Acceptance Criteria: AC-3 - output shows category grouping.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "how-to" in output_lower or "how to" in output_lower
        assert "reference" in output_lower

    def test_given_no_args_when_docs_then_shows_usage_hint(self, tmp_path, monkeypatch):
        """
        Purpose: Proves listing mode shows how to read a specific doc.
        Quality Contribution: Agents know what to do next.
        Acceptance Criteria: AC-3 - usage hint in output.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs"])
        assert result.exit_code == 0
        assert "fs2 docs" in result.output


class TestDocsReadMode:
    """AC-4, AC-5: Read specific document or show error."""

    def test_given_valid_id_when_docs_then_shows_content(self, tmp_path, monkeypatch):
        """
        Purpose: Proves reading a known doc ID shows its content.
        Quality Contribution: Agents can read documentation.
        Acceptance Criteria: AC-4 - fs2 docs agents displays content.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs", "agents"])
        assert result.exit_code == 0
        # agents.md contains agent-related content
        assert "agent" in result.output.lower()

    def test_given_invalid_id_when_docs_then_exits_one(self, tmp_path, monkeypatch):
        """
        Purpose: Proves unknown doc ID exits with error code.
        Quality Contribution: Agents get clear error signal.
        Acceptance Criteria: AC-5 - exit code 1 for nonexistent ID.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs", "nonexistent"])
        assert result.exit_code == 1

    def test_given_invalid_id_when_docs_then_shows_available_ids(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves error message lists available doc IDs.
        Quality Contribution: Agents know which IDs are valid.
        Acceptance Criteria: AC-5 - error lists available IDs.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs", "nonexistent"])
        assert result.exit_code == 1
        # Should mention at least one valid ID
        assert "agents" in result.output


class TestDocsJsonMode:
    """AC-6, AC-7: JSON output mirrors MCP format."""

    def test_given_json_flag_when_list_then_valid_json(self, tmp_path, monkeypatch):
        """
        Purpose: Proves JSON list mode outputs valid JSON.
        Quality Contribution: Agents can parse structured output.
        Acceptance Criteria: AC-6 - valid JSON with docs and count.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["docs", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "docs" in data
        assert "count" in data
        assert isinstance(data["docs"], list)
        assert data["count"] > 0

    def test_given_json_flag_when_list_then_docs_have_expected_fields(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves JSON list entries have metadata fields.
        Quality Contribution: JSON matches MCP docs_list format.
        Acceptance Criteria: AC-6 - each doc has id, title, summary, category, tags.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["docs", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for doc in data["docs"]:
            assert "id" in doc
            assert "title" in doc
            assert "summary" in doc
            assert "category" in doc
            assert "tags" in doc

    def test_given_json_flag_when_read_then_valid_json(self, tmp_path, monkeypatch):
        """
        Purpose: Proves JSON read mode outputs valid JSON for a single doc.
        Quality Contribution: Agents can parse doc content programmatically.
        Acceptance Criteria: AC-7 - valid JSON with id, content, metadata.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["docs", "agents", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "agents"
        assert "content" in data
        assert "metadata" in data
        assert len(data["content"]) > 0

    def test_given_json_flag_when_read_then_metadata_has_fields(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves JSON read mode metadata matches MCP docs_get format.
        Quality Contribution: Format parity between CLI and MCP.
        Acceptance Criteria: AC-7 - metadata has title, category, tags.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["docs", "agents", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        metadata = data["metadata"]
        assert "title" in metadata
        assert "category" in metadata
        assert "tags" in metadata


class TestDocsFiltering:
    """AC-9: Category and tag filtering."""

    def test_given_category_flag_when_docs_then_filters_by_category(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves --category filters documents.
        Quality Contribution: Agents can narrow doc search.
        Acceptance Criteria: AC-9 - only reference docs shown.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs", "--category", "reference"])
        assert result.exit_code == 0
        # configuration-guide is category=reference
        assert "configuration-guide" in result.output

    def test_given_category_flag_when_docs_json_then_all_match_category(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves JSON category filter only includes matching docs.
        Quality Contribution: Structured filtering works correctly.
        Acceptance Criteria: AC-9 - all returned docs match category.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["docs", "--category", "reference", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] > 0
        for doc in data["docs"]:
            assert doc["category"] == "reference"

    def test_given_tags_flag_when_docs_then_filters_by_tag(self, tmp_path, monkeypatch):
        """
        Purpose: Proves --tags filters documents.
        Quality Contribution: Agents can search by topic.
        Acceptance Criteria: AC-9 - tag filtering works.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs", "--tags", "config"])
        assert result.exit_code == 0
        # configuration-guide has tag "config"
        assert "configuration" in result.output

    def test_given_tags_flag_when_docs_json_then_all_match_tag(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves JSON tag filter returns matching docs.
        Quality Contribution: Structured tag filtering works.
        Acceptance Criteria: AC-9 - all returned docs have the tag.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["docs", "--tags", "config", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] > 0
        for doc in data["docs"]:
            assert "config" in doc["tags"]
