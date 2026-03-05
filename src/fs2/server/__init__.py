"""fs2 Server — HTTP server for hosting code intelligence graphs.

This package provides a FastAPI application that serves pre-scanned
code graphs via REST API, with PostgreSQL + pgvector storage.
"""

from fs2.server.app import create_app

__all__ = ["create_app"]
