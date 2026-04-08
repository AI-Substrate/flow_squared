"""Tests for ProjectConfig and ProjectsConfig pydantic models.

Validates type alias normalisation, field defaults, required fields,
'entries' field name (not 'projects'), and YAML_CONFIG_TYPES registry.
"""

import pytest
from pydantic import ValidationError

from fs2.config.objects import (
    YAML_CONFIG_TYPES,
    ProjectConfig,
    ProjectsConfig,
)


class TestProjectConfigDefaults:
    """Test default values for ProjectConfig."""

    def test_path_defaults_to_dot(self):
        config = ProjectConfig(type="python")
        assert config.path == "."

    def test_enabled_defaults_to_true(self):
        config = ProjectConfig(type="python")
        assert config.enabled is True

    def test_options_defaults_to_empty(self):
        config = ProjectConfig(type="python")
        assert config.options == {}

    def test_project_file_defaults_to_none(self):
        config = ProjectConfig(type="python")
        assert config.project_file is None


class TestProjectConfigTypeNormalisation:
    """Test type alias normalisation."""

    def test_ts_normalises_to_typescript(self):
        assert ProjectConfig(type="ts").type == "typescript"

    def test_js_normalises_to_javascript(self):
        assert ProjectConfig(type="js").type == "javascript"

    def test_cs_normalises_to_dotnet(self):
        assert ProjectConfig(type="cs").type == "dotnet"

    def test_csharp_normalises_to_dotnet(self):
        assert ProjectConfig(type="csharp").type == "dotnet"

    def test_c_sharp_normalises_to_dotnet(self):
        assert ProjectConfig(type="c#").type == "dotnet"

    def test_python_stays_python(self):
        assert ProjectConfig(type="python").type == "python"

    def test_go_stays_go(self):
        assert ProjectConfig(type="go").type == "go"

    def test_case_insensitive(self):
        assert ProjectConfig(type="Python").type == "python"
        assert ProjectConfig(type="TS").type == "typescript"

    def test_strips_whitespace(self):
        assert ProjectConfig(type=" python ").type == "python"

    def test_unknown_type_rejected(self):
        with pytest.raises(ValidationError, match="Unknown project type"):
            ProjectConfig(type="cobol")


class TestProjectConfigCustomValues:
    """Test creating config with custom values."""

    def test_all_fields(self):
        config = ProjectConfig(
            type="typescript",
            path="frontend",
            project_file="tsconfig.json",
            enabled=True,
            options={"strict": "true"},
        )
        assert config.type == "typescript"
        assert config.path == "frontend"
        assert config.project_file == "tsconfig.json"
        assert config.options == {"strict": "true"}


class TestProjectsConfigDefaults:
    """Test default values for ProjectsConfig."""

    def test_entries_defaults_to_empty(self):
        config = ProjectsConfig()
        assert config.entries == []

    def test_auto_discover_defaults_to_true(self):
        config = ProjectsConfig()
        assert config.auto_discover is True

    def test_scip_cache_dir_defaults(self):
        config = ProjectsConfig()
        assert config.scip_cache_dir == ".fs2/scip"


class TestProjectsConfigPath:
    """Test __config_path__ for YAML/env loading."""

    def test_config_path_is_projects(self):
        assert ProjectsConfig.__config_path__ == "projects"


class TestProjectsConfigRegistry:
    """Test YAML_CONFIG_TYPES registry membership."""

    def test_in_yaml_config_types(self):
        assert ProjectsConfig in YAML_CONFIG_TYPES


class TestProjectsConfigWithEntries:
    """Test ProjectsConfig with nested entries."""

    def test_entries_with_multiple_projects(self):
        config = ProjectsConfig(
            entries=[
                ProjectConfig(type="python", path="."),
                ProjectConfig(type="ts", path="frontend"),
            ]
        )
        assert len(config.entries) == 2
        assert config.entries[0].type == "python"
        assert config.entries[1].type == "typescript"  # normalised

    def test_entries_field_name_is_entries(self):
        """The field is 'entries' not 'projects' (avoids YAML stutter)."""
        fields = set(ProjectsConfig.model_fields.keys())
        assert "entries" in fields
        assert "projects" not in fields
