#!/usr/bin/env python3
"""
Multi-language cross-file relationship extraction exploration.

Demonstrates a language-registry approach where each language provides
its own tree-sitter queries for imports, calls, and scopes. The core
pipeline (index → resolve → edge) is language-agnostic.

Run from repo root:
    uv run python scripts/fastcode-explore/mini_crossfile.py [directory]

Default: runs against scripts/fastcode-explore/sample_project/
"""

from __future__ import annotations

import os
import sys
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from tree_sitter import Language, Query, QueryCursor
from tree_sitter_language_pack import get_language, get_parser

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Language Handler ABC — each language registers one of these
# ══════════════════════════════════════════════════════════════


class LanguageCrossFileHandler(ABC):
    """Per-language handler for cross-file relationship extraction."""

    @property
    @abstractmethod
    def language(self) -> str:
        ...

    @abstractmethod
    def extract_imports(self, code: str, lang: Language) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def extract_calls(self, code: str, file_path: str, lang: Language) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def extract_definitions(self, code: str, file_path: str, lang: Language) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def file_path_to_module(self, file_path: str, root_dir: str) -> str | None:
        ...

    @abstractmethod
    def resolve_import_to_module(self, imp: dict, current_module: str) -> str | None:
        ...


# ══════════════════════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════════════════════

BUILTINS_PYTHON = {
    "abs", "all", "any", "bin", "bool", "breakpoint", "bytearray",
    "bytes", "callable", "chr", "classmethod", "compile", "complex",
    "delattr", "dict", "dir", "divmod", "enumerate", "eval", "exec",
    "filter", "float", "format", "frozenset", "getattr", "globals",
    "hasattr", "hash", "help", "hex", "id", "input", "int", "isinstance",
    "issubclass", "iter", "len", "list", "locals", "map", "max",
    "memoryview", "min", "next", "object", "oct", "open", "ord",
    "pow", "print", "property", "range", "repr", "reversed", "round",
    "set", "setattr", "slice", "sorted", "staticmethod", "str", "sum",
    "super", "tuple", "type", "vars", "zip",
}


def _find_scope(call_node, scopes: list[dict]) -> str | None:
    pos = call_node.start_byte
    for scope in reversed(scopes):
        if scope["start_byte"] <= pos < scope["end_byte"]:
            return f"{scope['type']}::{scope['name']}"
    return None


def _find_parent_class(node, code: str) -> str | None:
    current = node.parent
    while current and current.type not in ("module", "program", "source_file", "compilation_unit"):
        if current.type in ("class_definition", "class_declaration"):
            name_node = current.child_by_field_name("name")
            if name_node:
                return code[name_node.start_byte:name_node.end_byte]
        if current.type == "class_body":
            current = current.parent
            continue
        current = current.parent
    return None


def _extract_call_details(func_node) -> dict | None:
    if func_node.type == "identifier":
        return {"call_name": func_node.text.decode(), "call_type": "simple", "base_object": None}

    if func_node.type in ("attribute", "member_expression", "member_access_expression",
                           "field_expression", "scoped_identifier"):
        obj = func_node.child_by_field_name("object") or func_node.child_by_field_name("value")
        attr = (func_node.child_by_field_name("attribute")
                or func_node.child_by_field_name("name")
                or func_node.child_by_field_name("field"))
        if obj and attr:
            return {"call_name": attr.text.decode(), "base_object": obj.text.decode(), "call_type": "attribute"}

    if func_node.type == "selector_expression":
        operand = func_node.child_by_field_name("operand")
        fld = func_node.child_by_field_name("field")
        if operand and fld:
            return {"call_name": fld.text.decode(), "base_object": operand.text.decode(), "call_type": "attribute"}

    return None


def _run_query(lang_name: str, lang: Language, code: str, query_str: str) -> dict[str, list]:
    parser = get_parser(lang_name)
    tree = parser.parse(code.encode())
    query = Query(lang, query_str)
    cursor = QueryCursor(query)
    return cursor.captures(tree.root_node), tree


# ══════════════════════════════════════════════════════════════
# Python Handler
# ══════════════════════════════════════════════════════════════


class PythonHandler(LanguageCrossFileHandler):
    @property
    def language(self) -> str:
        return "python"

    def extract_imports(self, code: str, lang: Language) -> list[dict[str, Any]]:
        caps, _ = _run_query("python", lang, code, """
            (import_statement name: (_) @import.item)
            (import_from_statement name: (_) @from.item)
            (import_from_statement (wildcard_import) @from.item)
        """)
        imports, from_cache = [], {}
        for cap_name, nodes in caps.items():
            for node in nodes:
                if cap_name == "import.item":
                    name = code[node.start_byte:node.end_byte]
                    imports.append({"module": name, "names": [name], "level": 0})
                elif cap_name == "from.item":
                    parent = node.parent
                    while parent and parent.type != "import_from_statement":
                        parent = parent.parent
                    if not parent:
                        continue
                    if parent.id not in from_cache:
                        from_cache[parent.id] = self._parse_from(parent, code)
                    module, level = from_cache[parent.id]
                    name = "*" if node.type == "wildcard_import" else code[node.start_byte:node.end_byte]
                    imports.append({"module": module, "names": [name], "level": level})
        return imports

    def _parse_from(self, stmt, code):
        level, module = 0, ""
        for child in stmt.children:
            if child.type == "relative_import":
                text = code[child.start_byte:child.end_byte]
                level = sum(1 for c in text if c == ".")
                module = text[level:]
            elif child.type == "dotted_name" and level == 0 and not module:
                module = code[child.start_byte:child.end_byte]
            elif child.type == "import":
                break
        return module, level

    def extract_calls(self, code: str, file_path: str, lang: Language) -> list[dict[str, Any]]:
        caps, tree = _run_query("python", lang, code, "(call function: (_) @func) @call_node")
        scopes = self._scopes(code, lang)
        calls = []
        for cap_name, nodes in caps.items():
            if cap_name != "call_node":
                continue
            for cn in nodes:
                fn = cn.child_by_field_name("function")
                if not fn:
                    continue
                info = _extract_call_details(fn)
                if not info or info["call_name"] in BUILTINS_PYTHON:
                    continue
                calls.append({**info, "scope_id": _find_scope(cn, scopes), "file_path": file_path})
        return calls

    def _scopes(self, code, lang):
        caps, _ = _run_query("python", lang, code, """
            (function_definition name: (identifier) @name) @scope
            (class_definition name: (identifier) @name) @scope
        """)
        scopes = []
        for cap_name, nodes in caps.items():
            if cap_name != "scope":
                continue
            for n in nodes:
                nn = n.child_by_field_name("name")
                if nn:
                    t = "class" if n.type == "class_definition" else "function"
                    scopes.append({"type": t, "name": nn.text.decode(),
                                   "start_byte": n.start_byte, "end_byte": n.end_byte})
        scopes.sort(key=lambda s: s["start_byte"])
        return scopes

    def extract_definitions(self, code: str, file_path: str, lang: Language) -> list[dict[str, Any]]:
        caps, _ = _run_query("python", lang, code, """
            (function_definition) @function.def
            (class_definition) @class.def
        """)
        defs = []
        for cap_name, nodes in caps.items():
            for node in nodes:
                nn = node.child_by_field_name("name")
                if not nn:
                    continue
                name = code[nn.start_byte:nn.end_byte]
                dtype = "class" if cap_name == "class.def" else "function"
                pc = _find_parent_class(node, code)
                bases = []
                if dtype == "class":
                    for child in node.children:
                        if child.type == "argument_list":
                            for bc in child.children:
                                if bc.type == "identifier":
                                    bases.append(code[bc.start_byte:bc.end_byte])
                defs.append({"name": name, "type": dtype, "parent_class": pc,
                             "file_path": file_path, "bases": bases})
        return defs

    def file_path_to_module(self, file_path: str, root_dir: str) -> str | None:
        rel = os.path.relpath(file_path, root_dir)
        m = rel.replace(os.sep, ".").removesuffix(".py")
        if m.endswith(".__init__"):
            m = m.removesuffix(".__init__")
        return m

    def resolve_import_to_module(self, imp: dict, current_module: str) -> str | None:
        target = imp.get("module", "")
        level = imp.get("level", 0)
        if level > 0 and current_module:
            parts = current_module.split(".")
            if level <= len(parts):
                parent = ".".join(parts[:-level])
                return f"{parent}.{target}" if target else parent
        return target or None


# ══════════════════════════════════════════════════════════════
# JavaScript/TypeScript Handler
# ══════════════════════════════════════════════════════════════


class JSHandler(LanguageCrossFileHandler):
    def __init__(self, lang_name: str = "javascript"):
        self._lang = lang_name

    @property
    def language(self) -> str:
        return self._lang

    def extract_imports(self, code: str, lang: Language) -> list[dict[str, Any]]:
        caps, _ = _run_query(self._lang, lang, code, "(import_statement) @imp")
        imports = []
        for cap_name, nodes in caps.items():
            if cap_name != "imp":
                continue
            for node in nodes:
                src = node.child_by_field_name("source")
                source = code[src.start_byte:src.end_byte].strip("'\"") if src else ""
                names = []
                for child in node.children:
                    if child.type == "import_clause":
                        for ic in child.children:
                            if ic.type == "identifier":
                                names.append(ic.text.decode())
                            elif ic.type == "named_imports":
                                for spec in ic.children:
                                    if spec.type == "import_specifier":
                                        n = spec.child_by_field_name("name")
                                        if n:
                                            names.append(n.text.decode())
                            elif ic.type == "namespace_import":
                                for ns in ic.children:
                                    if ns.type == "identifier":
                                        names.append(ns.text.decode())
                imports.append({"module": source, "names": names or [source.split("/")[-1]],
                                "level": 1 if source.startswith(".") else 0})
        return imports

    def extract_calls(self, code: str, file_path: str, lang: Language) -> list[dict[str, Any]]:
        caps, tree = _run_query(self._lang, lang, code,
                                "(call_expression function: (_) @func) @call_node")
        scopes = self._scopes(code, lang)
        calls = []
        for cap_name, nodes in caps.items():
            if cap_name != "call_node":
                continue
            for cn in nodes:
                fn = cn.child_by_field_name("function")
                if not fn:
                    continue
                info = _extract_call_details(fn)
                if info:
                    calls.append({**info, "scope_id": _find_scope(cn, scopes), "file_path": file_path})
        return calls

    def _scopes(self, code, lang):
        caps, _ = _run_query(self._lang, lang, code, """
            (function_declaration name: (identifier) @name) @scope
            (method_definition name: (property_identifier) @name) @scope
        """)
        scopes = []
        for cap_name, nodes in caps.items():
            if cap_name != "scope":
                continue
            for n in nodes:
                nn = n.child_by_field_name("name")
                if nn:
                    scopes.append({"type": "function", "name": nn.text.decode(),
                                   "start_byte": n.start_byte, "end_byte": n.end_byte})
        scopes.sort(key=lambda s: s["start_byte"])
        return scopes

    def extract_definitions(self, code: str, file_path: str, lang: Language) -> list[dict[str, Any]]:
        caps, _ = _run_query(self._lang, lang, code, """
            (function_declaration name: (identifier) @name) @func
            (class_declaration name: (identifier) @name) @cls
            (method_definition name: (property_identifier) @name) @func
        """)
        defs = []
        for cap_name, nodes in caps.items():
            if cap_name not in ("func", "cls"):
                continue
            for node in nodes:
                nn = node.child_by_field_name("name")
                if not nn:
                    continue
                defs.append({"name": nn.text.decode(),
                             "type": "class" if cap_name == "cls" else "function",
                             "parent_class": _find_parent_class(node, code),
                             "file_path": file_path, "bases": []})
        return defs

    def file_path_to_module(self, file_path: str, root_dir: str) -> str | None:
        rel = os.path.relpath(file_path, root_dir).replace(os.sep, "/")
        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            if rel.endswith(ext):
                rel = rel[:-len(ext)]
                break
        if rel.endswith("/index"):
            rel = rel[:-len("/index")]
        return rel

    def resolve_import_to_module(self, imp: dict, current_module: str) -> str | None:
        source = imp.get("module", "")
        if not source:
            return None
        if source.startswith("."):
            cur_dir = "/".join(current_module.split("/")[:-1])
            for part in source.split("/"):
                if part == ".":
                    pass
                elif part == "..":
                    cur_dir = "/".join(cur_dir.split("/")[:-1])
                else:
                    cur_dir = f"{cur_dir}/{part}" if cur_dir else part
            return cur_dir
        return source


# ══════════════════════════════════════════════════════════════
# Go Handler
# ══════════════════════════════════════════════════════════════


class GoHandler(LanguageCrossFileHandler):
    @property
    def language(self) -> str:
        return "go"

    def extract_imports(self, code: str, lang: Language) -> list[dict[str, Any]]:
        caps, _ = _run_query("go", lang, code,
                             '(import_spec path: (interpreted_string_literal) @path) @imp')
        imports = []
        for cap_name, nodes in caps.items():
            if cap_name != "imp":
                continue
            for node in nodes:
                pn = node.child_by_field_name("path")
                if pn:
                    mod = code[pn.start_byte:pn.end_byte].strip('"')
                    imports.append({"module": mod, "names": [mod.split("/")[-1]], "level": 0})
        return imports

    def extract_calls(self, code: str, file_path: str, lang: Language) -> list[dict[str, Any]]:
        caps, _ = _run_query("go", lang, code,
                             "(call_expression function: (_) @func) @call_node")
        scopes = self._scopes(code, lang)
        calls = []
        for cap_name, nodes in caps.items():
            if cap_name != "call_node":
                continue
            for cn in nodes:
                fn = cn.child_by_field_name("function")
                if not fn:
                    continue
                info = _extract_call_details(fn)
                if info:
                    calls.append({**info, "scope_id": _find_scope(cn, scopes), "file_path": file_path})
        return calls

    def _scopes(self, code, lang):
        caps, _ = _run_query("go", lang, code,
                             "(function_declaration name: (identifier) @name) @scope")
        scopes = []
        for cap_name, nodes in caps.items():
            if cap_name != "scope":
                continue
            for n in nodes:
                nn = n.child_by_field_name("name")
                if nn:
                    scopes.append({"type": "function", "name": nn.text.decode(),
                                   "start_byte": n.start_byte, "end_byte": n.end_byte})
        scopes.sort(key=lambda s: s["start_byte"])
        return scopes

    def extract_definitions(self, code: str, file_path: str, lang: Language) -> list[dict[str, Any]]:
        caps, _ = _run_query("go", lang, code, """
            (function_declaration name: (identifier) @name) @func
            (method_declaration name: (field_identifier) @name) @func
            (type_declaration (type_spec name: (type_identifier) @name)) @cls
        """)
        defs = []
        for cap_name, nodes in caps.items():
            if cap_name not in ("func", "cls"):
                continue
            for node in nodes:
                nn = node.child_by_field_name("name")
                if not nn:
                    for child in node.children:
                        if child.type == "type_spec":
                            nn = child.child_by_field_name("name")
                            break
                if not nn:
                    continue
                defs.append({"name": nn.text.decode(),
                             "type": "class" if cap_name == "cls" else "function",
                             "parent_class": None, "file_path": file_path, "bases": []})
        return defs

    def file_path_to_module(self, file_path: str, root_dir: str) -> str | None:
        rel = os.path.relpath(file_path, root_dir)
        return os.path.dirname(rel).replace(os.sep, "/") or rel.replace(os.sep, "/").removesuffix(".go")

    def resolve_import_to_module(self, imp: dict, current_module: str) -> str | None:
        return imp.get("module")


# ══════════════════════════════════════════════════════════════
# Rust Handler
# ══════════════════════════════════════════════════════════════


class RustHandler(LanguageCrossFileHandler):
    @property
    def language(self) -> str:
        return "rust"

    def extract_imports(self, code: str, lang: Language) -> list[dict[str, Any]]:
        caps, _ = _run_query("rust", lang, code, "(use_declaration) @use_node")
        imports = []
        for cap_name, nodes in caps.items():
            if cap_name != "use_node":
                continue
            for node in nodes:
                text = code[node.start_byte:node.end_byte].removeprefix("use ").removesuffix(";").strip()
                parts = text.split("::")
                module = "::".join(parts[:-1]) if len(parts) > 1 else text
                name = parts[-1] if len(parts) > 1 else text
                imports.append({"module": module, "names": [name], "level": 0})
        return imports

    def extract_calls(self, code: str, file_path: str, lang: Language) -> list[dict[str, Any]]:
        caps, _ = _run_query("rust", lang, code,
                             "(call_expression function: (_) @func) @call_node")
        scopes = self._scopes(code, lang)
        calls = []
        for cap_name, nodes in caps.items():
            if cap_name != "call_node":
                continue
            for cn in nodes:
                fn = cn.child_by_field_name("function")
                if not fn:
                    continue
                info = _extract_call_details(fn)
                if info:
                    calls.append({**info, "scope_id": _find_scope(cn, scopes), "file_path": file_path})
        return calls

    def _scopes(self, code, lang):
        caps, _ = _run_query("rust", lang, code,
                             "(function_item name: (identifier) @name) @scope")
        scopes = []
        for cap_name, nodes in caps.items():
            if cap_name != "scope":
                continue
            for n in nodes:
                nn = n.child_by_field_name("name")
                if nn:
                    scopes.append({"type": "function", "name": nn.text.decode(),
                                   "start_byte": n.start_byte, "end_byte": n.end_byte})
        scopes.sort(key=lambda s: s["start_byte"])
        return scopes

    def extract_definitions(self, code: str, file_path: str, lang: Language) -> list[dict[str, Any]]:
        caps, _ = _run_query("rust", lang, code, """
            (function_item name: (identifier) @name) @func
            (struct_item name: (type_identifier) @name) @cls
        """)
        defs = []
        for cap_name, nodes in caps.items():
            if cap_name not in ("func", "cls"):
                continue
            for node in nodes:
                nn = node.child_by_field_name("name")
                if not nn:
                    continue
                defs.append({"name": nn.text.decode(),
                             "type": "class" if cap_name == "cls" else "function",
                             "parent_class": None, "file_path": file_path, "bases": []})
        return defs

    def file_path_to_module(self, file_path: str, root_dir: str) -> str | None:
        rel = os.path.relpath(file_path, root_dir)
        return rel.replace(os.sep, "::").removesuffix(".rs")

    def resolve_import_to_module(self, imp: dict, current_module: str) -> str | None:
        mod = imp.get("module", "")
        if mod.startswith("crate"):
            return mod.removeprefix("crate::")
        if mod.startswith("super"):
            parts = current_module.split("::")
            return "::".join(parts[:-1]) + "::" + mod.removeprefix("super::") if parts else mod
        return mod


# ══════════════════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════════════════

HANDLERS: dict[str, LanguageCrossFileHandler] = {}

def _register(h: LanguageCrossFileHandler):
    HANDLERS[h.language] = h

_register(PythonHandler())
_register(JSHandler("javascript"))
_register(JSHandler("typescript"))
_register(JSHandler("tsx"))
_register(GoHandler())
_register(RustHandler())

EXTENSION_TO_LANG: dict[str, str] = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".go": "go", ".rs": "rust",
}


# ══════════════════════════════════════════════════════════════
# Core Pipeline (language-agnostic)
# ══════════════════════════════════════════════════════════════


@dataclass
class GlobalIndex:
    module_map: dict[str, str] = field(default_factory=dict)
    module_to_file: dict[str, str] = field(default_factory=dict)
    export_map: dict[str, dict[str, str]] = field(default_factory=dict)

    def build(self, all_defs, root_dir, handlers):
        for fpath, defs in all_defs.items():
            ext = os.path.splitext(fpath)[1]
            lang_name = EXTENSION_TO_LANG.get(ext)
            handler = handlers.get(lang_name) if lang_name else None
            if not handler:
                continue
            module = handler.file_path_to_module(fpath, root_dir)
            if not module:
                continue
            self.module_map[fpath] = module
            self.module_to_file[module] = fpath
            if module not in self.export_map:
                self.export_map[module] = {}
            for d in defs:
                self.export_map[module][d["name"]] = _make_id(d)
                if d["type"] == "function" and d.get("parent_class"):
                    self.export_map[module][f"{d['parent_class']}.{d['name']}"] = _make_id(d)

    def resolve(self, symbol, current_file, imports, handler):
        cur_mod = self.module_map.get(current_file)
        if cur_mod:
            local = self.export_map.get(cur_mod, {}).get(symbol)
            if local:
                return local
        for imp in imports:
            if symbol not in imp.get("names", []):
                if not any(symbol.startswith(n + ".") for n in imp.get("names", [])):
                    continue
            target_mod = handler.resolve_import_to_module(imp, cur_mod or "")
            if target_mod:
                r = self.export_map.get(target_mod, {}).get(symbol)
                if r:
                    return r
        return None


def _make_id(d):
    fp = d["file_path"]
    if d["type"] == "class":
        return f"type:{fp}:{d['name']}"
    elif d.get("parent_class"):
        return f"callable:{fp}:{d['parent_class']}.{d['name']}"
    return f"callable:{fp}:{d['name']}"


@dataclass
class Edge:
    source: str
    target: str
    edge_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        meta = ", ".join(f"{k}={v}" for k, v in self.metadata.items())
        return f"{self.source} ──{self.edge_type}──▶ {self.target}" + (f" ({meta})" if meta else "")


def build_cross_file_edges(root_dir: str) -> tuple[list[Edge], GlobalIndex]:
    # Phase 1: Discover
    files: dict[str, str] = {}
    langs: dict[str, str] = {}
    for dirpath, _, fnames in os.walk(root_dir):
        for fname in fnames:
            ext = os.path.splitext(fname)[1]
            lang_name = EXTENSION_TO_LANG.get(ext)
            if lang_name and lang_name in HANDLERS:
                fpath = os.path.join(dirpath, fname)
                with open(fpath) as f:
                    files[fpath] = f.read()
                langs[fpath] = lang_name

    log.info(f"Found {len(files)} files ({', '.join(sorted(set(langs.values())))})")

    # Phase 2: Extract all (nodes first, then relationships)
    all_defs, all_imports, all_calls = {}, {}, {}
    for fpath, code in files.items():
        h = HANDLERS[langs[fpath]]
        lang = get_language(langs[fpath])
        all_defs[fpath] = h.extract_definitions(code, fpath, lang)
        all_imports[fpath] = h.extract_imports(code, lang)
        all_calls[fpath] = h.extract_calls(code, fpath, lang)
        log.info(f"  {os.path.relpath(fpath, root_dir)} [{langs[fpath]}]: "
                 f"{len(all_defs[fpath])} defs, {len(all_imports[fpath])} imports, {len(all_calls[fpath])} calls")

    # Phase 3: Global index
    index = GlobalIndex()
    index.build(all_defs, root_dir, HANDLERS)
    log.info(f"\nIndex: {len(index.module_map)} modules, "
             f"{sum(len(v) for v in index.export_map.values())} exports")

    # Phase 4: Edges
    edges: list[Edge] = []

    for fpath, calls in all_calls.items():
        h = HANDLERS[langs[fpath]]
        imps = all_imports.get(fpath, [])
        for call in calls:
            caller = _caller_from_scope(call, fpath, all_defs)
            cn = call["call_name"]
            bo = call.get("base_object")
            if call["call_type"] == "simple":
                callee = index.resolve(cn, fpath, imps, h)
            elif call["call_type"] == "attribute" and bo:
                callee = index.resolve(f"{bo}.{cn}", fpath, imps, h) or index.resolve(cn, fpath, imps, h)
            else:
                callee = None
            if caller and callee and caller != callee:
                edges.append(Edge(caller, callee, "calls", {"call_name": cn}))

    for fpath, imps in all_imports.items():
        h = HANDLERS[langs[fpath]]
        cur_mod = index.module_map.get(fpath, "")
        for imp in imps:
            target_mod = h.resolve_import_to_module(imp, cur_mod)
            target_file = index.module_to_file.get(target_mod) if target_mod else None
            if target_file and target_file != fpath:
                edges.append(Edge(f"file:{fpath}", f"file:{target_file}", "imports",
                                  {"module": target_mod}))

    for fpath, defs in all_defs.items():
        h = HANDLERS[langs[fpath]]
        imps = all_imports.get(fpath, [])
        for d in defs:
            if d["type"] == "class" and d.get("bases"):
                for base in d["bases"]:
                    pid = index.resolve(base, fpath, imps, h)
                    if pid:
                        edges.append(Edge(_make_id(d), pid, "inherits", {"base_name": base}))

    return edges, index


def _caller_from_scope(call, fpath, all_defs):
    sid = call.get("scope_id")
    if not sid:
        return f"file:{fpath}"
    parts = sid.split("::", 1)
    if len(parts) != 2:
        return f"file:{fpath}"
    for d in all_defs.get(fpath, []):
        if d["name"] == parts[1]:
            return _make_id(d)
    return f"file:{fpath}"


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

def main():
    root_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "sample_project")
    root_dir = os.path.abspath(root_dir)
    if not os.path.isdir(root_dir):
        print(f"Not found: {root_dir}")
        sys.exit(1)

    log.info(f"═══ Multi-Language Cross-File Rels ═══")
    log.info(f"Root: {root_dir}")
    log.info(f"Languages: {', '.join(sorted(HANDLERS.keys()))}\n")

    edges, _ = build_cross_file_edges(root_dir)

    seen = set()
    unique = []
    for e in edges:
        key = (e.source, e.target, e.edge_type)
        if key not in seen:
            seen.add(key)
            unique.append(e)

    log.info(f"\n═══ {len(unique)} unique edges ═══\n")
    for et in ("imports", "inherits", "calls"):
        typed = [e for e in unique if e.edge_type == et]
        if typed:
            log.info(f"── {et.upper()} ({len(typed)}) ──")
            for e in typed:
                log.info(f"  {e}")
            log.info("")

    c = sum(1 for e in unique if e.edge_type == "calls")
    i = sum(1 for e in unique if e.edge_type == "imports")
    h = sum(1 for e in unique if e.edge_type == "inherits")
    log.info(f"Total: {c} calls, {i} imports, {h} inherits")


if __name__ == "__main__":
    main()
