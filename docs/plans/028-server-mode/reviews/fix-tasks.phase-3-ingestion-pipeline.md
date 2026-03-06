# Fix Tasks: Phase 3: Ingestion Pipeline + Graph Upload

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Fix multipart upload contract fields
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py
- **Issue**: Upload metadata (`name`, `description`, `source_url`) is currently bound as query params instead of multipart form fields.
- **Fix**: Annotate upload fields with `Form(...)` and file with `File(...)`; keep behavior consistent with phase task contract.
- **Patch hint**:
  ```diff
  -from fastapi import APIRouter, HTTPException, Request, UploadFile
  +from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
   
   @router.post("")
   async def upload_graph(
       request: Request,
  -    file: UploadFile,
  -    name: str,
  -    description: str | None = None,
  -    source_url: str | None = None,
  +    file: UploadFile = File(...),
  +    name: str = Form(...),
  +    description: str | None = Form(None),
  +    source_url: str | None = Form(None),
   ) -> dict:
  ```

### FT-002: Make ingestion failure path transaction-safe
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/ingestion.py
- **Issue**: On COPY/SQL failure, code tries to update `graphs.status='error'` in the same possibly aborted transaction.
- **Fix**: `rollback()` failed transaction first, then update error status in a clean transaction/connection, then raise `IngestionError`.
- **Patch hint**:
  ```diff
   except Exception as e:
  -    await conn.execute(
  -        "UPDATE graphs SET status = 'error', updated_at = now() WHERE id = %s",
  -        (graph_id,),
  -    )
  -    await conn.commit()
  +    await conn.rollback()
  +    async with self._db.connection() as err_conn:
  +        await err_conn.execute(
  +            "UPDATE graphs SET status = 'error', updated_at = now() WHERE id = %s",
  +            (graph_id,),
  +        )
  +        await err_conn.commit()
       raise IngestionError(f"Ingestion failed: {e}") from e
  ```

### FT-003: Remove graph-storage -> server coupling and satisfy GraphStore contract
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/graph_store_pg.py
- **Issue**: `PostgreSQLGraphStore` directly imports `fs2.server.database.Database` and required sync read methods currently raise `NotImplementedError`.
- **Fix**: Depend on a neutral protocol/port for DB access (or move implementation to server infra), and provide contract-appropriate read method behavior (or separate async interface from `GraphStore`).
- **Patch hint**:
  ```diff
  -from fs2.server.database import Database
  +from typing import Protocol
  +
  +class ConnectionProvider(Protocol):
  +    async def connection(self): ...
   
  -class PostgreSQLGraphStore(GraphStore):
  -    def __init__(self, db: Database, graph_id: str) -> None:
  +class PostgreSQLGraphStore(GraphStore):
  +    def __init__(self, db: ConnectionProvider, graph_id: str) -> None:
           self._db = db
           self._graph_id = graph_id
  ```

### FT-004: Add missing phase-critical tests (including PG store parity file)
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_graph_upload.py, /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_ingestion.py, /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_graph_store_pg.py
- **Issue**: Tests do not verify upload behavior, re-upload replacement semantics, status transitions, or PostgreSQLGraphStore round-trip parity.
- **Fix**: Add behavior tests for `POST /api/v1/graphs`, status lifecycle, re-upload full replace/no-orphan rows, and field-by-field CodeNode parity through PG store.
- **Patch hint**:
  ```diff
  +# tests/server/test_graph_store_pg.py
  +async def test_given_ingested_graph_when_get_node_then_fields_round_trip(...):
  +    ...
  +
  +# tests/server/test_graph_upload.py
  +async def test_given_valid_multipart_when_upload_then_ready_response(...):
  +    ...
  +
  +async def test_given_existing_graph_when_reupload_then_old_rows_removed(...):
  +    ...
  ```

### FT-005: Update domain artifacts to match implemented dependencies
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md, /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md, /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md
- **Issue**: Domain docs/map/manifest do not fully represent changed files and current dependency edges.
- **Fix**: Sync Contracts/Composition/Source tables, map edges/labels, and Domain Manifest entries for all touched files.
- **Patch hint**:
  ```diff
  +| `src/fs2/core/repos/pickle_security.py` | contract | RestrictedUnpickler public contract |
  +| `tests/server/test_graph_upload.py` | server | internal | Endpoint behavior coverage |
  ...
  -server -->|PostgreSQLGraphStore| graphstore
  +server -->|PostgreSQLGraphStore| graphstore
  +graphstore -.->|Database contract (if intentional)| server
  ```

## Medium / Low Fixes

### FT-006: Enforce configured upload size limits
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py
- **Issue**: `ServerStorageConfig.max_upload_bytes` is not enforced during stream write.
- **Fix**: Count streamed bytes and return HTTP 413 once limit exceeded; always delete temp file.

### FT-007: Consolidate duplicate pickle-loading semantics
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/ingestion.py, /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/graph_store_impl.py
- **Issue**: Pickle loading/validation behavior is partly duplicated.
- **Fix**: Extract shared helper/contract function for common validation path.

### FT-008: Improve execution evidence traceability
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-3-ingestion-pipeline/execution.log.md
- **Issue**: Log includes summary counts but not reproducible command outputs or AC-level mapping.
- **Fix**: Append exact commands/results and AC↔test evidence table.

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
