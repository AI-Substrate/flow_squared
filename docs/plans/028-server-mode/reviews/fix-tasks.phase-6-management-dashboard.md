# Fix Tasks: Phase 6: Management Dashboard

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Stop endless dashboard polling
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/graphs/list.html; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/graphs/_table.html; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_dashboard.py
- **Issue**: Once the graphs page first renders with a pending/ingesting graph, the HTMX polling attributes stay on `#graph-table-container` forever because `/dashboard/graphs/table` only returns a table fragment and never re-renders the wrapper attributes.
- **Fix**: Return/re-render a polling container fragment (or use an out-of-band attribute update) so `hx-get` / `hx-trigger` are removed when `has_pending` becomes false. Add a regression test that proves polling starts when pending rows exist and stops when all rows settle.
- **Patch hint**:
  ```diff
  - <div id="graph-table-container" {% if has_pending %} hx-get="/dashboard/graphs/table" hx-trigger="every 5s" hx-swap="innerHTML" {% endif %}>
  -     {% include "graphs/_table.html" %}
  - </div>
  + {% include "graphs/_table_container.html" %}
  ```
  ```diff
  - return templates.TemplateResponse(request, "graphs/_table.html", context)
  + return templates.TemplateResponse(request, "graphs/_table_container.html", context)
  ```

### FT-002: Reconcile tenant-management scope with AC18
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/tasks.md; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/settings/keys.html; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_dashboard.py
- **Issue**: The governing artifacts still promise “create tenants and generate API keys through the dashboard,” but Phase 6 only exposes API-key CRUD for a single default tenant.
- **Fix**: Choose one path before re-review: **(a)** implement tenant creation UI/routes/tests for Phase 6, or **(b)** formally defer tenant creation by updating the spec/plan/phase artifacts and execution evidence so AC18 no longer claims it is delivered here.
- **Patch hint**:
  ```diff
  - - **AC18**: A server operator can create tenants and generate API keys through the dashboard
  + - **AC18**: A server operator can generate API keys through the dashboard; tenant creation remains deferred until the auth phase lands
  ```

### FT-003: Add tenant and graph context to structured access logs
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/middleware.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_middleware.py; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/execution.log.md
- **Issue**: `AccessLogMiddleware` and its tests cover method/path/status/duration/content_length, but AC24/T007 require tenant and graph context too.
- **Fix**: Attach tenant and graph identifiers to the structured `extra` payload (use the active/default tenant model until auth lands) and add caplog assertions for those fields.
- **Patch hint**:
  ```diff
    extra={
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
        "content_length": content_length,
  +     "tenant": getattr(request.state, "tenant_id", DEFAULT_TENANT_ID),
  +     "graph": request.path_params.get("graph_id"),
        "query": str(request.query_params) if request.query_params else None,
    }
  ```

### FT-004: Rebaseline server/auth domain artifacts
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/auth/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md
- **Issue**: The domain map and server/auth domain docs still describe active AuthService/auth middleware contracts even though `src/fs2/auth/` does not exist and Phase 6 keeps API-key CRUD in the server domain.
- **Fix**: Update the docs so auth is clearly marked as planned/deferred, server’s temporary ownership of minimal API-key logic is explicit, and the live server→auth edge is no longer shown as an active solid dependency.
- **Patch hint**:
  ```diff
  - server -->|AuthService + API key middleware| auth
  + server -.->|planned AuthService extraction| auth
  ```
  ```diff
  - - **auth** — AuthService, middleware for request validation
  + - **auth** — planned extraction target for tenant/API-key enforcement (not yet implemented)
  ```

## Medium / Low Fixes

### FT-005: Add concrete upload, polling, and logging evidence
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_dashboard.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_middleware.py; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/execution.log.md
- **Issue**: The current evidence does not prove multipart upload POST behavior, oversize rejection, polling-stop behavior, or the full AC24 log contract.
- **Fix**: Add dashboard upload success/failure/oversize tests, polling stop-condition assertions, and tenant/graph logging tests. Update `execution.log.md` with the exact commands and representative outputs that demonstrate those behaviors.
- **Patch hint**:
  ```diff
  + async def test_dashboard_upload_success(...): ...
  + async def test_dashboard_upload_rejects_oversize_file(...): ...
  + async def test_graph_list_polling_stops_when_settled(...): ...
  + async def test_middleware_logs_tenant_and_graph(...): ...
  ```

### FT-006: Stop hiding dashboard-home query failures
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/index.html
- **Issue**: `dashboard_home()` swallows all exceptions and renders zero counts, which makes a broken DB/query path look like a healthy empty system.
- **Fix**: Log the exception and render an explicit error state (or a non-200 response) so operators can tell the dashboard is unhealthy.
- **Patch hint**:
  ```diff
  - except Exception:
  -     pass
  + except Exception as exc:
  +     logger.exception("Failed to load dashboard counts")
  +     return templates.TemplateResponse(request, "index.html", {"graph_count": 0, "ingesting_count": 0, "error": "Unable to load dashboard counts."}, status_code=503)
  ```

### FT-007: Extract shared graph-management helpers
- **Severity**: LOW
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py
- **Issue**: Dashboard list/upload/delete paths duplicate logic that already exists in the API routes, including a second default-tenant bootstrap implementation.
- **Fix**: Pull shared tenant bootstrap / graph CRUD/query helpers into a common internal module (or a reused service function) and call that from both dashboard and API surfaces.
- **Patch hint**:
  ```diff
  - async def _ensure_default_tenant(db): ...
  + from fs2.server.graph_admin import ensure_default_tenant
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
