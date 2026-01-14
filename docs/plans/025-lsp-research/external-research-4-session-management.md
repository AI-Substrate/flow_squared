# External Research: LSP Session Management for Large Codebases

> **Research Date**: 2026-01-14
> **Research Tool**: Perplexity Deep Research
> **Context**: fs2 (Flowspace2) - Python code intelligence tool for cross-file relationship extraction

---

## Executive Summary

This research investigates best practices for managing LSP server lifecycle during batch operations across large codebases (1000+ files). Key findings include:

1. **Lifecycle Pattern**: Use single server instance per scan, properly initialized before queries, gracefully shut down after
2. **Batching Strategy**: Group requests by file to leverage server caching; use semaphore-based throttling (3-5 concurrent requests)
3. **Memory Management**: Monitor per-server memory; restart servers exceeding thresholds; expect 200-2500MB per server
4. **Initialization**: Expect 10-30 seconds startup; leverage file-based caching where available (gopls v0.12+)
5. **Resilience**: Implement per-request timeouts (30s), retries with exponential backoff, graceful degradation

---

## Table of Contents

1. [LSP Protocol Fundamentals](#1-lsp-protocol-fundamentals)
2. [Lifecycle Management for Batch Operations](#2-lifecycle-management-for-batch-operations)
3. [Request Batching and Query Optimization](#3-request-batching-and-query-optimization)
4. [Throttling and Rate Limiting](#4-throttling-and-rate-limiting)
5. [Memory Management Strategies](#5-memory-management-strategies)
6. [Workspace Initialization Performance](#6-workspace-initialization-performance)
7. [Large-Scale Analysis Architecture](#7-large-scale-analysis-architecture)
8. [Failure Handling and Resilience](#8-failure-handling-and-resilience)
9. [Performance Benchmarks](#9-performance-benchmarks)
10. [Common Pitfalls and Solutions](#10-common-pitfalls-and-solutions)
11. [Practical Code Examples](#11-practical-code-examples)

---

## 1. LSP Protocol Fundamentals

### Lifecycle Model

The Language Server Protocol establishes a well-defined lifecycle model where **the client controls the server lifetime**, starting it as a subprocess and managing its shutdown through specific protocol messages.

**Lifecycle Sequence**:
```
Client                              Server
   |                                   |
   |------ initialize request -------->|
   |<----- initialize response --------|
   |------ initialized notification -->|
   |                                   |
   |<==== bidirectional messages =====>|
   |                                   |
   |------ shutdown request --------->|
   |<----- shutdown response ---------|
   |------ exit notification -------->|
   |                                   X (process terminates)
```

### Ordering Guarantees

The LSP specification states that responses should generally be sent in the same order as requests appear, though servers may use parallel execution strategies provided reordering does not affect correctness.

**Safe to Reorder**:
- Completion and signature help requests (independent operations)
- Hover requests across different positions

**Must Preserve Order**:
- Definition followed by rename operations
- Any sequence where earlier results affect later queries

### JSON-RPC Over Stdio

The transport mechanism uses content-length prefixed messages:

```
Content-Length: 123\r\n
\r\n
{"jsonrpc":"2.0","id":1,"method":"initialize"...}
```

**Critical Implementation Notes**:
- Server receives input through stdin, sends output through stdout
- Improper stream handling causes deadlocks where output buffer fills while client is not reading
- Must implement non-blocking I/O with asyncio subprocess APIs

---

## 2. Lifecycle Management for Batch Operations

### Batch vs Interactive Scenarios

| Aspect | Interactive (Editor) | Batch (fs2) |
|--------|---------------------|-------------|
| Server lifetime | Long-lived, persists across sessions | Short-lived, per-scan |
| Query pattern | Sparse, user-driven | Dense, systematic |
| State requirements | Warm cache important | Clean state per scan |
| Resource constraints | Must coexist with editor | Can use available resources |

### Recommended Pattern for fs2

```
1. Parse codebase structure (determine files to analyze)
2. Initialize LSP server with workspace configuration
3. Wait for initialization to complete
4. Dispatch batches of requests grouped by file
5. Accumulate and deduplicate responses
6. Cleanly shut down server
7. Release all resources
```

### Warm vs Cold Server Decision

**Start Fresh Per-Scan (Recommended for fs2)**:
- Ensures clean state and predictable resource consumption
- Avoids accumulated memory from previous scans
- Eliminates stale cache issues
- Simpler error recovery (just restart)

**Keep Warm Across Scans**:
- Only beneficial if re-scanning same codebase frequently
- Requires careful memory monitoring
- Must handle invalidation when files change

**Evidence**: Visual Studio sends shutdown and exit requests when closing a solution, even if no documents of the server's type are open. This design reflects the principle that server lifetime should cleanly map to analysis scope boundaries.

---

## 3. Request Batching and Query Optimization

### Batching at Application Layer

LSP itself does not define a native batching protocol - each message is transmitted individually. Batching must occur at the application layer through intelligent request sequencing.

### Effective Batching Patterns

**Pattern 1: Group by File**
```python
# Process all symbols in one file before moving to next
for file in files_to_analyze:
    symbols = await query_document_symbols(file)
    for symbol in symbols:
        references = await query_references(file, symbol.position)
```
- Leverages server's parse cache
- Symbol table stays warm for the file

**Pattern 2: Parallel Independent Requests**
```python
# Dispatch multiple independent requests concurrently
async def query_batch(files):
    tasks = [query_document_symbols(f) for f in files]
    return await asyncio.gather(*tasks)
```
- Use semaphore to limit concurrency
- Respect ordering constraints for dependent requests

**Pattern 3: Progressive Disclosure**
```python
# Start broad, then focus
symbols = await query_workspace_symbols()  # Get overview
high_impact = filter_by_usage_count(symbols)
for symbol in high_impact:
    references = await query_references(symbol)  # Detailed query
```
- Reduces query volume dramatically
- Achieves analysis goals with fewer requests

---

## 4. Throttling and Rate Limiting

### Why Throttling Matters

Language servers exhibit variable performance characteristics under load:
- **gopls**: Experienced severe degradation on large projects due to excessive LSP traffic from test discovery
- **Dart analyzer**: Intermittent slowness where analysis server became the bottleneck
- **Pyright**: Performance regression over time in some cases

### Semaphore-Based Throttling (Recommended)

```python
class LSPRequestThrottler:
    def __init__(self, max_concurrent: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_pending = 100  # Prevent unbounded queue growth
        self.pending_requests = 0

    async def throttled_request(self, manager, request):
        if self.pending_requests >= self.max_pending:
            raise RuntimeError("Request queue is full")

        self.pending_requests += 1
        try:
            async with asyncio.timeout(60.0):  # Queue timeout
                async with self.semaphore:
                    async with asyncio.timeout(30.0):  # Request timeout
                        return await manager.send_request(request)
        finally:
            self.pending_requests -= 1
```

### Why Semaphores Over Rate Limiting

| Approach | Pros | Cons |
|----------|------|------|
| Semaphore (concurrent limit) | Adapts to server speed; simple | No time-based control |
| Rate limit (requests/second) | Predictable timing | Doesn't adapt to variable response times |
| **Recommendation** | Semaphore with 3-5 concurrent | Best for LSP batch operations |

### Recommended Limits by Server

| Server | Max Concurrent | Request Timeout | Notes |
|--------|---------------|-----------------|-------|
| Pyright | 5 | 30s | Handles concurrency well |
| gopls | 3 | 30s | Can slow under heavy load |
| TypeScript LSP | 4 | 30s | Moderate concurrency |
| OmniSharp | 3 | 45s | Slower responses |

---

## 5. Memory Management Strategies

### Memory Characteristics by Server

| Server | Initial Memory | Peak Memory | Notes |
|--------|---------------|-------------|-------|
| Pyright | 200-400 MB | 800-1200 MB | Medium Python projects |
| gopls | 300-500 MB | 1500-2500 MB | Large Go projects (10k+ files) |
| TypeScript LSP | 250-400 MB | 1000-1500 MB | Large TS projects |
| OmniSharp | 400-600 MB | 1200-1800 MB | Medium .NET projects |

### gopls v0.12 Architecture Improvements

The Go team addressed memory issues through architectural redesign:
- **Before**: Held all symbols in memory (30x source code size)
- **After**: File-based caching similar to compiler object files
- **Result**: ~75% average memory reduction

### Memory Management Strategy for fs2

```python
class MultiServerMemoryManager:
    def __init__(self, memory_limit_mb: int = 2048):
        self.servers = {}
        self.memory_limit_mb = memory_limit_mb

    async def check_memory_health(self):
        import psutil
        for server_key, manager in self.servers.items():
            process = psutil.Process(manager.process.pid)
            memory_mb = process.memory_info().rss / 1024 / 1024

            if memory_mb > self.memory_limit_mb:
                logging.warning(f"Server {server_key} exceeded limit: {memory_mb}MB")
                await self.restart_server(server_key)
```

### Practical Recommendations

1. **Monitor actively**: Check memory every N requests or every M seconds
2. **Set conservative limits**: 2GB per server is reasonable default
3. **Restart unhealthy servers**: Better than crashing the whole analysis
4. **Avoid redundant instances**: Share servers across related operations
5. **Lazy loading**: Start servers only when processing relevant file types

---

## 6. Workspace Initialization Performance

### Initialization Time Benchmarks

| Server | Project Size | Startup Time | Notes |
|--------|-------------|--------------|-------|
| Pyright | Medium (1000s files) | 15-30 seconds | First run slower |
| gopls | Large (10k+ files) | 10-20 seconds | Cached starts faster |
| TypeScript LSP | Large (5k+ files) | 8-15 seconds | 8x improvement with native port |
| OmniSharp | Medium (2k+ files) | 20-40 seconds | .NET analysis overhead |

### Initialization Scaling

| Project Size | Typical Init Time | Notes |
|--------------|------------------|-------|
| Small (<100 files) | 2-5 seconds | Minimal overhead |
| Medium (100-1000) | 8-15 seconds | Reasonable wait |
| Large (1000-10000) | 20-60 seconds | Significant cost |
| Very Large (>10000) | 60-120+ seconds | May need optimization |

### gopls Caching Benefits

```
First startup:  Time proportional to project complexity
Second startup: Leverages cached results (file-based)
Parallel instances: Can work synergistically
```

### TypeScript Native Port Improvements

Microsoft's native TypeScript implementation achieved:
- Startup: 9.6s -> 1.2s (8x improvement)
- Memory: ~50% reduction target
- Key: Architecture optimization, not just code optimization

### Initialization Strategy for fs2

```python
class WorkspaceInitializationTracker:
    async def initialize_and_measure(self, manager, workspace_root):
        import time

        start = time.perf_counter()
        try:
            await asyncio.wait_for(manager.start_server(), timeout=120.0)
        except asyncio.TimeoutError:
            return {"status": "timeout", "startup_ms": 120000}

        startup_ms = (time.perf_counter() - start) * 1000

        # Allow background indexing to complete
        await asyncio.sleep(2.0)

        return {"status": "success", "startup_ms": startup_ms}
```

---

## 7. Large-Scale Analysis Architecture

### Sourcegraph's Approach

Sourcegraph provides valuable lessons for scaling code intelligence:

> "LSP defines no semantic data model - it operates only on filename, line, and column as input, returning same coordinates as output"

**Sourcegraph's Key Insight**: Separate concerns between LSP and indexing:
- LSP provides real-time language services (hover, completion)
- Separate systems handle batch analysis and semantic indexing
- Build caching layers that accumulate LSP results into searchable indices

### Recommended Architecture for fs2

```
                    +-----------------+
                    |  fs2 Scanner    |
                    +--------+--------+
                             |
              +--------------+--------------+
              |              |              |
        +-----v-----+  +-----v-----+  +-----v-----+
        | Pyright   |  | gopls     |  | TS LSP    |
        | Server    |  | Server    |  | Server    |
        +-----------+  +-----------+  +-----------+
              |              |              |
              +--------------+--------------+
                             |
                    +--------v--------+
                    |  Symbol Cache   |
                    |  (per-file)     |
                    +-----------------+
                             |
                    +--------v--------+
                    |  Relationship   |
                    |  Index          |
                    +-----------------+
```

### Separation of Concerns

```python
class CodeIntelligencePipeline:
    """
    LSP provides symbol information retrieval.
    Separate indices provide relationship navigation.
    """

    def __init__(self):
        self.symbol_cache = {}      # File -> symbols
        self.reference_cache = {}   # Symbol -> references

    async def index_file_symbols(self, manager, file_path):
        cache_key = f"symbols:{file_path}"
        if cache_key in self.symbol_cache:
            return self.symbol_cache[cache_key]

        symbols = await manager.query_document_symbols(file_path)

        indexed = {
            "file": file_path,
            "symbols": symbols,
            "by_name": {s["name"]: s for s in symbols},
            "by_location": {f"{s['line']}:{s['col']}": s for s in symbols}
        }

        self.symbol_cache[cache_key] = indexed
        return indexed
```

---

## 8. Failure Handling and Resilience

### Common Failure Modes

| Failure Type | Cause | Detection | Recovery |
|--------------|-------|-----------|----------|
| Timeout | Complex analysis, deadlock | Request timeout | Retry, then skip |
| Crash | Bug, OOM, assertion | Process exit | Restart server |
| Hang | Deadlock, infinite loop | Heartbeat failure | Kill and restart |
| Error response | Invalid request, internal error | Error in JSON-RPC | Log and continue |

### Cancellation Protocol

LSP supports request cancellation:

```json
{"jsonrpc": "2.0", "method": "$/cancelRequest", "params": {"id": 42}}
```

**Important**: A cancelled request still needs to return from the server with error code -32800 (RequestCancelled).

### Resilient Client Implementation

```python
class ResilientLSPClient:
    def __init__(self, manager, max_retries=3, request_timeout=30.0):
        self.manager = manager
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.failure_count = 0

    async def query_with_retry(self, request, fallback_result=None):
        for attempt in range(self.max_retries):
            try:
                async with asyncio.timeout(self.request_timeout):
                    result = await self.manager.send_request(request)
                    self.failure_count = 0  # Reset on success
                    return result
            except asyncio.TimeoutError:
                logging.warning(f"Attempt {attempt + 1} timed out")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        self.failure_count += 1
        return fallback_result

    async def query_with_cancellation(self, request, timeout_ms):
        request_id = request.get("id")
        try:
            async with asyncio.timeout(timeout_ms / 1000):
                return await self.manager.send_request(request)
        except asyncio.TimeoutError:
            # Send cancellation notification
            if request_id:
                await self.manager.send_notification({
                    "jsonrpc": "2.0",
                    "method": "$/cancelRequest",
                    "params": {"id": request_id}
                })
            return None
```

### Graceful Degradation Strategy

1. **Per-request failure**: Log, return None, continue with other requests
2. **Multiple failures**: Mark server unhealthy, attempt restart
3. **Server crash**: Restart server, retry pending requests
4. **Repeated crashes**: Disable server for this scan, report partial results

---

## 9. Performance Benchmarks

### Query Throughput Expectations

| Query Type | Throughput | Notes |
|------------|-----------|-------|
| Simple (hover, signature) | 10-20/second | Position-based, fast |
| Medium (definition) | 5-10/second | May involve analysis |
| Complex (references) | 2-5/second | Workspace-wide search |
| Document symbols | 3-5/second | Per-file parsing |

### End-to-End Analysis Estimates

**Scenario**: 1000 Python files, 5 queries per file

```
Initialization:     15 seconds
Query execution:    5000 queries / 5 per second = 1000 seconds
Total:              ~17 minutes (single server)

With 4 parallel file batches:
Query execution:    ~4 minutes
Total:              ~4.5 minutes
```

### Memory Budget for Multiple Servers

```
4 concurrent servers @ 800MB peak each = 3.2GB
Recommendation: Limit to 2-3 concurrent servers on 8GB systems
```

---

## 10. Common Pitfalls and Solutions

### Pitfall 1: Improper Stream Handling (Deadlocks)

**Problem**: Client doesn't read server output buffer regularly -> buffer fills -> server blocks on write -> deadlock

**Solution**:
```python
# Use asyncio's asynchronous subprocess APIs
self.process = await asyncio.create_subprocess_exec(
    *server_command,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
)

# Dedicated read task running continuously
asyncio.create_task(self._read_responses())
```

### Pitfall 2: Memory Leaks from Improper Shutdown

**Problem**: Forgetting shutdown request and exit notification leaves server running

**Solution**:
```python
async def shutdown(self):
    try:
        # Always use try-finally
        await self.send_request({"method": "shutdown"})
        await self.send_notification({"method": "exit"})
        await asyncio.wait_for(self.process.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            self.process.kill()
```

### Pitfall 3: Request ID Conflicts

**Problem**: Using same ID for multiple concurrent requests

**Solution**:
```python
def _get_next_id(self) -> int:
    self.request_id += 1
    return self.request_id
```

### Pitfall 4: Initialization Race Conditions

**Problem**: Dispatching queries before initialization completes

**Solution**:
```python
class InitializationGate:
    def __init__(self):
        self._initialized = asyncio.Event()

    async def wait_initialized(self):
        await self._initialized.wait()

    def mark_initialized(self):
        self._initialized.set()
```

### Pitfall 5: Unbounded Request Queue Growth

**Problem**: Accepting requests faster than server processes -> OOM

**Solution**:
```python
if self.pending_requests >= self.max_pending:
    raise RuntimeError("Request queue is full")
```

### Pitfall 6: Missing Timeout Protection

**Problem**: Queries hang indefinitely if server stalls

**Solution**:
```python
# Two-level timeout: queue + request
async with asyncio.timeout(self.queue_timeout):      # Wait for semaphore
    async with self.semaphore:
        async with asyncio.timeout(self.request_timeout):  # Wait for response
            return await self.send_request(request)
```

---

## 11. Practical Code Examples

### Complete LSP Server Manager

```python
import asyncio
import subprocess
import json
from typing import Dict, List, Optional, Any
import logging

class LSPServerManager:
    """Manages LSP server lifecycle for batch operations"""

    def __init__(self, server_command: List[str], workspace_root: str):
        self.server_command = server_command
        self.workspace_root = workspace_root
        self.process: Optional[subprocess.Process] = None
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.logger = logging.getLogger(__name__)

    async def start_server(self) -> None:
        """Start LSP server subprocess with stdio communication"""
        self.process = await asyncio.create_subprocess_exec(
            *self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_root
        )

        # Start response reader
        asyncio.create_task(self._read_responses())

        # Initialize the server
        await self._send_initialize()
        await self._send_initialized()

    async def _send_initialize(self) -> Dict[str, Any]:
        """Send initialize request"""
        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "initialize",
            "params": {
                "processId": None,
                "rootPath": self.workspace_root,
                "rootUri": f"file://{self.workspace_root}",
                "capabilities": {
                    "textDocument": {
                        "definition": {},
                        "references": {},
                        "documentSymbol": {}
                    }
                }
            }
        }
        return await self._send_request(request)

    async def _send_initialized(self) -> None:
        """Send initialized notification"""
        await self._send_notification({
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {}
        })

    async def _send_request(self, request: Dict[str, Any]) -> Any:
        """Send request and wait for response"""
        request_id = request.get("id")
        future = asyncio.Future()
        self.pending_requests[request_id] = future

        # Send with content-length header
        payload = json.dumps(request)
        message = f"Content-Length: {len(payload)}\r\n\r\n{payload}"

        self.process.stdin.write(message.encode())
        await self.process.stdin.drain()

        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            del self.pending_requests[request_id]
            raise

    async def _send_notification(self, notification: Dict[str, Any]) -> None:
        """Send notification (no response expected)"""
        payload = json.dumps(notification)
        message = f"Content-Length: {len(payload)}\r\n\r\n{payload}"
        self.process.stdin.write(message.encode())
        await self.process.stdin.drain()

    async def _read_responses(self) -> None:
        """Continuously read responses from server"""
        buffer = b""
        while True:
            chunk = await self.process.stdout.read(4096)
            if not chunk:
                break

            buffer += chunk

            while True:
                # Parse content-length header
                header_end = buffer.find(b"\r\n\r\n")
                if header_end == -1:
                    break

                headers = buffer[:header_end].decode()
                content_length = None
                for line in headers.split("\r\n"):
                    if line.startswith("Content-Length:"):
                        content_length = int(line.split(":")[1].strip())
                        break

                if content_length is None:
                    buffer = buffer[header_end + 4:]
                    continue

                message_start = header_end + 4
                message_end = message_start + content_length
                if len(buffer) < message_end:
                    break

                message_bytes = buffer[message_start:message_end]
                buffer = buffer[message_end:]

                message = json.loads(message_bytes.decode())
                self._handle_message(message)

    def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle response from server"""
        if "id" in message and "result" in message:
            request_id = message["id"]
            if request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                if not future.done():
                    future.set_result(message.get("result"))
        elif "id" in message and "error" in message:
            request_id = message["id"]
            if request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                if not future.done():
                    error = message.get("error", {})
                    future.set_exception(
                        RuntimeError(f"LSP Error: {error.get('message')}")
                    )

    def _get_next_id(self) -> int:
        self.request_id += 1
        return self.request_id

    async def shutdown(self) -> None:
        """Cleanly shutdown the LSP server"""
        try:
            await self._send_request({
                "jsonrpc": "2.0",
                "id": self._get_next_id(),
                "method": "shutdown",
                "params": None
            })
            await self._send_notification({
                "jsonrpc": "2.0",
                "method": "exit",
                "params": None
            })
            await asyncio.wait_for(self.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self.process.kill()
```

### Batch Query with Throttling

```python
async def batch_query_references(
    manager: LSPServerManager,
    file_path: str,
    symbol_positions: List[Dict[str, int]],
    max_concurrent: int = 5
) -> Dict[str, Any]:
    """Batch query references with semaphore-based throttling"""

    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def query_single(position_info):
        async with semaphore:
            request = {
                "jsonrpc": "2.0",
                "id": manager._get_next_id(),
                "method": "textDocument/references",
                "params": {
                    "textDocument": {"uri": f"file://{file_path}"},
                    "position": {
                        "line": position_info['line'],
                        "character": position_info['character']
                    },
                    "context": {"includeDeclaration": True}
                }
            }
            try:
                return await manager._send_request(request)
            except asyncio.TimeoutError:
                return None

    # Dispatch all queries concurrently (throttled by semaphore)
    tasks = [query_single(pos) for pos in symbol_positions]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    for pos, response in zip(symbol_positions, responses):
        name = pos.get('name', f"pos_{pos['line']}")
        if isinstance(response, Exception):
            results[name] = []
        else:
            results[name] = response or []

    return results
```

### Full Analysis Pipeline

```python
async def analyze_codebase(
    codebase_root: str,
    target_language: str,
    output_file: str
) -> None:
    """End-to-end batch codebase analysis"""

    import os

    # Select server command
    server_commands = {
        "python": ["pyright-langserver", "--stdio"],
        "go": ["gopls", "serve"],
        "typescript": ["typescript-language-server", "--stdio"]
    }

    if target_language not in server_commands:
        raise ValueError(f"Unsupported language: {target_language}")

    server_command = server_commands[target_language]
    manager = LSPServerManager(server_command, codebase_root)

    # Start server
    await manager.start_server()
    logging.info("Server initialized")

    # Scan for files
    extensions = {
        "python": [".py"],
        "go": [".go"],
        "typescript": [".ts", ".tsx"]
    }

    files_to_analyze = []
    for root, dirs, filenames in os.walk(codebase_root):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules"}]
        for filename in filenames:
            if any(filename.endswith(ext) for ext in extensions[target_language]):
                files_to_analyze.append(os.path.join(root, filename))

    logging.info(f"Found {len(files_to_analyze)} files")

    # Analyze in batches
    results = {}
    batch_size = 20

    for i in range(0, len(files_to_analyze), batch_size):
        batch = files_to_analyze[i:i+batch_size]
        logging.info(f"Processing batch {i//batch_size + 1}")

        for file_path in batch:
            try:
                request = {
                    "jsonrpc": "2.0",
                    "id": manager._get_next_id(),
                    "method": "textDocument/documentSymbol",
                    "params": {"textDocument": {"uri": f"file://{file_path}"}}
                }
                symbols = await manager._send_request(request)
                results[file_path] = {"symbols": symbols or []}
            except Exception as e:
                results[file_path] = {"symbols": [], "error": str(e)}

    # Save results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    logging.info(f"Analysis saved to {output_file}")

    # Shutdown
    await manager.shutdown()
```

---

## References

1. [LSP 3.17 Specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/)
2. [gopls Scalability Blog Post](https://go.dev/blog/gopls-scalability)
3. [TypeScript Native Port Announcement](https://devblogs.microsoft.com/typescript/typescript-native-port/)
4. [Sourcegraph LSP Architecture](https://sourcegraph.com/blog/part-1-how-sourcegraph-scales-with-the-language-server-protocol)
5. [Visual Studio LSP Lifecycle](https://learn.microsoft.com/en-us/answers/questions/5669869/visual-studio-sends-shutdown-and-exit-requests-to)
6. [Python asyncio Documentation](https://docs.python.org/3/library/asyncio-subprocess.html)
7. [gopls Performance Issues](https://github.com/golang/go/issues/61352)
8. [Pyright Performance Discussion](https://github.com/microsoft/pyright/discussions/5651)

---

## Summary for fs2 Implementation

### Recommended Configuration

```yaml
# fs2 LSP session configuration
lsp:
  # Per-server settings
  servers:
    pyright:
      command: ["pyright-langserver", "--stdio"]
      max_concurrent_requests: 5
      request_timeout_ms: 30000
      memory_limit_mb: 1200
    gopls:
      command: ["gopls", "serve"]
      max_concurrent_requests: 3
      request_timeout_ms: 30000
      memory_limit_mb: 2000
    typescript:
      command: ["typescript-language-server", "--stdio"]
      max_concurrent_requests: 4
      request_timeout_ms: 30000
      memory_limit_mb: 1500

  # Global settings
  global:
    initialization_timeout_ms: 120000
    max_retries: 3
    queue_max_pending: 100
    health_check_interval_seconds: 30
```

### Implementation Priority

1. **Phase 1**: Basic lifecycle management (start, query, shutdown)
2. **Phase 2**: Semaphore-based throttling (3-5 concurrent)
3. **Phase 3**: Timeout and retry handling
4. **Phase 4**: Memory monitoring and health checks
5. **Phase 5**: Multi-server coordination
