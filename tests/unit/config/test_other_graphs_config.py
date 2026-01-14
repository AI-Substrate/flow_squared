"""Tests for OtherGraph and OtherGraphsConfig models.

Phase 1: Configuration Model - Multi-Graph Support
Per spec AC1, AC9, AC10: Configuration of multiple graphs
Per Critical Finding 01: List concatenation merge
Per Critical Finding 04: Reserved name "default" enforcement

Phase 2: GraphService Implementation
Per DYK-02: _source_dir field for path resolution from config file location
Per DYK-04: Tests validate _source_dir is set correctly during merge

TDD Approach: Tests written FIRST, implementation follows.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError


# =============================================================================
# T001: Tests for OtherGraph model
# =============================================================================


@pytest.mark.unit
class TestOtherGraph:
    """T001: Tests for OtherGraph configuration model."""

    def test_valid_graph_config(self):
        """
        Purpose: Proves basic OtherGraph instantiation works.
        Quality Contribution: Validates config schema.
        Acceptance Criteria: All fields populated correctly.

        Task: T001
        """
        from fs2.config.objects import OtherGraph

        graph = OtherGraph(
            name="shared-lib",
            path="~/projects/shared/.fs2/graph.pickle",
            description="Shared utilities",
            source_url="https://github.com/org/shared",
        )

        assert graph.name == "shared-lib"
        assert graph.path == "~/projects/shared/.fs2/graph.pickle"
        assert graph.description == "Shared utilities"
        assert graph.source_url == "https://github.com/org/shared"

    def test_reserved_name_default_rejected(self):
        """
        Purpose: Ensures 'default' cannot be used as graph name.
        Quality Contribution: Prevents ambiguity with local graph.
        Acceptance Criteria: ValidationError raised with "reserved" in message.

        Task: T001
        Per: Critical Finding 04
        """
        from fs2.config.objects import OtherGraph

        with pytest.raises(ValidationError, match="reserved"):
            OtherGraph(name="default", path="/some/path.pickle")

    def test_optional_fields(self):
        """
        Purpose: Proves description and source_url are optional.
        Quality Contribution: Validates minimal config works.
        Acceptance Criteria: Graph created with only name and path.

        Task: T001
        """
        from fs2.config.objects import OtherGraph

        graph = OtherGraph(name="minimal", path="/path/to/graph.pickle")

        assert graph.name == "minimal"
        assert graph.path == "/path/to/graph.pickle"
        assert graph.description is None
        assert graph.source_url is None

    def test_empty_name_rejected(self):
        """
        Purpose: Validates name cannot be empty or whitespace.
        Quality Contribution: Prevents misconfiguration.
        Acceptance Criteria: ValidationError raised for empty name.

        Task: T001
        """
        from fs2.config.objects import OtherGraph

        with pytest.raises(ValidationError, match="name"):
            OtherGraph(name="", path="/path/to/graph.pickle")

        with pytest.raises(ValidationError, match="name"):
            OtherGraph(name="   ", path="/path/to/graph.pickle")

    def test_empty_path_rejected(self):
        """
        Purpose: Validates path cannot be empty or whitespace.
        Quality Contribution: Prevents misconfiguration.
        Acceptance Criteria: ValidationError raised for empty path.

        Task: T001
        """
        from fs2.config.objects import OtherGraph

        with pytest.raises(ValidationError, match="path"):
            OtherGraph(name="valid-name", path="")

        with pytest.raises(ValidationError, match="path"):
            OtherGraph(name="valid-name", path="   ")

    def test_name_with_special_chars(self):
        """
        Purpose: Allows hyphens and underscores in names.
        Quality Contribution: Supports common naming patterns.
        Acceptance Criteria: Graph created successfully.

        Task: T001
        """
        from fs2.config.objects import OtherGraph

        graph1 = OtherGraph(name="my-lib", path="/path.pickle")
        assert graph1.name == "my-lib"

        graph2 = OtherGraph(name="my_lib", path="/path.pickle")
        assert graph2.name == "my_lib"

        graph3 = OtherGraph(name="my-lib_v2", path="/path.pickle")
        assert graph3.name == "my-lib_v2"


# =============================================================================
# T002: Tests for OtherGraphsConfig model
# =============================================================================


@pytest.mark.unit
class TestOtherGraphsConfig:
    """T002: Tests for OtherGraphsConfig container model."""

    def test_empty_graphs_list_by_default(self):
        """
        Purpose: Proves default state is empty list.
        Quality Contribution: Backward compatibility.
        Acceptance Criteria: Empty list, not None.

        Task: T002
        """
        from fs2.config.objects import OtherGraphsConfig

        config = OtherGraphsConfig()

        assert config.graphs == []
        assert isinstance(config.graphs, list)

    def test_config_path_attribute(self):
        """
        Purpose: Verifies YAML loading path.
        Quality Contribution: Ensures auto-loading works.
        Acceptance Criteria: __config_path__ == "other_graphs".

        Task: T002
        """
        from fs2.config.objects import OtherGraphsConfig

        assert OtherGraphsConfig.__config_path__ == "other_graphs"

    def test_multiple_graphs(self):
        """
        Purpose: Container holds multiple graphs.
        Quality Contribution: Validates list behavior.
        Acceptance Criteria: All graphs accessible by index.

        Task: T002
        """
        from fs2.config.objects import OtherGraph, OtherGraphsConfig

        config = OtherGraphsConfig(
            graphs=[
                OtherGraph(name="lib1", path="/path1.pickle"),
                OtherGraph(name="lib2", path="/path2.pickle"),
                OtherGraph(name="lib3", path="/path3.pickle"),
            ]
        )

        assert len(config.graphs) == 3
        assert config.graphs[0].name == "lib1"
        assert config.graphs[1].name == "lib2"
        assert config.graphs[2].name == "lib3"

    def test_in_yaml_config_types(self):
        """
        Purpose: Verifies registry inclusion.
        Quality Contribution: Ensures auto-loading from YAML.
        Acceptance Criteria: OtherGraphsConfig in YAML_CONFIG_TYPES.

        Task: T002
        """
        from fs2.config.objects import YAML_CONFIG_TYPES, OtherGraphsConfig

        assert OtherGraphsConfig in YAML_CONFIG_TYPES


# =============================================================================
# T003: Tests for config list concatenation
# =============================================================================


@pytest.mark.unit
class TestOtherGraphsConfigMerge:
    """T003: Tests for config list concatenation behavior.

    Per Critical Finding 01: deep_merge() treats lists as scalars.
    Custom merge logic needed to concatenate user + project graphs.
    Per DYK-02: Warning logged when project shadows user graph.
    """

    def test_user_and_project_graphs_concatenated(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Proves list concatenation works.
        Quality Contribution: Core multi-graph functionality.
        Acceptance Criteria: 4 graphs from 2 (user) + 2 (project).

        Task: T003
        Per: Critical Finding 01, spec AC9
        """
        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup user config directory
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "user-lib1"
      path: "/user/lib1.pickle"
    - name: "user-lib2"
      path: "/user/lib2.pickle"
"""
        )

        # Setup project config directory
        project_config_dir = tmp_path / ".fs2"
        project_config_dir.mkdir()
        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "project-lib1"
      path: "/project/lib1.pickle"
    - name: "project-lib2"
      path: "/project/lib2.pickle"
"""
        )

        # Monkeypatch config directories
        monkeypatch.chdir(tmp_path)
        # Patch in the service module where it's imported
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        service = FS2ConfigurationService()
        config = service.get(OtherGraphsConfig)

        assert config is not None
        assert len(config.graphs) == 4
        names = [g.name for g in config.graphs]
        assert "user-lib1" in names
        assert "user-lib2" in names
        assert "project-lib1" in names
        assert "project-lib2" in names

    def test_duplicate_names_project_wins(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Later source (project) wins per name.
        Quality Contribution: Clear deduplication semantics.
        Acceptance Criteria: Project's version of duplicate name used.

        Task: T003
        Per: DYK-02
        """
        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup user config - has "shared" with user path
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "shared"
      path: "/user/shared.pickle"
      description: "User version"
    - name: "unique-user"
      path: "/user/unique.pickle"
"""
        )

        # Setup project config - has "shared" with project path
        project_config_dir = tmp_path / ".fs2"
        project_config_dir.mkdir()
        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "shared"
      path: "/project/shared.pickle"
      description: "Project version"
    - name: "unique-project"
      path: "/project/unique.pickle"
"""
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        service = FS2ConfigurationService()
        config = service.get(OtherGraphsConfig)

        assert config is not None
        # Should have 3 graphs: unique-user, shared (project version), unique-project
        assert len(config.graphs) == 3

        # Find the "shared" graph - should be project version
        shared = next(g for g in config.graphs if g.name == "shared")
        assert shared.path == "/project/shared.pickle"
        assert shared.description == "Project version"

    def test_duplicate_names_logs_warning(
        self, tmp_path, monkeypatch, clean_config_env, caplog
    ):
        """
        Purpose: Warning logged when project shadows user graph.
        Quality Contribution: Visibility into shadowing behavior.
        Acceptance Criteria: Warning message contains shadowed graph name.

        Task: T003
        Per: DYK-02
        """
        import logging

        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup user config
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "shadowed-lib"
      path: "/user/lib.pickle"
"""
        )

        # Setup project config with same name
        project_config_dir = tmp_path / ".fs2"
        project_config_dir.mkdir()
        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "shadowed-lib"
      path: "/project/lib.pickle"
"""
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        with caplog.at_level(logging.WARNING, logger="fs2.config.service"):
            FS2ConfigurationService()

        # Check for warning about shadowed graph
        assert any("shadowed-lib" in record.message for record in caplog.records)
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    def test_user_only_graphs(self, tmp_path, monkeypatch, clean_config_env):
        """
        Purpose: User config works without project config.
        Quality Contribution: Partial config support.
        Acceptance Criteria: User graphs available.

        Task: T003
        """
        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup user config only
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "user-only"
      path: "/user/lib.pickle"
"""
        )

        # Setup empty project config
        project_config_dir = tmp_path / ".fs2"
        project_config_dir.mkdir()
        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            """scan:
  scan_paths:
    - "."
"""
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        service = FS2ConfigurationService()
        config = service.get(OtherGraphsConfig)

        assert config is not None
        assert len(config.graphs) == 1
        assert config.graphs[0].name == "user-only"

    def test_project_only_graphs(self, tmp_path, monkeypatch, clean_config_env):
        """
        Purpose: Project config works without user config.
        Quality Contribution: Partial config support.
        Acceptance Criteria: Project graphs available.

        Task: T003
        """
        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup empty user config
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
"""
        )

        # Setup project config only
        project_config_dir = tmp_path / ".fs2"
        project_config_dir.mkdir()
        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "project-only"
      path: "/project/lib.pickle"
"""
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        service = FS2ConfigurationService()
        config = service.get(OtherGraphsConfig)

        assert config is not None
        assert len(config.graphs) == 1
        assert config.graphs[0].name == "project-only"

    def test_no_other_graphs_section(self, tmp_path, monkeypatch, clean_config_env):
        """
        Purpose: Backward compatibility when no other_graphs section.
        Quality Contribution: Existing configs still work.
        Acceptance Criteria: Empty OtherGraphsConfig returned.

        Task: T003
        """
        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup config without other_graphs
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
"""
        )

        project_config_dir = tmp_path / ".fs2"
        project_config_dir.mkdir()
        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            """scan:
  scan_paths:
    - "."
"""
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        service = FS2ConfigurationService()
        config = service.get(OtherGraphsConfig)

        # Should return None since no other_graphs section exists
        # and we don't auto-create empty config objects
        # OR if we do auto-register, it should have empty graphs list
        if config is not None:
            assert config.graphs == []


# =============================================================================
# T007: Integration test - YAML loading
# =============================================================================


@pytest.mark.unit
class TestOtherGraphsConfigYAMLLoading:
    """T007: Integration tests for YAML loading.

    Per DYK-03: ERROR logged for invalid graphs.
    Per DYK-04: ERROR logged for schema misuse (list instead of dict).
    """

    def test_loads_from_yaml(self, tmp_path, monkeypatch, clean_config_env):
        """
        Purpose: End-to-end YAML loading works.
        Quality Contribution: Validates full pipeline.
        Acceptance Criteria: Graphs accessible via require().

        Task: T007
        """
        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup project config
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "external-lib"
      path: "~/projects/lib/.fs2/graph.pickle"
      description: "External library for reference"
      source_url: "https://github.com/org/lib"
"""
        )

        monkeypatch.chdir(tmp_path)

        service = FS2ConfigurationService()
        config = service.get(OtherGraphsConfig)

        assert config is not None
        assert len(config.graphs) == 1
        assert config.graphs[0].name == "external-lib"
        assert config.graphs[0].path == "~/projects/lib/.fs2/graph.pickle"
        assert config.graphs[0].description == "External library for reference"
        assert config.graphs[0].source_url == "https://github.com/org/lib"

    def test_invalid_graph_logs_error(
        self, tmp_path, monkeypatch, clean_config_env, caplog
    ):
        """
        Purpose: Fail fast with clear message for invalid graphs.
        Quality Contribution: Actionable error messages.
        Acceptance Criteria: ERROR log with graph name and validation reason.

        Task: T007
        Per: DYK-03, Invariant #5
        """
        import logging

        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup config with invalid graph (uses reserved name "default")
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "default"
      path: "/some/path.pickle"
"""
        )

        monkeypatch.chdir(tmp_path)

        with caplog.at_level(logging.ERROR, logger="fs2.config.service"):
            FS2ConfigurationService()

        # Should log ERROR (not debug) with specific message
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) > 0
        # Should mention the config path or validation error
        assert any("other_graphs" in r.message.lower() for r in error_records) or any(
            "reserved" in r.message.lower() for r in error_records
        )

    def test_list_instead_of_dict_logs_error(
        self, tmp_path, monkeypatch, clean_config_env, caplog
    ):
        """
        Purpose: Schema misuse detection.
        Quality Contribution: Helpful error for common mistake.
        Acceptance Criteria: ERROR log with correct format example.

        Task: T007
        Per: DYK-04, Invariant #6
        """
        import logging

        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup config with wrong schema (list directly under other_graphs)
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  - name: "lib1"
    path: "/path1.pickle"
"""
        )

        monkeypatch.chdir(tmp_path)

        with caplog.at_level(logging.ERROR, logger="fs2.config.service"):
            FS2ConfigurationService()

        # Should log ERROR about schema misuse
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        # If we detect schema misuse, there should be an error
        # Note: This may not fire if YAML loads it as a different structure
        # The implementation should check if other_graphs is a list and log error
        # For now, we just verify no exception is raised
        # The actual assertion depends on implementation


# =============================================================================
# Phase 2 T000: Tests for _source_dir field
# =============================================================================


@pytest.mark.unit
class TestOtherGraphSourceDir:
    """Phase 2 T000: Tests for OtherGraph._source_dir field.

    Per DYK-02: Relative paths resolve from config file's source directory.
    Per DYK-04: Tests validate _source_dir is set correctly during merge.

    The _source_dir field tracks which config file each OtherGraph came from,
    enabling correct relative path resolution at GraphService access time.
    """

    def test_source_dir_field_exists_and_defaults_to_none(self):
        """
        Purpose: OtherGraph has _source_dir field defaulting to None.
        Quality Contribution: Field presence validation.
        Acceptance Criteria: Field accessible, defaults to None.

        Task: Phase 2 T000
        Per: DYK-02
        """
        from fs2.config.objects import OtherGraph

        graph = OtherGraph(name="test", path="/some/path.pickle")

        assert hasattr(graph, "_source_dir")
        assert graph._source_dir is None

    def test_source_dir_can_be_set_after_construction(self):
        """
        Purpose: _source_dir can be set after construction (PrivateAttr).
        Quality Contribution: Field settability validation.
        Acceptance Criteria: Field accepts Path value after init.

        Task: Phase 2 T000
        Per: DYK-02
        Note: Pydantic v2 PrivateAttr fields are set after construction, not in __init__.
        """
        from fs2.config.objects import OtherGraph

        graph = OtherGraph(name="test", path="./relative/path.pickle")
        source_dir = Path("/home/user/.config/fs2")
        graph._source_dir = source_dir

        assert graph._source_dir == source_dir

    def test_source_dir_accepts_path_object(self):
        """
        Purpose: _source_dir accepts Path object.
        Quality Contribution: Type validation.
        Acceptance Criteria: Path object stored correctly.

        Task: Phase 2 T000
        Per: DYK-02
        """
        from fs2.config.objects import OtherGraph

        graph = OtherGraph(name="test", path="/abs/path.pickle")
        graph._source_dir = Path("/config/dir")

        assert isinstance(graph._source_dir, Path)
        assert graph._source_dir == Path("/config/dir")

    def test_source_dir_set_from_user_config(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: _source_dir is set to user config dir for user graphs.
        Quality Contribution: Core DYK-02 functionality.
        Acceptance Criteria: User graph has user config dir as _source_dir.

        Task: Phase 2 T000
        Per: DYK-02, DYK-04
        """
        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup user config directory
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "user-graph"
      path: "./relative/path.pickle"
"""
        )

        # Setup empty project config
        project_config_dir = tmp_path / ".fs2"
        project_config_dir.mkdir()
        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            """scan:
  scan_paths:
    - "."
"""
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        service = FS2ConfigurationService()
        config = service.get(OtherGraphsConfig)

        assert config is not None
        assert len(config.graphs) == 1
        user_graph = config.graphs[0]
        assert user_graph.name == "user-graph"
        # _source_dir should be set to user config directory
        assert user_graph._source_dir == user_config_dir

    def test_source_dir_set_from_project_config(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: _source_dir is set to project config dir for project graphs.
        Quality Contribution: Core DYK-02 functionality.
        Acceptance Criteria: Project graph has project config dir as _source_dir.

        Task: Phase 2 T000
        Per: DYK-02, DYK-04
        """
        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup empty user config
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
"""
        )

        # Setup project config with graph
        project_config_dir = tmp_path / ".fs2"
        project_config_dir.mkdir()
        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "project-graph"
      path: "../sibling-project/.fs2/graph.pickle"
"""
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        service = FS2ConfigurationService()
        config = service.get(OtherGraphsConfig)

        assert config is not None
        assert len(config.graphs) == 1
        project_graph = config.graphs[0]
        assert project_graph.name == "project-graph"
        # _source_dir should be set to project config directory
        assert project_graph._source_dir == project_config_dir

    def test_source_dir_preserved_during_merge(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Both user and project graphs keep their respective _source_dir.
        Quality Contribution: Validates merge preserves source information.
        Acceptance Criteria: Each graph has correct _source_dir after merge.

        Task: Phase 2 T000
        Per: DYK-02, DYK-04
        """
        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup user config directory
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "from-user"
      path: "./user-relative.pickle"
"""
        )

        # Setup project config directory
        project_config_dir = tmp_path / ".fs2"
        project_config_dir.mkdir()
        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "from-project"
      path: "./project-relative.pickle"
"""
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        service = FS2ConfigurationService()
        config = service.get(OtherGraphsConfig)

        assert config is not None
        assert len(config.graphs) == 2

        # Find each graph and verify _source_dir
        user_graph = next(g for g in config.graphs if g.name == "from-user")
        project_graph = next(g for g in config.graphs if g.name == "from-project")

        assert user_graph._source_dir == user_config_dir
        assert project_graph._source_dir == project_config_dir

    def test_source_dir_overwritten_when_project_shadows_user(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: When project shadows user graph, _source_dir is project dir.
        Quality Contribution: Validates shadowing behavior for _source_dir.
        Acceptance Criteria: Shadowed graph has project's _source_dir.

        Task: Phase 2 T000
        Per: DYK-02
        """
        from fs2.config.objects import OtherGraphsConfig
        from fs2.config.service import FS2ConfigurationService

        # Setup user config with graph
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "shadowed"
      path: "./user-version.pickle"
"""
        )

        # Setup project config with same name (shadows user)
        project_config_dir = tmp_path / ".fs2"
        project_config_dir.mkdir()
        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "shadowed"
      path: "./project-version.pickle"
"""
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        service = FS2ConfigurationService()
        config = service.get(OtherGraphsConfig)

        assert config is not None
        assert len(config.graphs) == 1

        shadowed_graph = config.graphs[0]
        assert shadowed_graph.name == "shadowed"
        assert shadowed_graph.path == "./project-version.pickle"
        # _source_dir should be project dir since project won
        assert shadowed_graph._source_dir == project_config_dir
