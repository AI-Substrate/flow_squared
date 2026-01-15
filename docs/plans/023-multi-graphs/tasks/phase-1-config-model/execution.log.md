# Phase 1: Configuration Model - Execution Log

**Phase**: Phase 1: Configuration Model
**Plan**: [../../multi-graphs-plan.md](../../multi-graphs-plan.md)
**Started**: 2026-01-13
**Completed**: 2026-01-13

---

## Task T001: Write tests for OtherGraph model
**Started**: 2026-01-13
**Status**: ✅ Complete

### What I Did
Created test file `tests/unit/config/test_other_graphs_config.py` with TestOtherGraph class containing 6 tests:
- `test_valid_graph_config` - Basic instantiation
- `test_reserved_name_default_rejected` - Rejects "default" (Critical Finding 04)
- `test_optional_fields` - description/source_url optional
- `test_empty_name_rejected` - Empty/whitespace name rejected
- `test_empty_path_rejected` - Empty/whitespace path rejected
- `test_name_with_special_chars` - Allows hyphens, underscores

### Evidence
```
tests/unit/config/test_other_graphs_config.py::TestOtherGraph::test_valid_graph_config PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraph::test_reserved_name_default_rejected PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraph::test_optional_fields PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraph::test_empty_name_rejected PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraph::test_empty_path_rejected PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraph::test_name_with_special_chars PASSED
```

### Files Changed
- `tests/unit/config/test_other_graphs_config.py` — Created with TestOtherGraph class

**Completed**: 2026-01-13

---

## Task T002: Write tests for OtherGraphsConfig model
**Started**: 2026-01-13
**Status**: ✅ Complete

### What I Did
Added TestOtherGraphsConfig class with 4 tests:
- `test_empty_graphs_list_by_default` - Default is empty list
- `test_config_path_attribute` - __config_path__ == "other_graphs"
- `test_multiple_graphs` - Container holds multiple graphs
- `test_in_yaml_config_types` - Registered in YAML_CONFIG_TYPES

### Evidence
```
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfig::test_empty_graphs_list_by_default PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfig::test_config_path_attribute PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfig::test_multiple_graphs PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfig::test_in_yaml_config_types PASSED
```

### Files Changed
- `tests/unit/config/test_other_graphs_config.py` — Added TestOtherGraphsConfig class

**Completed**: 2026-01-13

---

## Task T003: Write tests for config list concatenation
**Started**: 2026-01-13
**Status**: ✅ Complete

### What I Did
Added TestOtherGraphsConfigMerge class with 6 tests:
- `test_user_and_project_graphs_concatenated` - 2+2=4 graphs
- `test_duplicate_names_project_wins` - Project version wins on collision
- `test_duplicate_names_logs_warning` - Warning logged on shadow (DYK-02)
- `test_user_only_graphs` - Works without project config
- `test_project_only_graphs` - Works without user config
- `test_no_other_graphs_section` - Backward compatibility

### Discoveries
- Monkeypatch must target `fs2.config.service.get_user_config_dir` not `fs2.config.paths.get_user_config_dir` since service.py imports at top level.

### Evidence
```
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfigMerge::test_user_and_project_graphs_concatenated PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfigMerge::test_duplicate_names_project_wins PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfigMerge::test_duplicate_names_logs_warning PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfigMerge::test_user_only_graphs PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfigMerge::test_project_only_graphs PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfigMerge::test_no_other_graphs_section PASSED
```

### Files Changed
- `tests/unit/config/test_other_graphs_config.py` — Added TestOtherGraphsConfigMerge class

**Completed**: 2026-01-13

---

## Task T004: Implement OtherGraph Pydantic model
**Started**: 2026-01-13
**Status**: ✅ Complete

### What I Did
Implemented `OtherGraph` Pydantic model in `objects.py`:
- Fields: name (str), path (str), description (str|None), source_url (str|None)
- @field_validator("name") - Rejects empty/whitespace and reserved "default"
- @field_validator("path") - Rejects empty/whitespace

### Evidence
All T001 tests pass (6/6)

### Files Changed
- `src/fs2/config/objects.py` — Added OtherGraph class (lines 739-795)

**Completed**: 2026-01-13

---

## Task T005: Implement OtherGraphsConfig model + registry
**Started**: 2026-01-13
**Status**: ✅ Complete

### What I Did
Implemented `OtherGraphsConfig` Pydantic model in `objects.py`:
- `__config_path__: ClassVar[str] = "other_graphs"`
- `graphs: list[OtherGraph] = []`
- Added to `YAML_CONFIG_TYPES` registry

### Evidence
All T002 tests pass (4/4)

### Files Changed
- `src/fs2/config/objects.py` — Added OtherGraphsConfig class (lines 798-832) and registry entry

**Completed**: 2026-01-13

---

## Task T006: Implement pre-extract/post-inject list concatenation
**Started**: 2026-01-13
**Status**: ✅ Complete

### What I Did
Implemented custom merge logic in `service.py`:

1. **Module-level additions:**
   - `CONCATENATE_LIST_PATHS = ["other_graphs.graphs"]` - Explicit opt-in for concatenation
   - `_get_nested_value()` - Navigate nested dict by dot path
   - `_set_nested_value()` - Set value in nested dict
   - `_delete_nested_value()` - Remove value from nested dict

2. **FS2ConfigurationService.__init__ refactored:**
   - Phase 2: Load raw configs from each source separately
   - Phase 3: Pre-extract lists from CONCATENATE_LIST_PATHS before deep_merge
   - Phase 4: Deep merge all configs
   - Phase 5: Post-inject concatenated lists (deduplicated, project wins)
   - Phase 6: Expand placeholders
   - Phase 7: Create typed config objects

3. **New methods:**
   - `_extract_and_remove_list()` - Extract list, detect schema misuse (DYK-04)
   - `_concatenate_and_dedupe()` - Concatenate + dedupe + warn on shadow (DYK-02)

4. **_create_config_objects updated:**
   - Log ERROR (not debug) for OtherGraphsConfig validation failures (DYK-03)

### Evidence
All T003 tests pass (6/6)
No regressions in existing config tests (234 passed)

### Files Changed
- `src/fs2/config/service.py` — Major refactor of __init__ and new helper methods

**Completed**: 2026-01-13

---

## Task T007: Integration test - load config with other_graphs
**Started**: 2026-01-13
**Status**: ✅ Complete

### What I Did
Added TestOtherGraphsConfigYAMLLoading class with 3 tests:
- `test_loads_from_yaml` - End-to-end YAML loading
- `test_invalid_graph_logs_error` - ERROR on validation failure (DYK-03)
- `test_list_instead_of_dict_logs_error` - ERROR on schema misuse (DYK-04)

### Evidence
```
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfigYAMLLoading::test_loads_from_yaml PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfigYAMLLoading::test_invalid_graph_logs_error PASSED
tests/unit/config/test_other_graphs_config.py::TestOtherGraphsConfigYAMLLoading::test_list_instead_of_dict_logs_error PASSED
```

### Files Changed
- `tests/unit/config/test_other_graphs_config.py` — Added TestOtherGraphsConfigYAMLLoading class

**Completed**: 2026-01-13

---

## Phase Summary

### Tests Written
- 19 tests total in `test_other_graphs_config.py`
- All passing

### Implementation Files
- `src/fs2/config/objects.py` — OtherGraph, OtherGraphsConfig models
- `src/fs2/config/service.py` — Pre-extract/post-inject merge logic

### Acceptance Criteria Met
- [x] AC1: Configuration of multiple graphs ✅
- [x] AC9: Config composition from multiple sources ✅ (lists concatenated)
- [x] AC10: Path resolution stores paths as-is (expansion in Phase 2) ✅
- [x] AC11: Default graph unchanged ✅ (backward compatible)

### Regression Check
- 234 config tests passed (2 skipped, 1 warning)
- No regressions introduced

### Key Decisions
1. **Explicit opt-in for list concatenation** via `CONCATENATE_LIST_PATHS`
2. **Project wins on name collision** with WARNING logged (DYK-02)
3. **ERROR logging** for validation failures (DYK-03) and schema misuse (DYK-04)
4. **Pre-extract/post-inject pattern** to work around deep_merge's list-as-scalar behavior

---

## Suggested Commit Message

```
feat(config): Add OtherGraph and OtherGraphsConfig for multi-graph support

Phase 1 of multi-graph feature implementation:

- Add OtherGraph Pydantic model with name, path, description, source_url
- Add OtherGraphsConfig container with __config_path__ = "other_graphs"
- Implement pre-extract/post-inject list concatenation for config merge
- User + project config graphs are concatenated, not replaced
- Duplicate names deduplicated (project wins, warning logged)
- Reserved name "default" rejected with clear error
- ERROR logging for validation failures and schema misuse

Per spec AC1, AC9, AC10, AC11
Per Critical Findings 01 (merge), 04 (reserved name)
Per DYK-02 (warning on shadow), DYK-03 (ERROR on invalid), DYK-04 (schema misuse)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```
