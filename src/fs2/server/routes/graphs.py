"""Graph management routes for fs2 server.

Endpoints:
- POST /api/v1/graphs — upload a graph pickle file
- GET  /api/v1/graphs — list all graphs
- GET  /api/v1/graphs/{graph_id}/status — graph status
- DELETE /api/v1/graphs/{graph_id} — delete a graph
"""

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from fs2.server.graph_admin import DEFAULT_TENANT_ID, ensure_default_tenant
from fs2.server.ingestion import IngestionError, IngestionPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/graphs", tags=["graphs"])


@router.post("")
async def upload_graph(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str | None = Form(None),
    source_url: str | None = Form(None),
) -> dict:
    """Upload a graph pickle file for ingestion.

    Streams file to temp disk, ingests synchronously, returns when ready.
    """
    db = request.app.state.db
    upload_dir = getattr(request.app.state, "upload_dir", "/tmp/fs2-uploads")

    os.makedirs(upload_dir, exist_ok=True)
    temp_path = Path(upload_dir) / f"{uuid.uuid4()}.pickle"

    try:
        # Stream to temp file with size limit enforcement
        max_bytes = getattr(request.app.state, "max_upload_bytes", 524_288_000)
        bytes_written = 0
        with open(temp_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeds maximum size of {max_bytes} bytes",
                    )
                f.write(chunk)

        pipeline = IngestionPipeline(db)

        await ensure_default_tenant(db)

        result = await pipeline.ingest(
            pickle_path=temp_path,
            graph_name=name,
            tenant_id=DEFAULT_TENANT_ID,
            description=description,
            source_url=source_url,
        )

        return {
            "graph_id": result.graph_id,
            "name": name,
            "status": "ready",
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "chunk_count": result.chunk_count,
        }

    except IngestionError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.get("")
async def list_graphs(
    request: Request,
    status: str | None = None,
) -> dict:
    """List all available graphs with status and metadata.

    Args:
        status: Optional filter (e.g. 'ready') for query-eligible graphs.
    """
    db = request.app.state.db

    if status:
        query = """SELECT id, name, description, status, node_count, edge_count,
                embedding_model, embedding_dimensions, format_version,
                created_at, updated_at, ingested_at
            FROM graphs WHERE status = %s
            ORDER BY name"""
        params = (status,)
    else:
        query = """SELECT id, name, description, status, node_count, edge_count,
                embedding_model, embedding_dimensions, format_version,
                created_at, updated_at, ingested_at
            FROM graphs
            ORDER BY name"""
        params = None

    async with db.connection() as conn:
        if params:
            result = await conn.execute(query, params)
        else:
            result = await conn.execute(query)
        rows = await result.fetchall()

    graphs = []
    for row in rows:
        graphs.append({
            "id": str(row[0]),
            "name": row[1],
            "description": row[2],
            "status": row[3],
            "node_count": row[4],
            "edge_count": row[5],
            "embedding_model": row[6],
            "embedding_dimensions": row[7],
            "format_version": row[8],
            "created_at": row[9].isoformat() if row[9] else None,
            "updated_at": row[10].isoformat() if row[10] else None,
            "ingested_at": row[11].isoformat() if row[11] else None,
        })

    return {"graphs": graphs, "count": len(graphs)}


@router.get("/{graph_id}/status")
async def graph_status(request: Request, graph_id: str) -> dict:
    """Get the current status of a graph."""
    db = request.app.state.db

    async with db.connection() as conn:
        result = await conn.execute(
            """SELECT id, name, status, node_count, edge_count, ingested_at
            FROM graphs WHERE id = %s""",
            (graph_id,),
        )
        row = await result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Graph {graph_id} not found")

    return {
        "id": str(row[0]),
        "name": row[1],
        "status": row[2],
        "node_count": row[3],
        "edge_count": row[4],
        "ingested_at": row[5].isoformat() if row[5] else None,
    }


@router.delete("/{graph_id}")
async def delete_graph(request: Request, graph_id: str) -> dict:
    """Delete a graph and all associated data."""
    db = request.app.state.db

    async with db.connection() as conn:
        result = await conn.execute(
            "SELECT name FROM graphs WHERE id = %s", (graph_id,)
        )
        row = await result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Graph {graph_id} not found")

        graph_name = row[0]
        # CASCADE deletes code_nodes, node_edges, embedding_chunks
        await conn.execute("DELETE FROM graphs WHERE id = %s", (graph_id,))
        await conn.commit()

    return {"deleted": graph_id, "name": graph_name}
