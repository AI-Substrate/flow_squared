"""Dashboard package for fs2 server management UI.

Provides an HTMX + Jinja2 + Alpine.js web interface for graph management,
API key provisioning, and server monitoring. Mounted at /dashboard/.
"""

from fs2.server.dashboard.routes import router

__all__ = ["router"]
