"""Health check endpoint for fs2 server.

AC23: Returns server status, database connectivity, and graph count.
"""

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict:
    """Check server health, database connectivity, and graph count.

    Returns:
        JSON with status, db connectivity, and ready graph count.
        Degrades gracefully if the database is unreachable.
    """
    db = request.app.state.db

    if not db.is_connected:
        return {
            "status": "degraded",
            "db": "disconnected",
            "graphs": None,
        }

    try:
        async with db.connection() as conn:
            result = await conn.execute("SELECT 1")
            await result.fetchone()

            result = await conn.execute(
                "SELECT count(*) FROM graphs WHERE status = 'ready'"
            )
            row = await result.fetchone()
            graph_count = row[0] if row else 0

        return {
            "status": "ok",
            "db": "connected",
            "graphs": graph_count,
        }
    except Exception:
        return {
            "status": "degraded",
            "db": "error",
            "graphs": None,
        }
