"""Remote client for querying fs2 server endpoints.

Provides RemoteClient (single server) and MultiRemoteClient (fan-out across
multiple servers) for the CLI and MCP remote mode.

Per DYK-P5-01: Uses async httpx.AsyncClient (not sync) to avoid blocking
the MCP event loop. CLI wraps calls with asyncio.run().

Per DYK #1/#2: Does NOT implement GraphStore ABC. Returns raw server JSON
dicts — no CodeNode reconstruction needed.

Usage:
    ```python
    # Single remote
    client = RemoteClient(base_url="https://fs2.example.com")
    result = await client.tree("my-graph", pattern="src/")

    # Multi-remote
    multi = MultiRemoteClient([client1, client2])
    results = await multi.search("auth", mode="auto")
    ```
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Default timeout for remote requests (seconds)
DEFAULT_TIMEOUT = 30.0


class RemoteClientError(Exception):
    """Error communicating with a remote fs2 server.

    Always includes actionable context: remote name/URL and what to do.
    """

    def __init__(self, message: str, remote_name: str | None = None, url: str | None = None) -> None:
        self.remote_name = remote_name
        self.url = url
        super().__init__(message)


class RemoteClient:
    """Async HTTP client for a single fs2 server.

    Calls server REST API endpoints directly and returns raw JSON dicts.
    Does NOT implement GraphStore ABC (DYK #1).

    Attributes:
        base_url: Server base URL (no trailing slash).
        api_key: Optional API key for Bearer auth.
        name: Optional human-readable name (e.g., "work") for error messages.
        _timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        name: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.name = name or base_url
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        """Build request headers with optional auth."""
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _client(self) -> httpx.AsyncClient:
        """Create a fresh async client for a request."""
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=self._timeout,
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an HTTP request and return parsed JSON.

        Translates HTTP errors into actionable RemoteClientError messages.
        """
        async with self._client() as client:
            try:
                response = await client.request(method, path, **kwargs)
            except httpx.ConnectError:
                raise RemoteClientError(
                    f"Remote '{self.name}' unreachable at {self.base_url}. "
                    "Check the URL and ensure the server is running.",
                    remote_name=self.name,
                    url=self.base_url,
                ) from None
            except httpx.TimeoutException:
                raise RemoteClientError(
                    f"Request to remote '{self.name}' timed out after {self._timeout}s. "
                    "The server may be overloaded. Try again or increase timeout.",
                    remote_name=self.name,
                    url=self.base_url,
                ) from None
            except httpx.HTTPError as e:
                raise RemoteClientError(
                    f"Network error contacting remote '{self.name}': {e}",
                    remote_name=self.name,
                    url=self.base_url,
                ) from None

        # Handle HTTP status errors
        if response.status_code == 401:
            raise RemoteClientError(
                f"Authentication failed for remote '{self.name}'. "
                "Check your API key in remotes config.",
                remote_name=self.name,
                url=self.base_url,
            )
        if response.status_code == 404:
            # Extract detail from JSON if possible
            try:
                detail = response.json().get("detail", "Resource not found")
            except Exception:
                detail = "Resource not found"
            raise RemoteClientError(
                f"Not found on remote '{self.name}': {detail}",
                remote_name=self.name,
                url=self.base_url,
            )
        if response.status_code == 503:
            try:
                detail = response.json().get("detail", "Service unavailable")
            except Exception:
                detail = "Service unavailable"
            raise RemoteClientError(
                f"Remote '{self.name}' service unavailable: {detail}. "
                "The server may be starting up or missing configuration.",
                remote_name=self.name,
                url=self.base_url,
            )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise RemoteClientError(
                f"Remote '{self.name}' returned error {response.status_code}: {detail}",
                remote_name=self.name,
                url=self.base_url,
            )

        return response.json()

    # ── Public API — returns raw server JSON dicts ──

    async def list_graphs(self, status: str | None = "ready") -> dict:
        """List graphs on the remote server.

        Args:
            status: Optional filter (e.g., "ready"). Default filters to ready graphs.

        Returns:
            Server JSON: {"graphs": [...], "count": N}
        """
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        return await self._request("GET", "/api/v1/graphs", params=params)

    async def tree(
        self,
        graph: str,
        pattern: str = ".",
        max_depth: int = 0,
    ) -> dict:
        """Get tree view from remote server.

        Per DYK-P5-02: Returns server JSON directly. CLI uses format=text
        for pre-rendered output.

        Args:
            graph: Graph name on the server.
            pattern: Filter pattern (default: ".").
            max_depth: Max depth (0=unlimited).

        Returns:
            Server JSON tree response.
        """
        params: dict[str, Any] = {"pattern": pattern, "max_depth": max_depth}
        return await self._request("GET", f"/api/v1/graphs/{graph}/tree", params=params)

    async def search(
        self,
        pattern: str,
        *,
        graph: str | None = None,
        mode: str = "auto",
        limit: int = 20,
        offset: int = 0,
        detail: str = "min",
        include: str | None = None,
        exclude: str | None = None,
    ) -> dict:
        """Search on remote server.

        If graph is specified, searches single graph. Otherwise searches all.

        Args:
            pattern: Search pattern.
            graph: Optional graph name (None = search all).
            mode: Search mode (auto/text/regex/semantic).
            limit: Max results.
            offset: Pagination offset.
            detail: Detail level (min/max).
            include: Comma-separated include patterns.
            exclude: Comma-separated exclude patterns.

        Returns:
            Server JSON search envelope: {"meta": {...}, "results": [...]}
        """
        params: dict[str, Any] = {
            "pattern": pattern,
            "mode": mode,
            "limit": limit,
            "offset": offset,
            "detail": detail,
        }
        if include:
            params["include"] = include
        if exclude:
            params["exclude"] = exclude

        if graph:
            return await self._request("GET", f"/api/v1/graphs/{graph}/search", params=params)
        else:
            params["graph"] = "all"
            return await self._request("GET", "/api/v1/search", params=params)

    async def get_node(
        self,
        graph: str,
        node_id: str,
        detail: str = "min",
    ) -> dict | None:
        """Get a single node from remote server.

        Args:
            graph: Graph name.
            node_id: Node ID (may contain / and :).
            detail: Detail level (min/max).

        Returns:
            Server JSON node dict, or None if not found.
        """
        params: dict[str, Any] = {"detail": detail}
        try:
            return await self._request(
                "GET", f"/api/v1/graphs/{graph}/nodes/{node_id}", params=params,
            )
        except RemoteClientError as e:
            if "Not found" in str(e):
                return None
            raise


class MultiRemoteClient:
    """Fan-out client across multiple remote servers.

    Merges results from N RemoteClient instances. Partial failures
    log warnings but don't abort the entire operation (DYK Workshop R8).

    Per DYK-P5-04: Cross-remote score comparability is a known v1 limitation.
    Results are merged and sorted by score — text/regex scores are consistent;
    cosine similarity is comparable across graph sizes.
    """

    def __init__(self, clients: list[RemoteClient]) -> None:
        self.clients = clients

    async def search(
        self,
        pattern: str,
        *,
        graph: str | None = None,
        mode: str = "auto",
        limit: int = 20,
        offset: int = 0,
        detail: str = "min",
        include: str | None = None,
        exclude: str | None = None,
    ) -> dict:
        """Search across all remotes, merge results by score.

        Partial failures warn on stderr and continue with successful remotes.

        Returns:
            Merged search envelope with results re-sorted by score.
        """
        import asyncio
        import sys

        tasks = [
            client.search(
                pattern,
                graph=graph,
                mode=mode,
                limit=limit,
                offset=offset,
                detail=detail,
                include=include,
                exclude=exclude,
            )
            for client in self.clients
        ]

        results_per_remote = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[dict] = []
        for client, result in zip(self.clients, results_per_remote, strict=True):
            if isinstance(result, Exception):
                print(
                    f"Warning: Remote '{client.name}' failed: {result}",
                    file=sys.stderr,
                )
                continue
            if isinstance(result, dict) and "results" in result:
                # Tag each result with its source remote
                for r in result["results"]:
                    r["_remote"] = client.name
                all_results.extend(result["results"])

        # Sort merged results by score (descending)
        all_results.sort(key=lambda r: r.get("score", 0), reverse=True)

        # Apply limit to merged results
        limited = all_results[:limit]

        return {
            "meta": {
                "total": len(all_results),
                "showing": {"from": 0, "to": len(limited), "count": len(limited)},
                "pagination": {"limit": limit, "offset": 0},
                "folders": {},
                "remotes": [c.name for c in self.clients],
            },
            "results": limited,
        }

    async def list_graphs(self, status: str | None = "ready") -> dict:
        """List graphs from all remotes, merged.

        Returns:
            Merged graphs list with remote source tagged.
        """
        import asyncio
        import sys

        tasks = [client.list_graphs(status=status) for client in self.clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_graphs: list[dict] = []
        for client, result in zip(self.clients, results, strict=True):
            if isinstance(result, Exception):
                print(
                    f"Warning: Remote '{client.name}' failed: {result}",
                    file=sys.stderr,
                )
                continue
            if isinstance(result, dict) and "graphs" in result:
                for g in result["graphs"]:
                    g["_remote"] = client.name
                all_graphs.extend(result["graphs"])

        return {
            "graphs": all_graphs,
            "count": len(all_graphs),
        }
