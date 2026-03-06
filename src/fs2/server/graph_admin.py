"""Shared graph administration helpers for fs2 server.

Used by both the API routes (routes/graphs.py) and the dashboard
routes (dashboard/routes.py) to avoid duplicating tenant bootstrap
and common graph queries.
"""

# Default tenant for v1 (no multi-tenancy)
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"


async def ensure_default_tenant(db) -> None:
    """Create the default tenant if it doesn't exist.

    Idempotent — safe to call on every upload.
    """
    async with db.connection() as conn:
        await conn.execute(
            """INSERT INTO tenants (id, name, slug)
            VALUES (%s, 'default', 'default')
            ON CONFLICT (id) DO NOTHING""",
            (DEFAULT_TENANT_ID,),
        )
        await conn.commit()
