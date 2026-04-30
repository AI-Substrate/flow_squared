"""ConfigurationService ABC and implementations for fs2.

This module provides:
- ConfigurationService: Abstract base class defining the config interface
- FS2ConfigurationService: Production implementation with multi-source loading
- FakeConfigurationService: Test double for DI in tests

Per Architecture Decision: Typed object registry pattern.
Per Insight #1: No singleton, explicit construction via DI.
Per Critical Finding 01: Pre-extract/post-inject for list concatenation.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from fs2.config.objects import OtherGraphsConfig

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.loaders import (
    deep_merge,
    expand_placeholders,
    load_secrets_to_env,
    load_yaml_config,
    parse_env_vars,
)
from fs2.config.objects import YAML_CONFIG_TYPES, GraphConfig
from fs2.config.paths import get_project_config_dir, get_user_config_dir

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Paths where lists should be concatenated instead of replaced during merge.
# Per Critical Finding 01: deep_merge() treats lists as scalars (overlay wins).
# These paths get special handling: extract before merge, concatenate, re-inject.
CONCATENATE_LIST_PATHS: list[str] = ["other_graphs.graphs"]

# Config types that should be auto-registered with default values when their
# YAML key is absent from the loaded config. Use this for configs whose every
# field has a sensible default (so default-construction is safe) and whose
# absence should NOT raise MissingConfigurationError when consumers call
# `config.require(...)`.
#
# Closes issue #14: GraphConfig has a default `graph_path` and is consumed by
# tree/get_node/graph_utilities services. Without this, omitting the `graph:`
# YAML block makes MCP tools fail with `Missing configuration: GraphConfig`,
# even though the default would have worked.
#
# Contract:
#   - Auto-registration runs AFTER YAML loading, so any explicit YAML value
#     wins (the type is already registered before this fall-through runs and
#     `set()` is idempotent — explicit registration takes precedence).
#   - Iterate in declaration order; duplicates are not expected.
#   - Add a config here only when ALL fields have safe defaults.
_AUTO_DEFAULT_CONFIGS: list[type[BaseModel]] = [GraphConfig]


def _get_nested_value(data: dict, path: str) -> Any:
    """Get a value from a nested dict using dot-notation path.

    Args:
        data: Dictionary to navigate.
        path: Dot-separated path (e.g., "other_graphs.graphs").

    Returns:
        The value at the path, or None if path doesn't exist.
    """
    parts = path.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested_value(data: dict, path: str, value: Any) -> None:
    """Set a value in a nested dict using dot-notation path.

    Creates intermediate dicts as needed.

    Args:
        data: Dictionary to modify.
        path: Dot-separated path (e.g., "other_graphs.graphs").
        value: Value to set at the path.
    """
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _delete_nested_value(data: dict, path: str) -> None:
    """Delete a value from a nested dict using dot-notation path.

    Does nothing if path doesn't exist.

    Args:
        data: Dictionary to modify.
        path: Dot-separated path (e.g., "other_graphs.graphs").
    """
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict) and parts[-1] in current:
        del current[parts[-1]]


class ConfigurationService(ABC):
    """Abstract base class for configuration services.

    Provides a typed object registry pattern where config objects
    are stored and retrieved by type.

    Methods:
        set: Store a typed config object.
        get: Retrieve a config object by type (returns None if not set).
        require: Retrieve a config object by type (raises if not set).
    """

    @abstractmethod
    def set(self, config: T) -> None:
        """Store a typed configuration object.

        Args:
            config: Pydantic BaseModel instance to store.
        """

    @abstractmethod
    def get(self, config_type: type[T]) -> T | None:
        """Retrieve a configuration object by type.

        Args:
            config_type: The type of config to retrieve.

        Returns:
            The config object if set, None otherwise.
        """

    @abstractmethod
    def require(self, config_type: type[T]) -> T:
        """Retrieve a configuration object by type, raising if not set.

        Args:
            config_type: The type of config to retrieve.

        Returns:
            The config object.

        Raises:
            MissingConfigurationError: If config type is not set.
        """


class FS2ConfigurationService(ConfigurationService):
    """Production configuration service with multi-source loading.

    Loading pipeline (executed in __init__):
    1. Load secrets into os.environ (user → project → .env)
    2. Load raw config dicts from each source
    3. Pre-extract lists from CONCATENATE_LIST_PATHS (per Critical Finding 01)
    4. Deep merge all configs (user → project → env vars)
    5. Post-inject concatenated lists (user + project, deduplicated)
    6. Expand ${VAR} placeholders
    7. Create typed config objects from YAML_CONFIG_TYPES

    Precedence (lowest → highest):
    - Config object defaults
    - User YAML (~/.config/fs2/config.yaml)
    - Project YAML (./.fs2/config.yaml)
    - Environment vars (FS2_*)

    Special handling for CONCATENATE_LIST_PATHS:
    - Lists at these paths are concatenated (not replaced) during merge
    - Duplicate items (by name) are deduplicated, with later source winning
    - Warning logged when project shadows user-defined item
    """

    def __init__(self) -> None:
        """Initialize the service, loading all config sources."""
        self._configs: dict[type, BaseModel] = {}

        # Phase 1: Load secrets into os.environ
        load_secrets_to_env()

        # Phase 2: Load raw config dicts from each source
        user_config_file = get_user_config_dir() / "config.yaml"
        user_raw = load_yaml_config(user_config_file)

        project_config_file = get_project_config_dir() / "config.yaml"
        project_raw = load_yaml_config(project_config_file)

        env_raw = parse_env_vars()

        # Phase 3: Pre-extract lists from CONCATENATE_LIST_PATHS
        # Per Critical Finding 01: Extract before deep_merge, which would clobber user's list
        # Per Phase 2 DYK-02: Track source directories for path resolution
        user_config_dir = get_user_config_dir()
        project_config_dir = get_project_config_dir()

        extracted_lists: dict[str, dict[str, tuple[list, Path]]] = {}
        for path in CONCATENATE_LIST_PATHS:
            extracted_lists[path] = {
                "user": (
                    self._extract_and_remove_list(user_raw, path),
                    user_config_dir,
                ),
                "project": (
                    self._extract_and_remove_list(project_raw, path),
                    project_config_dir,
                ),
            }

        # Phase 4: Deep merge all configs (user → project → env)
        raw_config: dict = {}
        raw_config = deep_merge(raw_config, user_raw)
        raw_config = deep_merge(raw_config, project_raw)
        raw_config = deep_merge(raw_config, env_raw)

        # Phase 5: Post-inject concatenated lists
        # Per DYK-02: Log warning on name collision when project shadows user
        # Per Phase 2 DYK-02: Set _source_dir on each item for path resolution
        for path, lists in extracted_lists.items():
            user_list, user_source_dir = lists["user"]
            project_list, project_source_dir = lists["project"]
            if user_list or project_list:
                concatenated = self._concatenate_and_dedupe(
                    user_list,
                    project_list,
                    path,
                    user_source_dir=user_source_dir,
                    project_source_dir=project_source_dir,
                )
                if concatenated:
                    _set_nested_value(raw_config, path, concatenated)

        # Phase 6: Expand ${VAR} placeholders
        expand_placeholders(raw_config)

        # Phase 7: Create typed config objects
        self._create_config_objects(raw_config)

    def _extract_and_remove_list(self, data: dict, path: str) -> list:
        """Extract a list from nested dict and remove it.

        Per DYK-04: Detect schema misuse (list instead of dict for parent).
        Logs ERROR if the value at path's parent is a list when it should be dict.

        Args:
            data: Dictionary to extract from.
            path: Dot-separated path to the list.

        Returns:
            The list at the path, or empty list if not found or invalid.
        """
        # Check for schema misuse: parent should be dict, not list
        # e.g., for path "other_graphs.graphs", check if "other_graphs" is a list
        parts = path.split(".")
        if len(parts) > 1:
            parent_path = ".".join(parts[:-1])
            parent_value = _get_nested_value(data, parent_path)
            if isinstance(parent_value, list):
                # Per DYK-04: Log ERROR with helpful message
                logger.error(
                    "Schema error: '%s' should be a dict with '%s' key, not a list. "
                    "Correct format:\n  %s:\n    %s:\n      - name: ...",
                    parent_path,
                    parts[-1],
                    parts[-2] if len(parts) > 1 else parent_path,
                    parts[-1],
                )
                # Clear the misformed data
                _delete_nested_value(data, parent_path)
                return []

        value = _get_nested_value(data, path)
        if isinstance(value, list):
            _delete_nested_value(data, path)
            return value
        return []

    def _concatenate_and_dedupe(
        self,
        user_list: list,
        project_list: list,
        path: str,
        *,
        user_source_dir: Path | None = None,
        project_source_dir: Path | None = None,
    ) -> list:
        """Concatenate two lists and deduplicate by name.

        Per spec AC9: Lists are concatenated (not replaced).
        Per DYK-02: Log warning when project shadows user item.
        Per Phase 2 DYK-02: Set _source_dir on each item for path resolution.

        Args:
            user_list: List from user config (lower priority).
            project_list: List from project config (higher priority, wins on collision).
            path: Config path for logging context.
            user_source_dir: Directory where user config was loaded from.
            project_source_dir: Directory where project config was loaded from.

        Returns:
            Concatenated list with duplicates removed (project wins on name collision).
            Each item dict will have _source_dir key set to its source directory.
        """
        # Build dict keyed by name for deduplication
        # User items first, then project items (project wins on collision)
        items_by_name: dict[str, dict] = {}

        # Track user names for shadow detection
        user_names: set[str] = set()

        for item in user_list:
            if isinstance(item, dict) and "name" in item:
                name = item["name"]
                # Per Phase 2 DYK-02: Set _source_dir for path resolution
                item["_source_dir"] = user_source_dir
                items_by_name[name] = item
                user_names.add(name)

        for item in project_list:
            if isinstance(item, dict) and "name" in item:
                name = item["name"]
                if name in user_names:
                    # Per DYK-02: Log warning about shadowing
                    logger.warning(
                        "Graph '%s' in project config shadows user config definition "
                        "(project version will be used)",
                        name,
                    )
                # Per Phase 2 DYK-02: Set _source_dir for path resolution
                item["_source_dir"] = project_source_dir
                items_by_name[name] = item  # Project wins

        return list(items_by_name.values())

    def _create_config_objects(self, raw_config: dict) -> None:
        """Create typed config objects from raw config dict.

        For each config type in YAML_CONFIG_TYPES, extracts data from
        raw_config using __config_path__ and creates the typed object.

        Per DYK-03: Log ERROR (not debug) for OtherGraphsConfig validation failures
        to ensure users see actionable error messages.
        Per Phase 2 DYK-02: Set _source_dir on OtherGraph objects after creation.
        """
        from fs2.config.objects import OtherGraphsConfig

        for config_type in YAML_CONFIG_TYPES:
            config_path = getattr(config_type, "__config_path__", None)
            if config_path is None:
                continue

            # Navigate to the config data using path (e.g., "azure.openai")
            data = raw_config
            for part in config_path.split("."):
                if not isinstance(data, dict) or part not in data:
                    data = None
                    break
                data = data[part]

            # Create typed object if data was found
            if data and isinstance(data, dict):
                try:
                    # Per Phase 2 DYK-02: Special handling for OtherGraphsConfig
                    # to preserve _source_dir from raw dicts to OtherGraph objects
                    if config_type is OtherGraphsConfig:
                        config_obj = self._create_other_graphs_config(data)
                    else:
                        config_obj = config_type(**data)
                    self.set(config_obj)
                except Exception as e:
                    # Per DYK-03: Log ERROR for OtherGraphsConfig validation failures
                    # Other configs log at debug to avoid noise for optional configs
                    if config_type is OtherGraphsConfig:
                        logger.error(
                            "Failed to load '%s' configuration: %s. "
                            "Check your other_graphs section in config.yaml.",
                            config_path,
                            e,
                        )
                    else:
                        # Skip invalid configs - validation error will surface
                        # when consumer tries to require() it
                        logger.debug(
                            "Failed to create %s from config path '%s': %s",
                            config_type.__name__,
                            config_path,
                            e,
                        )

        # Phase 7b: Auto-register defaults for configs marked as optional.
        # If a config in _AUTO_DEFAULT_CONFIGS was NOT registered above (because
        # its YAML key was absent), register a default-constructed instance.
        # Closes issue #14: see _AUTO_DEFAULT_CONFIGS module docstring.
        for config_type in _AUTO_DEFAULT_CONFIGS:
            if self.get(config_type) is None:
                self.set(config_type())

    def _create_other_graphs_config(self, data: dict) -> "OtherGraphsConfig":
        """Create OtherGraphsConfig with _source_dir preserved on each OtherGraph.

        Per Phase 2 DYK-02: Pydantic PrivateAttr fields are not set from __init__,
        so we must extract _source_dir from raw dict and set it after construction.

        Args:
            data: Raw dict containing 'graphs' list with _source_dir keys.

        Returns:
            OtherGraphsConfig with _source_dir set on each OtherGraph.
        """
        from fs2.config.objects import OtherGraph, OtherGraphsConfig

        graphs_data = data.get("graphs", [])
        graphs: list[OtherGraph] = []

        for graph_dict in graphs_data:
            if isinstance(graph_dict, dict):
                # Extract _source_dir before Pydantic ignores it
                source_dir = graph_dict.pop("_source_dir", None)

                # Create OtherGraph from remaining data
                graph = OtherGraph(**graph_dict)

                # Set private attribute after construction
                if source_dir is not None:
                    graph._source_dir = source_dir

                graphs.append(graph)

        return OtherGraphsConfig(graphs=graphs)

    def set(self, config: T) -> None:
        """Store a typed configuration object."""
        self._configs[type(config)] = config

    def get(self, config_type: type[T]) -> T | None:
        """Retrieve a configuration object by type."""
        return self._configs.get(config_type)  # type: ignore

    def require(self, config_type: type[T]) -> T:
        """Retrieve a configuration object by type, raising if not set."""
        config = self.get(config_type)
        if config is None:
            raise MissingConfigurationError(
                key=config_type.__name__,
                sources=[
                    f"Set via: config.set({config_type.__name__}(...))",
                    f"Or in YAML at: {getattr(config_type, '__config_path__', 'N/A')}",
                ],
            )
        return config


class FakeConfigurationService(ConfigurationService):
    """Test double for ConfigurationService.

    Accepts config objects in constructor for easy test setup.

    Usage:
        config = FakeConfigurationService(
            AzureOpenAIConfig(endpoint="..."),
            SearchQueryConfig(mode="slim"),
        )
        service = MyService(config=config)
    """

    def __init__(self, *configs: BaseModel) -> None:
        """Initialize with optional pre-set configs.

        Args:
            *configs: Typed config objects to pre-load.
        """
        self._configs: dict[type, BaseModel] = {}
        for config in configs:
            self.set(config)

    def set(self, config: T) -> None:
        """Store a typed configuration object."""
        self._configs[type(config)] = config

    def get(self, config_type: type[T]) -> T | None:
        """Retrieve a configuration object by type."""
        return self._configs.get(config_type)  # type: ignore

    def require(self, config_type: type[T]) -> T:
        """Retrieve a configuration object by type, raising if not set."""
        config = self.get(config_type)
        if config is None:
            raise MissingConfigurationError(
                key=config_type.__name__,
                sources=[
                    f"Set via: config.set({config_type.__name__}(...))",
                ],
            )
        return config
