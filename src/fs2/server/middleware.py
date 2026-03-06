"""Structured request logging middleware for fs2 server.

Logs every HTTP request as structured JSON for monitoring and observability.
Skips noisy endpoints (/health) to avoid log spam.

AC24: Structured request logging for all HTTP requests.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("fs2.server.access")

# Paths to exclude from access logging (noisy health checks)
SKIP_PATHS = frozenset({"/health"})


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log structured request metrics for every HTTP request.

    Emits: method, path, status_code, duration_ms, content_length.
    Uses standard Python logging — compatible with JSON formatters.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        content_length = response.headers.get("content-length", "-")

        logger.info(
            "%(method)s %(path)s %(status)s %(duration)sms %(size)s",
            {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration": duration_ms,
                "size": content_length,
            },
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "content_length": content_length,
                "query": str(request.query_params) if request.query_params else None,
            },
        )

        return response
