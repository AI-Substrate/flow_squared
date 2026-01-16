# Fix Tasks: Phase 1 - Foundation

**Created**: 2026-01-15
**Review**: [./review.phase-1-foundation.md](./review.phase-1-foundation.md)
**Verdict**: REQUEST_CHANGES

---

## Summary

4 blocking issues + 2 advisory issues identified. Fix in priority order below.

---

## Blocking Issues (Must Fix)

### FIX-001: Remove Unused Import (LINT-001)

**Severity**: HIGH
**File**: `src/fs2/cli/web.py`
**Line**: 19

**Issue**: `webbrowser` imported but never used.

**Patch**:
```diff
 import subprocess
 import sys
-import webbrowser
 from pathlib import Path
 from typing import Annotated
```

**Test**: `ruff check src/fs2/cli/web.py` should not report F401

---

### FIX-002: Add Exception Chaining (LINT-002)

**Severity**: HIGH
**File**: `src/fs2/cli/web.py`
**Line**: 98

**Issue**: Exception raised within except clause without `from err` or `from None`.

**Patch**:
```diff
     except FileNotFoundError:
         typer.echo(
             "Error: Streamlit not installed. Install with: pip install streamlit",
             err=True,
         )
-        raise typer.Exit(1)
+        raise typer.Exit(1) from None
```

**Test**: `ruff check src/fs2/cli/web.py` should not report B904

---

### FIX-003: Add Type Safety to _unflatten_dict (CORR-001)

**Severity**: HIGH
**File**: `src/fs2/web/services/config_inspector.py`
**Lines**: 173-176

**Issue**: No type validation when traversing nested keys. If intermediate value is scalar, crashes with AttributeError.

**Current Code**:
```python
for part in parts[:-1]:
    if part not in current:
        current[part] = {}
    current = current[part]
```

**Patch**:
```diff
 for part in parts[:-1]:
     if part not in current:
         current[part] = {}
+    elif not isinstance(current[part], dict):
+        # Cannot unflatten: intermediate value is not a dict
+        # Skip this key rather than crash
+        break
     current = current[part]
+ else:
+    current[parts[-1]] = value
+    continue
+ # If we broke out of the loop, skip this key
+ continue
```

**Alternative (simpler, logs warning)**:
```diff
 for part in parts[:-1]:
     if part not in current:
         current[part] = {}
+    if not isinstance(current[part], dict):
+        # Skip keys that would overwrite non-dict values
+        break
     current = current[part]
+ else:
+    # Only set value if we traversed all intermediate parts
+    current[parts[-1]] = value
```

**Test**: Add test case in `test_config_inspector.py`:
```python
def test_unflatten_handles_mixed_type_nesting(self, tmp_path: Path) -> None:
    """Verify graceful handling of configs with mixed-type nesting.

    Contract: If intermediate key has scalar value, key is skipped.
    """
    config = tmp_path / "config.yaml"
    # 'llm' is a string, not a dict, but also appears as nested key
    config.write_text("llm: fake\nllm.timeout: 30")

    inspector = ConfigInspectorService(project_path=config)
    result = inspector.inspect()

    # Should not crash; behavior depends on YAML parser
    assert isinstance(result, InspectionResult)
```

---

### FIX-004: Add Footnote References to Tasks Table (GRAPH-001)

**Severity**: CRITICAL
**File**: `docs/plans/026-web/tasks/phase-1-foundation/tasks.md`
**Lines**: 213-227

**Issue**: Tasks table Notes column has no `[^N]` footnote markers. This breaks bidirectional navigation from tasks to changed files.

**Required Changes**: Update each task's Notes column to include the corresponding footnote:

| Task ID | Current Notes | Required Update |
|---------|---------------|-----------------|
| T001 | `Enables imports` | `Enables imports [^7]` |
| T002 | `Per Critical Discovery 01 - verify os.environ unchanged` | `Per Critical Discovery 01 - verify os.environ unchanged [^1]` |
| T003 | `Per Critical Discovery 01, 02, 03` | `Per Critical Discovery 01, 02, 03 [^2]` |
| T004 | `Per Critical Discovery 05` | `Per Critical Discovery 05 [^3]` |
| T005 | `Per Critical Discovery 05` | `Per Critical Discovery 05 [^4]` |
| T006 | `Simple config model` | `Simple config model [^10]` |
| T007 | `Pattern: FakeLogAdapter` | `Pattern: FakeLogAdapter [^5]` |
| T008 | `Follow FakeLogAdapter pattern` | `Follow FakeLogAdapter pattern [^5]` |
| T009 | `Pattern: FakeLogAdapter` | `Pattern: FakeLogAdapter [^6]` |
| T010 | `Follow FakeLogAdapter pattern` | `Follow FakeLogAdapter pattern [^6]` |
| T011 | (empty) | `[^8]` |
| T012 | `Add to main.py app` | `Add to main.py app [^8]` |
| T013 | `Per Critical Discovery 06 - session isolation` | `Per Critical Discovery 06 - session isolation [^9]` |

**Test**: Verify each `[^N]` in tasks table has corresponding entry in § Phase Footnote Stubs

---

## Advisory Issues (Should Fix)

### FIX-005: Use contextlib.suppress Pattern (LINT-003)

**Severity**: LOW
**File**: `src/fs2/web/services/config_backup.py`
**Lines**: 186-189

**Issue**: Try-except-pass pattern can be replaced with cleaner `contextlib.suppress`.

**Patch**:
```diff
+import contextlib
 ...
         finally:
             # Clean up temp file if it exists (operation failed)
             if temp_path is not None and temp_path.exists():
-                try:
-                    temp_path.unlink()
-                except OSError:
-                    pass  # Best effort cleanup
+                with contextlib.suppress(OSError):
+                    temp_path.unlink()
```

---

### FIX-006: Handle Multi-Placeholder Values (CORR-002)

**Severity**: MEDIUM
**File**: `src/fs2/web/services/config_inspector.py`
**Lines**: 314-322

**Issue**: Only first placeholder detected in multi-placeholder values.

**Current Code**:
```python
match = _PLACEHOLDER_PATTERN.search(value)
if match:
    var_name = match.group(1)
    if var_name in secrets and secrets[var_name]:
        result.placeholder_states[key] = PlaceholderState.RESOLVED
    else:
        result.placeholder_states[key] = PlaceholderState.UNRESOLVED
```

**Patch**:
```diff
-match = _PLACEHOLDER_PATTERN.search(value)
-if match:
-    var_name = match.group(1)
-    if var_name in secrets and secrets[var_name]:
+# Find ALL placeholders in value
+matches = _PLACEHOLDER_PATTERN.findall(value)
+if matches:
+    # Check if ALL placeholders are resolved
+    all_resolved = all(
+        var_name in secrets and secrets[var_name]
+        for var_name in matches
+    )
+    if all_resolved:
         result.placeholder_states[key] = PlaceholderState.RESOLVED
     else:
         result.placeholder_states[key] = PlaceholderState.UNRESOLVED
```

**Test**: Add test case in `test_config_inspector.py`:
```python
def test_placeholder_multi_value_detection(self, tmp_path: Path) -> None:
    """Verify all placeholders detected in multi-placeholder values.

    Contract: State is RESOLVED only if ALL placeholders resolve.
    """
    config = tmp_path / "config.yaml"
    config.write_text("api:\n  url: ${API_HOST}:${API_PORT}")

    env_file = tmp_path / ".env"
    env_file.write_text("API_HOST=localhost")  # Missing API_PORT

    inspector = ConfigInspectorService(
        project_path=config,
        secrets_paths=[env_file],
    )
    result = inspector.inspect()

    # Should be UNRESOLVED because API_PORT is missing
    assert result.placeholder_states["api.url"] == PlaceholderState.UNRESOLVED
```

---

## Verification Commands

After applying fixes:

```bash
# 1. Run linting (should be clean)
ruff check src/fs2/web/ src/fs2/cli/web.py

# 2. Run tests (should all pass)
pytest tests/unit/web/ tests/unit/cli/test_web_cli.py -v

# 3. Verify no forbidden imports
grep -rn "^from dotenv import load_dotenv" src/fs2/web/ && echo "FAIL" || echo "PASS"

# 4. Check CLI still works
python -m fs2.cli.main web --help
```

---

## Re-Review Checklist

Before requesting re-review:

- [ ] FIX-001 applied: Removed unused `webbrowser` import
- [ ] FIX-002 applied: Added `from None` to exception re-raise
- [ ] FIX-003 applied: Added type safety to `_unflatten_dict`
- [ ] FIX-004 applied: Added `[^N]` footnote refs to tasks table
- [ ] FIX-005 applied (optional): Used `contextlib.suppress`
- [ ] FIX-006 applied (optional): Handle multi-placeholder values
- [ ] All tests pass: `pytest tests/unit/web/ tests/unit/cli/test_web_cli.py -v`
- [ ] Lint clean: `ruff check src/fs2/web/ src/fs2/cli/web.py`

Re-run review: `/plan-7-code-review --phase "Phase 1: Foundation" --plan "/workspaces/flow_squared/docs/plans/026-web/web-plan.md"`

---

**Fix Tasks Created**: 2026-01-15
