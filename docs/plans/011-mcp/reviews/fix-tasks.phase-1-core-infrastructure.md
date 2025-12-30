# Fix Tasks: Phase 1 - Core Infrastructure

**Review**: [./review.phase-1-core-infrastructure.md](./review.phase-1-core-infrastructure.md)
**Created**: 2025-12-29
**Status**: PENDING

---

## Blocking Issues (Must Fix)

These issues must be resolved before Phase 1 can be approved.

### FIX-001: Add logging when services are lazily initialized

**Severity**: HIGH (OBS-001)
**File**: `/workspaces/flow_squared/src/fs2/mcp/dependencies.py`
**Lines**: 42-56, 69-87

**Issue**: `get_config()` and `get_graph_store()` create singletons silently without any logging. This makes it impossible to debug initialization timing or configuration issues.

**Testing Approach**: Full TDD - write test first, then implement

**Test to Write First**:
```python
# tests/mcp_tests/test_dependencies.py
def test_config_creation_logs_debug_message(caplog):
    """Creating config singleton logs a DEBUG message."""
    import logging
    from fs2.mcp import dependencies

    dependencies.reset_services()

    with caplog.at_level(logging.DEBUG, logger="fs2.mcp.dependencies"):
        dependencies.get_config()

    assert "Creating ConfigurationService" in caplog.text
```

**Patch**:
```diff
--- a/src/fs2/mcp/dependencies.py
+++ b/src/fs2/mcp/dependencies.py
@@ -27,6 +27,10 @@ Usage:

 from __future__ import annotations

+import logging
+
+logger = logging.getLogger(__name__)
+
 from typing import TYPE_CHECKING

 if TYPE_CHECKING:
@@ -50,6 +54,7 @@ def get_config() -> ConfigurationService:
     global _config
     if _config is None:
         from fs2.config.service import FS2ConfigurationService
+        logger.debug("Creating ConfigurationService singleton")
         _config = FS2ConfigurationService()
     return _config

@@ -80,6 +85,7 @@ def get_graph_store() -> GraphStore:
     global _graph_store
     if _graph_store is None:
         from fs2.core.repos.graph_store_impl import NetworkXGraphStore
+        logger.debug("Creating GraphStore singleton with ConfigurationService injection")
         _graph_store = NetworkXGraphStore(get_config())
     return _graph_store
```

**Validation**:
```bash
uv run pytest tests/mcp_tests/test_dependencies.py -v
```

---

### FIX-002: Log original exception in translate_error()

**Severity**: HIGH (OBS-002)
**File**: `/workspaces/flow_squared/src/fs2/mcp/server.py`
**Lines**: 58-104

**Issue**: `translate_error()` translates exceptions to agent-friendly dicts but discards the original stack trace. This makes production debugging extremely difficult.

**Testing Approach**: Full TDD - write test first, then implement

**Test to Write First**:
```python
# tests/mcp_tests/test_errors.py
def test_translate_error_logs_original_exception(caplog):
    """translate_error logs the original exception with stack trace."""
    import logging
    from fs2.mcp.server import translate_error
    from fs2.core.adapters.exceptions import GraphNotFoundError
    from pathlib import Path

    with caplog.at_level(logging.ERROR, logger="fs2.mcp.server"):
        translate_error(GraphNotFoundError(Path(".fs2/graph.pickle")))

    assert "GraphNotFoundError" in caplog.text
    assert "MCP error" in caplog.text.lower() or "translat" in caplog.text.lower()
```

**Patch**:
```diff
--- a/src/fs2/mcp/server.py
+++ b/src/fs2/mcp/server.py
@@ -32,9 +32,12 @@ from fs2.core.adapters.logging_config import MCPLoggingConfig
 MCPLoggingConfig().configure()

 # NOW safe to import FastMCP and other fs2 modules
-from pathlib import Path
+import logging
 from typing import Any

+logger = logging.getLogger(__name__)
+
 from fastmcp import FastMCP

 from fs2.core.adapters.exceptions import (
@@ -78,6 +81,9 @@ def translate_error(exc: Exception) -> dict[str, Any]:
             'action': "Run 'fs2 scan' to create the graph."
         }
     """
+    # Log original exception for debugging (goes to stderr per MCP config)
+    logger.error("MCP error translation: %s", exc, exc_info=True)
+
     error_type = type(exc).__name__
     message = str(exc)
     action: str | None = None
```

**Validation**:
```bash
uv run pytest tests/mcp_tests/test_errors.py -v
```

---

## Recommended Issues (Should Fix)

These issues should be fixed but are not blocking.

### FIX-003: Add threading.Lock for thread-safe singleton

**Severity**: MEDIUM (COR-001)
**File**: `/workspaces/flow_squared/src/fs2/mcp/dependencies.py`
**Lines**: 42-87

**Issue**: Race condition in singleton pattern - concurrent `get_config()` calls could create duplicate instances.

**Patch**:
```diff
--- a/src/fs2/mcp/dependencies.py
+++ b/src/fs2/mcp/dependencies.py
@@ -28,6 +28,7 @@ from __future__ import annotations

 import logging
+import threading

 logger = logging.getLogger(__name__)

@@ -38,6 +39,7 @@ if TYPE_CHECKING:
 # Module-level singletons (None until first access)
 _config: ConfigurationService | None = None
 _graph_store: GraphStore | None = None
+_lock = threading.Lock()


 def get_config() -> ConfigurationService:
@@ -51,10 +53,11 @@ def get_config() -> ConfigurationService:
         ConfigurationService instance (real or injected fake).
     """
     global _config
-    if _config is None:
-        from fs2.config.service import FS2ConfigurationService
-        logger.debug("Creating ConfigurationService singleton")
-        _config = FS2ConfigurationService()
+    with _lock:
+        if _config is None:
+            from fs2.config.service import FS2ConfigurationService
+            logger.debug("Creating ConfigurationService singleton")
+            _config = FS2ConfigurationService()
     return _config
```

Apply similar pattern to `get_graph_store()`.

---

### FIX-004: Add startup log after MCPLoggingConfig

**Severity**: MEDIUM (OBS-003)
**File**: `/workspaces/flow_squared/src/fs2/mcp/server.py`
**Lines**: 29-33

**Issue**: No confirmation that MCP logging was successfully configured.

**Patch**:
```diff
--- a/src/fs2/mcp/server.py
+++ b/src/fs2/mcp/server.py
@@ -31,6 +31,10 @@ from fs2.core.adapters.logging_config import MCPLoggingConfig

 MCPLoggingConfig().configure()

+# Emit startup log to confirm logging is active (goes to stderr)
+import logging as _startup_logging
+_startup_logging.getLogger(__name__).info("MCP logging configured: all output routed to stderr")
+
 # NOW safe to import FastMCP and other fs2 modules
```

---

### FIX-005: Clean up unused imports

**Severity**: LOW (LINT-*)
**Files**: Multiple

**Command**:
```bash
uv run ruff check src/fs2/mcp/ tests/mcp_tests/ --fix
```

This will automatically:
- Remove unused `Path` import from `server.py:36`
- Remove unused `pytest` import from `test_dependencies.py:9`
- Remove unused `pytest` import from `test_errors.py:14`
- Organize import blocks in `test_protocol.py:79-82`

---

## Optional Issues (Nice to Have)

### FIX-006: Add autouse fixture for test isolation

**Severity**: LOW (COR-002)
**File**: `/workspaces/flow_squared/tests/mcp_tests/conftest.py`

**Patch**:
```python
@pytest.fixture(autouse=True)
def reset_mcp_dependencies():
    """Reset MCP service singletons after each test."""
    yield
    from fs2.mcp import dependencies
    dependencies.reset_services()
```

---

## Validation Commands

After implementing fixes, run:

```bash
# Verify all tests still pass
UV_CACHE_DIR=.uv_cache uv run pytest tests/mcp_tests/ -v

# Verify linting is clean
uv run ruff check src/fs2/mcp/ tests/mcp_tests/

# Re-run code review
# /plan-7-code-review --phase "Phase 1: Core Infrastructure" --plan "/workspaces/flow_squared/docs/plans/011-mcp/mcp-plan.md"
```

---

## Acceptance Criteria

Phase 1 will be APPROVED when:
- [ ] FIX-001 implemented (logging in dependencies.py)
- [ ] FIX-002 implemented (logging in translate_error)
- [ ] All 21+ tests passing
- [ ] No HIGH severity findings in re-review

---

*Generated by Claude Code (plan-7-code-review) on 2025-12-29*
