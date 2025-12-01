# Wormhole MCP Server Guide

This guide covers the VS Code Wormhole MCP server's code search and navigation capabilities for use with Claude Code.

## Overview

The Wormhole MCP server bridges Claude Code to VS Code's Language Server Protocol (LSP), providing semantic code intelligence including symbol search, call hierarchy, reference finding, and diagnostics.

## Available Tools

### 1. Symbol Search (`search_symbol_search`)

Search for symbols (classes, methods, functions, fields) across the workspace or within a single file.

**Modes:**
- `workspace` (default): Search entire codebase
- `document`: Get outline of a specific file

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search query (fuzzy matching, empty returns all) |
| `mode` | string | `workspace` or `document` |
| `path` | string | **Absolute path** required for document mode |
| `kinds` | string | Comma-separated filter: `Class`, `Method`, `Function`, `Field`, `Interface`, `Property`, `Constructor` |
| `limit` | number | Max results (default 100, max 1000) |
| `includeLocation` | boolean | Include file path, line, range (default true) |
| `includeContainer` | boolean | Include parent symbol info (default true) |

**Examples:**

```
# Find all Converter classes
query: "Converter"
kinds: "Class"
limit: 30

# Get document outline
mode: "document"
path: "/absolute/path/to/file.dart"

# Find all methods containing "calculate"
query: "calculate"
kinds: "Method"
```

**Best Use Cases:**
- Finding class definitions quickly
- Getting a file's structure/outline
- Locating methods by name pattern
- Understanding what symbols exist in a module

---

### 2. Call Hierarchy (`symbol_calls`)

Find who calls a function/method (incoming) or what it calls (outgoing).

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | **Absolute path** to file containing symbol |
| `symbol` | string | Qualified name: `ClassName.methodName` |
| `nodeId` | string | Alternative: Flowspace ID |
| `direction` | string | `incoming` (callers) or `outgoing` (callees) |
| `enrichWithFlowspaceIds` | boolean | Add Flowspace IDs to results (slower) |

**Important:** Requires absolute paths and fully qualified symbol names.

**Examples:**

```
# Who calls _calculateTAS?
path: "/Users/.../lib/services/converters/tas_converter.dart"
symbol: "TasConverter._calculateTAS"
direction: "incoming"

# What does createCompositeResult call?
path: "/Users/.../lib/services/converters/tas_converter.dart"
symbol: "TasConverter.createCompositeResult"
direction: "outgoing"
```

**Best Use Cases:**
- Understanding how a method is used throughout the codebase
- Tracing data flow through the application
- Impact analysis before refactoring
- Finding entry points to functionality

---

### 3. Reference/Implementation Navigation (`symbol_navigate`)

Find all references to a symbol or find implementations of an interface/abstract class.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | **Absolute path** to file containing symbol |
| `symbol` | string | Symbol name (use qualified name if ambiguous) |
| `nodeId` | string | Alternative: Flowspace ID |
| `action` | string | `references` or `implementations` |
| `includeDeclaration` | boolean | Include the declaration itself |
| `enrichWithFlowspaceIds` | boolean | Add Flowspace IDs to results |

**Examples:**

```
# Find all references to DistanceConverter
path: "/Users/.../lib/services/converters/distance_converter.dart"
symbol: "DistanceConverter"
action: "references"

# Find implementations of Converter interface
path: "/Users/.../lib/services/converters/converter.dart"
symbol: "Converter"
action: "implementations"
```

**Best Use Cases:**
- Finding all usages of a class/method before renaming
- Discovering which classes implement an interface
- Understanding coupling between modules
- Verifying test coverage locations

---

### 4. Diagnostics (`diagnostic_collect`)

Gather compiler errors, warnings, and linting issues from VS Code.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | Optional: specific file path (omit for workspace-wide) |

**Response includes:**
- File location (path, line, column)
- Message and severity (error, warning, info)
- Diagnostic code and source (dart, cSpell, etc.)
- System info (VS Code version, platform)
- Debug session status

**Best Use Cases:**
- Checking for compile errors after edits
- Finding unused variables/imports to clean up
- Identifying type errors before running tests
- Getting quick feedback on code health

---

### 5. Editor Context (`editor_get_context`)

Get the current state of VS Code's active editor.

**Returns:**
- Current file path and language
- Cursor position (line, column)
- Selection state
- Containing symbol scope (when available)

**Best Use Cases:**
- Understanding what file the user is looking at
- Getting context for targeted assistance
- Orienting to the user's current focus

---

### 6. Bridge Status (`bridge_status`)

Check if the VS Code bridge is healthy and responsive.

**Best Use Cases:**
- Verify connectivity before using other tools
- Diagnose connection issues
- Check last seen timestamp

---

### 7. Symbol Rename (`symbol_rename`)

Rename symbols workspace-wide with LSP support.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | **Absolute path** to file containing symbol |
| `symbol` | string | Current symbol name |
| `newName` | string | New name for the symbol |

**Best Use Cases:**
- Safe refactoring with automatic reference updates
- Renaming classes, methods, variables across codebase

---

## Common Patterns

### Pattern 1: Understanding a Class

```
1. search_symbol_search (mode: document, path: /path/to/file.dart)
   → Get class outline with all methods/fields

2. symbol_navigate (symbol: ClassName, action: references)
   → See where it's used

3. symbol_calls (symbol: ClassName.methodName, direction: incoming)
   → Trace specific method usage
```

### Pattern 2: Pre-Refactoring Analysis

```
1. symbol_navigate (action: references)
   → Find all usages

2. symbol_calls (direction: incoming)
   → Understand call sites

3. diagnostic_collect
   → Check current code health
```

### Pattern 3: Exploring Inheritance

```
1. search_symbol_search (query: InterfaceName, kinds: Class,Interface)
   → Find the interface

2. symbol_navigate (action: implementations)
   → Find all implementing classes
```

---

## Important Notes

### Path Handling

Tools accept both **relative and absolute paths**:
- **Relative:** `lib/services/converter.dart` (relative to workspace root)
- **Absolute:** `/Users/jordanknight/github/mini-flight-bag/lib/services/converter.dart`

Relative paths are resolved against the VS Code workspace root.

### Qualified Symbol Names

When symbols are ambiguous (e.g., multiple classes named `Converter`), use qualified names:
- **Qualified:** `TasConverter._calculateTAS`
- **Simple:** `_calculateTAS` (may fail if ambiguous)

### Symbol Kinds

Valid kinds for filtering:
- `Class`, `Interface`, `Enum`
- `Method`, `Function`, `Constructor`
- `Field`, `Property`, `Variable`
- `Module`, `Namespace`

### Performance Considerations

- `enrichWithFlowspaceIds: true` adds overhead - use only when needed
- Large `limit` values increase response time
- Document mode is faster than workspace search for single files

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "File not found" | Check path exists, try absolute path |
| "Symbol not found" | Use qualified name (ClassName.method) |
| "Ambiguous symbol" | Add class prefix to disambiguate |
| Bridge unhealthy | Check VS Code is running, restart if needed |
| No results | Verify file is open/indexed in VS Code |

---

## When to Use vs. Traditional Search

| Task | Use Wormhole | Use Grep/Glob |
|------|--------------|---------------|
| Find class definition | `search_symbol_search` | - |
| Find text in comments | - | `Grep` |
| Get file outline | `search_symbol_search` (document mode) | - |
| Find string literals | - | `Grep` |
| Find method callers | `symbol_calls` | - |
| Find file by pattern | - | `Glob` |
| Find implementations | `symbol_navigate` | - |
| Search in specific dirs | - | `Grep` with path |
