Below is a **stdlib-only Python starter** that:

* spawns an LSP server over **stdio**
* does `initialize` / `initialized`
* answers common server→client requests (`workspace/configuration`, etc.)
* supports basic calls you’ll need for a graph:

  * `textDocument/documentSymbol`
  * `textDocument/definition`
  * `textDocument/references`
  * `workspace/symbol`
* adds **thin per-language wrappers** for:

  * **Go** (`gopls`)
  * **Python** (`pyright-langserver --stdio`) ([GitHub][1])
  * **C#** (OmniSharp `-lsp`, optionally `-s <solution.sln>`) ([Zeus Edit][2])

Notes on commands:

* `gopls` defaults to the `serve` command if you don’t specify one ([Go Forum][3]) and is designed to speak JSON-RPC over stdin/stdout ([Go.dev][4]).
* `pyright-langserver` is commonly launched with `--stdio` ([GitHub][1]).
* OmniSharp supports an LSP mode via `-lsp` ([Zeus Edit][2]).

---

## `lsp_starter.py`

```python
from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from concurrent.futures import Future


# ----------------------------
# Utilities
# ----------------------------

def path_to_uri(p: Path) -> str:
    p = p.resolve()
    return p.as_uri()


def _json_dumps(obj: Any) -> bytes:
    # LSP servers generally expect UTF-8 JSON without trailing newline.
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class LspProtocolError(RuntimeError):
    pass


class LspRequestError(RuntimeError):
    def __init__(self, method: str, error_obj: Dict[str, Any]):
        super().__init__(f"LSP error for {method}: {error_obj}")
        self.method = method
        self.error_obj = error_obj


# ----------------------------
# Config (thin per-language wrappers live here)
# ----------------------------

@dataclass(frozen=True)
class LspServerConfig:
    """
    Thin wrapper: how to launch the server + minimal config we might want to send.
    Everything else is generic LSP.
    """
    name: str
    command: List[str]                 # e.g. ["gopls"] or ["pyright-langserver","--stdio"]
    language_id: str                   # "go", "python", "csharp"
    initialization_options: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)


def find_solution_or_project(root: Path) -> Optional[Path]:
    """Best-effort for C#: prefer .sln, else .csproj."""
    root = root.resolve()
    slns = sorted(root.glob("**/*.sln"))
    if slns:
        return slns[0]
    csprojs = sorted(root.glob("**/*.csproj"))
    if csprojs:
        return csprojs[0]
    return None


def config_for_language(language: str, root: Path) -> LspServerConfig:
    lang = language.strip().lower()

    if lang in ("go", "golang"):
        # gopls defaults to 'serve' when no subcommand is given.
        return LspServerConfig(
            name="gopls",
            command=["gopls"],
            language_id="go",
            # gopls settings are usually delivered via workspace/configuration or didChangeConfiguration.
            settings={
                "gopls": {
                    # Add gopls settings here if you want (optional):
                    # "staticcheck": True,
                }
            },
        )

    if lang in ("python", "py"):
        return LspServerConfig(
            name="pyright",
            command=["pyright-langserver", "--stdio"],
            language_id="python",
            settings={
                "python": {
                    "analysis": {
                        # Optional knobs; keep empty if you prefer defaults.
                        "autoSearchPaths": True,
                        "useLibraryCodeForTypes": True,
                    }
                }
            },
        )

    if lang in ("csharp", "c#", "cs"):
        # OmniSharp in LSP mode. Many setups benefit from specifying a solution/project.
        target = find_solution_or_project(root)
        cmd = ["OmniSharp", "-lsp"]
        if target is not None:
            # Many people use -s <path> to point OmniSharp at the solution/project.
            cmd += ["-s", str(target)]
        return LspServerConfig(
            name="omnisharp",
            command=cmd,
            language_id="csharp",
            settings={
                # OmniSharp-specific settings could go here if you want.
            },
        )

    raise ValueError(f"Unsupported language: {language!r} (expected go|python|csharp)")


# ----------------------------
# Core LSP client (generic)
# ----------------------------

class LspClient:
    def __init__(self, root: Path, server: LspServerConfig):
        self.root = root.resolve()
        self.server = server

        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None

        self._lock = threading.Lock()
        self._next_id = 1
        self._pending: Dict[int, Tuple[str, Future]] = {}

        self._doc_versions: Dict[str, int] = {}  # uri -> version

        # Server->client request handlers (keep minimal + generic)
        self._server_request_handlers: Dict[str, Callable[[Any], Any]] = {
            "workspace/configuration": self._handle_workspace_configuration,
            "window/workDoneProgress/create": lambda _params: None,
            "client/registerCapability": lambda _params: None,
            "client/unregisterCapability": lambda _params: None,
            "workspace/workspaceFolders": lambda _params: [{"uri": path_to_uri(self.root), "name": self.root.name}],
        }

    # ----- Lifecycle -----

    def start(self) -> None:
        if self._proc is not None:
            raise RuntimeError("LSP already started")

        env = os.environ.copy()
        env.update(self.server.env)

        self._proc = subprocess.Popen(
            self.server.command,
            cwd=str(self.root),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

        assert self._proc.stdin and self._proc.stdout and self._proc.stderr

        self._reader_thread = threading.Thread(target=self._reader_loop, name=f"{self.server.name}-stdout", daemon=True)
        self._reader_thread.start()

        self._stderr_thread = threading.Thread(
            target=self._stderr_loop, name=f"{self.server.name}-stderr", daemon=True
        )
        self._stderr_thread.start()

        # Initialize handshake
        init_params = {
            "processId": os.getpid(),
            "rootUri": path_to_uri(self.root),
            "capabilities": {
                "workspace": {
                    "workspaceFolders": True,
                    "configuration": True,
                },
                "textDocument": {
                    "synchronization": {
                        "didSave": True,
                        "willSave": False,
                        "willSaveWaitUntil": False,
                    },
                    "documentSymbol": {},
                    "definition": {},
                    "references": {},
                },
            },
            "workspaceFolders": [{"uri": path_to_uri(self.root), "name": self.root.name}],
            "initializationOptions": self.server.initialization_options,
            "clientInfo": {"name": "fs2-lsp-starter", "version": "0.1"},
        }

        _ = self.request("initialize", init_params, timeout_s=30.0)
        self.notify("initialized", {})

        # Push initial config (many servers will also pull via workspace/configuration)
        self.notify("workspace/didChangeConfiguration", {"settings": self.server.settings})

    def shutdown(self) -> None:
        if not self._proc:
            return
        try:
            try:
                self.request("shutdown", {}, timeout_s=10.0)
            except Exception:
                pass
            try:
                self.notify("exit", {})
            except Exception:
                pass
        finally:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def __enter__(self) -> "LspClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()

    # ----- Public API: requests/notifications -----

    def request(self, method: str, params: Any, timeout_s: float = 10.0) -> Any:
        req_id = self._alloc_id()
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}

        fut: Future = Future()
        with self._lock:
            self._pending[req_id] = (method, fut)

        self._send(msg)

        try:
            return fut.result(timeout=timeout_s)
        except Exception:
            # best-effort cleanup
            with self._lock:
                self._pending.pop(req_id, None)
            raise

    def notify(self, method: str, params: Any) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        self._send(msg)

    # ----- Convenience: document operations -----

    def open_document(self, file_path: Path, text: Optional[str] = None) -> str:
        file_path = file_path.resolve()
        uri = path_to_uri(file_path)

        if text is None:
            text = file_path.read_text(encoding="utf-8", errors="replace")

        version = self._doc_versions.get(uri, 0) + 1
        self._doc_versions[uri] = version

        self.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": self.server.language_id,
                    "version": version,
                    "text": text,
                }
            },
        )
        return uri

    def document_symbols(self, file_path: Path) -> Any:
        uri = path_to_uri(file_path.resolve())
        return self.request("textDocument/documentSymbol", {"textDocument": {"uri": uri}}, timeout_s=30.0)

    def workspace_symbol(self, query: str) -> Any:
        return self.request("workspace/symbol", {"query": query}, timeout_s=30.0)

    def definition(self, file_path: Path, line: int, character: int) -> Any:
        uri = path_to_uri(file_path.resolve())
        return self.request(
            "textDocument/definition",
            {"textDocument": {"uri": uri}, "position": {"line": line, "character": character}},
            timeout_s=30.0,
        )

    def references(self, file_path: Path, line: int, character: int, include_declaration: bool = False) -> Any:
        uri = path_to_uri(file_path.resolve())
        return self.request(
            "textDocument/references",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
                "context": {"includeDeclaration": include_declaration},
            },
            timeout_s=60.0,
        )

    # ----------------------------
    # Internals: IO + dispatch
    # ----------------------------

    def _alloc_id(self) -> int:
        with self._lock:
            rid = self._next_id
            self._next_id += 1
            return rid

    def _send(self, msg: Dict[str, Any]) -> None:
        if not self._proc or not self._proc.stdin:
            raise RuntimeError("LSP process not running")

        body = _json_dumps(msg)
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        try:
            self._proc.stdin.write(header)
            self._proc.stdin.write(body)
            self._proc.stdin.flush()
        except BrokenPipeError as e:
            raise RuntimeError(f"LSP server {self.server.name} stdin closed") from e

    def _read_one_message(self) -> Optional[Dict[str, Any]]:
        assert self._proc and self._proc.stdout
        stdout = self._proc.stdout

        headers: Dict[str, str] = {}
        while True:
            line = stdout.readline()
            if not line:
                return None  # EOF
            if line in (b"\r\n", b"\n"):
                break
            if b":" not in line:
                # Non-protocol garbage on stdout. Rare, but don't crash.
                continue
            k, v = line.split(b":", 1)
            headers[k.decode("ascii", errors="replace").strip().lower()] = v.decode("ascii", errors="replace").strip()

        if "content-length" not in headers:
            raise LspProtocolError(f"Missing Content-Length header: {headers}")

        length = int(headers["content-length"])
        body = stdout.read(length)
        if len(body) != length:
            raise LspProtocolError(f"Short read: expected {length}, got {len(body)}")

        try:
            return json.loads(body.decode("utf-8"))
        except Exception as e:
            raise LspProtocolError(f"Failed to parse JSON: {body[:200]!r}") from e

    def _reader_loop(self) -> None:
        while True:
            if not self._proc:
                return
            msg = self._read_one_message()
            if msg is None:
                return
            self._dispatch(msg)

    def _stderr_loop(self) -> None:
        # Drain stderr to avoid blocking; you can wire this to your logger.
        assert self._proc and self._proc.stderr
        for raw in iter(self._proc.stderr.readline, b""):
            # Uncomment if you want verbose logs:
            # print(f"[{self.server.name} stderr] {raw.decode('utf-8', errors='replace').rstrip()}")
            pass

    def _dispatch(self, msg: Dict[str, Any]) -> None:
        # 1) Response to our request
        if "id" in msg and ("result" in msg or "error" in msg) and "method" not in msg:
            req_id = msg["id"]
            with self._lock:
                entry = self._pending.pop(req_id, None)

            if not entry:
                return  # unknown / timed-out request

            method, fut = entry
            if "error" in msg and msg["error"] is not None:
                fut.set_exception(LspRequestError(method, msg["error"]))
            else:
                fut.set_result(msg.get("result"))
            return

        # 2) Server -> client request (must respond)
        if "id" in msg and "method" in msg:
            method = msg["method"]
            params = msg.get("params")
            handler = self._server_request_handlers.get(method)
            try:
                result = handler(params) if handler else None
                resp = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
            except Exception as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg["id"],
                    "error": {"code": -32603, "message": f"client error in handler for {method}: {e}"},
                }
            self._send(resp)
            return

        # 3) Notification (ignore or log)
        # Common: window/logMessage, textDocument/publishDiagnostics, etc.
        return

    def _handle_workspace_configuration(self, params: Any) -> Any:
        """
        LSP: workspace/configuration -> return a list of config objects matching "items".
        We'll return by "section" if provided (supports dotted sections), else full settings.
        """
        items = (params or {}).get("items", [])
        out: List[Any] = []

        for item in items:
            section = item.get("section")
            out.append(self._get_settings_for_section(section))

        return out

    def _get_settings_for_section(self, section: Optional[str]) -> Any:
        if not section:
            return self.server.settings

        cur: Any = self.server.settings
        for part in section.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return {}
        return cur


# ----------------------------
# Small demo
# ----------------------------

def demo(language: str, root: str, file: str, line: int, col: int) -> None:
    root_path = Path(root)
    file_path = Path(file)

    cfg = config_for_language(language, root_path)

    with LspClient(root=root_path, server=cfg) as lsp:
        # Many servers behave best if you open the doc before asking def/refs.
        lsp.open_document(file_path)

        print("\n--- document symbols ---")
        symbols = lsp.document_symbols(file_path)
        print(json.dumps(symbols, indent=2)[:4000])

        print("\n--- definition ---")
        defs = lsp.definition(file_path, line, col)
        print(json.dumps(defs, indent=2)[:4000])

        print("\n--- references ---")
        refs = lsp.references(file_path, line, col, include_declaration=False)
        print(json.dumps(refs, indent=2)[:4000])


if __name__ == "__main__":
    import sys

    # Example:
    #   python lsp_starter.py python /path/to/repo /path/to/repo/pkg/mod.py 10 5
    if len(sys.argv) != 6:
        print("usage: python lsp_starter.py <go|python|csharp> <root_dir> <file> <line0> <col0>")
        raise SystemExit(2)

    demo(
        language=sys.argv[1],
        root=sys.argv[2],
        file=sys.argv[3],
        line=int(sys.argv[4]),
        col=int(sys.argv[5]),
    )
```

---

## How you’d extend this for your relationship graph

This “starter” gives you the primitives. The usual graph-building patterns on top:

* **Imports edges**: you already do with tree-sitter (good).
* **Call edges**: for each call-site identifier you care about, call `textDocument/definition` at its position; if it returns a `Location/LocationLink`, create `CALLS` edge from “containing symbol” → “target symbol”.
* **Reverse edges / usage edges**: for each “definition symbol node” you want inbound edges for, call `textDocument/references` at its definition position; each returned `Location` becomes a `REFERENCED_BY` or `CALLS` edge depending on syntactic context (you can classify context with tree-sitter around the reference location).
* **Inheritance/implementation edges**: if a server supports `textDocument/typeDefinition` or `textDocument/implementation`, you can add those later the same way (same harness).

If you want, I can also give you a small **“relationship extraction loop”** that:

1. gets all `documentSymbol` entries for a file,
2. chooses “interesting” symbols,
3. calls `references` on them,
4. emits edges in your `CodeEdge` format with confidence tiers.

[1]: https://github.com/microsoft/pyright/discussions/5945?utm_source=chatgpt.com "How to debug Pyright LSP Server stdio communication?"
[2]: https://www.zeusedit.com/lsp/cs-dls.html?utm_source=chatgpt.com "C# Omnisharp Roslyn Configuration"
[3]: https://forum.golangbridge.org/t/missing-flags-in-gopls-help-text/19398?utm_source=chatgpt.com "Missing flags in gopls help text - Getting Help - Go Forum"
[4]: https://go.dev/gopls/daemon?utm_source=chatgpt.com "Gopls: Running as a daemon"
