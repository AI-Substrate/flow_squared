"""Dashboard routes for fs2 server management UI.

HTMX-powered server-rendered views for:
- Graph list with status monitoring
- Graph upload with progress feedback
- Graph deletion with confirmation
- API key generation and management
"""

import hashlib
import logging
import os
import secrets
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from fs2.server.graph_admin import DEFAULT_TENANT_ID, ensure_default_tenant
from fs2.server.ingestion import IngestionError, IngestionPipeline

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _fetch_graphs(db) -> tuple[list[dict], bool]:
    """Fetch all graphs with display-formatted fields.

    Returns (graphs_list, has_pending) where has_pending indicates
    whether HTMX polling should be active.
    """
    async with db.connection() as conn:
        result = await conn.execute(
            """SELECT id, name, description, status, node_count, edge_count,
                    embedding_model, updated_at
                FROM graphs ORDER BY name"""
        )
        rows = await result.fetchall()

    has_pending = False
    graphs = []
    for row in rows:
        status = row[3]
        if status in ("pending", "ingesting"):
            has_pending = True
        updated = row[7]
        graphs.append({
            "id": str(row[0]),
            "name": row[1],
            "description": row[2],
            "status": status,
            "node_count": row[4],
            "edge_count": row[5],
            "embedding_model": row[6],
            "updated_at_display": updated.strftime("%Y-%m-%d %H:%M") if updated else "—",
        })
    return graphs, has_pending


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request) -> HTMLResponse:
    """Dashboard home page — overview and navigation."""
    db = request.app.state.db

    graph_count = 0
    ingesting_count = 0
    db_error = None
    try:
        async with db.connection() as conn:
            result = await conn.execute(
                "SELECT count(*) FROM graphs WHERE status = 'ready'"
            )
            row = await result.fetchone()
            graph_count = row[0] if row else 0

            result = await conn.execute(
                "SELECT count(*) FROM graphs WHERE status IN ('pending', 'ingesting')"
            )
            row = await result.fetchone()
            ingesting_count = row[0] if row else 0
    except Exception:
        logger.exception("Failed to load dashboard counts")
        db_error = "Unable to load dashboard data. Check database connectivity."

    return templates.TemplateResponse(request, "index.html", {
            "graph_count": graph_count,
            "ingesting_count": ingesting_count,
            "db_error": db_error,
        },
    )


@router.get("/graphs", response_class=HTMLResponse)
async def graph_list(request: Request) -> HTMLResponse:
    """Graph list view — table with status badges and metadata."""
    db = request.app.state.db
    graphs, has_pending = await _fetch_graphs(db)

    return templates.TemplateResponse(request, "graphs/list.html", {
            "graphs": graphs,
            "has_pending": has_pending,
        },
    )


@router.get("/graphs/table", response_class=HTMLResponse)
async def graph_table_partial(request: Request) -> HTMLResponse:
    """HTMX partial — returns just the table body for polling refresh."""
    db = request.app.state.db
    graphs, has_pending = await _fetch_graphs(db)

    return templates.TemplateResponse(request, "graphs/_table_container.html", {
            "graphs": graphs,
            "has_pending": has_pending,
        },
    )


@router.get("/graphs/upload", response_class=HTMLResponse)
async def graph_upload_form(request: Request) -> HTMLResponse:
    """Graph upload form — file picker with name/description fields."""
    return templates.TemplateResponse(request, "graphs/upload.html", {"error": None, "success": None},
    )


@router.post("/graphs/upload", response_class=HTMLResponse)
async def graph_upload(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str | None = Form(None),
    source_url: str | None = Form(None),
) -> HTMLResponse:
    """Handle graph upload — stream to temp, ingest, show result.

    Uses same IngestionPipeline as the API endpoint (DYK-P6-06).
    """
    db = request.app.state.db
    upload_dir = getattr(request.app.state, "upload_dir", "/tmp/fs2-uploads")
    os.makedirs(upload_dir, exist_ok=True)
    temp_path = Path(upload_dir) / f"{uuid.uuid4()}.pickle"

    try:
        # Stream to temp file with size limit
        max_bytes = getattr(request.app.state, "max_upload_bytes", 524_288_000)
        bytes_written = 0
        with open(temp_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    return templates.TemplateResponse(request, "graphs/upload.html", {
                            "error": f"File exceeds maximum size ({max_bytes // 1048576} MB)",
                            "success": None,
                        },
                    )
                f.write(chunk)

        await ensure_default_tenant(db)

        pipeline = IngestionPipeline(db)
        result = await pipeline.ingest(
            pickle_path=temp_path,
            graph_name=name,
            tenant_id=DEFAULT_TENANT_ID,
            description=description,
            source_url=source_url,
        )

        logger.info("Dashboard upload: %s (%d nodes)", name, result.node_count)

        return templates.TemplateResponse(request, "graphs/upload.html", {
                "error": None,
                "success": {
                    "name": name,
                    "node_count": result.node_count,
                    "edge_count": result.edge_count,
                },
            },
        )

    except IngestionError as e:
        return templates.TemplateResponse(request, "graphs/upload.html", {"error": str(e), "success": None},
        )
    except Exception as e:
        logger.exception("Dashboard upload failed")
        return templates.TemplateResponse(request, "graphs/upload.html", {
                "error": f"Unexpected error: {e}",
                "success": None,
            },
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.delete("/graphs/{graph_id}", response_class=HTMLResponse)
async def graph_delete(request: Request, graph_id: str) -> HTMLResponse:
    """Delete a graph — returns empty string for HTMX row removal."""
    db = request.app.state.db

    async with db.connection() as conn:
        result = await conn.execute(
            "SELECT name FROM graphs WHERE id = %s", (graph_id,)
        )
        row = await result.fetchone()
        if not row:
            return HTMLResponse(
                content="<tr><td colspan='7'>Graph not found</td></tr>",
                status_code=404,
            )

        graph_name = row[0]
        await conn.execute("DELETE FROM graphs WHERE id = %s", (graph_id,))
        await conn.commit()

    logger.info("Dashboard delete: %s (%s)", graph_name, graph_id)
    # Return empty string — HTMX outerHTML swap removes the row
    return HTMLResponse(content="", status_code=200)


# --- API Key Management ---


def _generate_api_key() -> tuple[str, str, str]:
    """Generate an API key with prefix, full key, and SHA-256 hash.

    Returns (full_key, key_prefix, key_hash).
    Key format: fs2_<32 hex chars> (128 bits of entropy).
    Hash: SHA-256 — appropriate for high-entropy tokens (DYK-P6-10).
    """
    raw = secrets.token_hex(16)
    full_key = f"fs2_{raw}"
    key_prefix = full_key[:12]
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_prefix, key_hash


async def _fetch_api_keys(db) -> list[dict]:
    """Fetch all active API keys for display."""
    async with db.connection() as conn:
        result = await conn.execute(
            """SELECT id, name, key_prefix, scope, is_active, last_used_at, created_at
                FROM api_keys WHERE is_active = true
                ORDER BY created_at DESC"""
        )
        rows = await result.fetchall()

    keys = []
    for row in rows:
        created = row[6]
        last_used = row[5]
        keys.append({
            "id": str(row[0]),
            "name": row[1],
            "key_prefix": row[2],
            "scope": row[3],
            "created_at_display": created.strftime("%Y-%m-%d %H:%M") if created else "—",
            "last_used_display": last_used.strftime("%Y-%m-%d %H:%M") if last_used else "Never",
        })
    return keys


@router.get("/settings/keys", response_class=HTMLResponse)
async def api_keys_page(request: Request) -> HTMLResponse:
    """API key management page — list keys + generate form."""
    db = request.app.state.db
    keys = await _fetch_api_keys(db)

    return templates.TemplateResponse(request, "settings/keys.html", {
            "keys": keys,
            "new_key": None,
            "new_key_name": None,
            "new_key_scope": None,
            "error": None,
        },
    )


@router.post("/settings/keys", response_class=HTMLResponse)
async def api_key_generate(
    request: Request,
    name: str = Form(...),
    scope: str = Form("read"),
) -> HTMLResponse:
    """Generate a new API key — shows full key once."""
    db = request.app.state.db

    if scope not in ("read", "write", "admin"):
        scope = "read"

    full_key, key_prefix, key_hash = _generate_api_key()

    await ensure_default_tenant(db)

    async with db.connection() as conn:
        await conn.execute(
            """INSERT INTO api_keys (tenant_id, key_hash, key_prefix, name, scope)
                VALUES (%s, %s, %s, %s, %s)""",
            (DEFAULT_TENANT_ID, key_hash, key_prefix, name, scope),
        )
        await conn.commit()

    logger.info("API key generated: %s (scope=%s, prefix=%s)", name, scope, key_prefix)

    keys = await _fetch_api_keys(db)

    return templates.TemplateResponse(request, "settings/keys.html", {
            "keys": keys,
            "new_key": full_key,
            "new_key_name": name,
            "new_key_scope": scope,
            "error": None,
        },
    )


@router.post("/settings/keys/{key_id}/revoke", response_class=HTMLResponse)
async def api_key_revoke(request: Request, key_id: str) -> HTMLResponse:
    """Revoke an API key — HTMX removes row."""
    db = request.app.state.db

    async with db.connection() as conn:
        await conn.execute(
            "UPDATE api_keys SET is_active = false WHERE id = %s",
            (key_id,),
        )
        await conn.commit()

    logger.info("API key revoked: %s", key_id)
    return HTMLResponse(content="", status_code=200)
