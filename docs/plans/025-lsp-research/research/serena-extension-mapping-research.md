# Serena Extension Mapping Research

**Date**: 2026-01-15
**Purpose**: Understand Serena's file extension to language mapping for adoption in fs2 Phase 0b
**Source**: `/workspaces/flow_squared/scratch/serena/src/solidlsp/ls_config.py`

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [FilenameMatcher Class](#filenamematcher-class)
4. [Language Enum](#language-enum)
5. [Extension Mapping Strategy](#extension-mapping-strategy)
6. [Complete Extension Reference](#complete-extension-reference)
7. [Liftability Assessment for fs2](#liftability-assessment-for-fs2)
8. [Recommendations](#recommendations)

---

## Executive Summary

Serena uses a **two-component pattern** for file extension to language mapping:

1. **`FilenameMatcher`**: A simple class that wraps `fnmatch` glob patterns
2. **`Language.get_source_fn_matcher()`**: A method on the Language enum returning a FilenameMatcher per language

### Key Design Decisions

| Decision | Serena's Approach | Rationale |
|----------|-------------------|-----------|
| Pattern type | `fnmatch` globs (not regex) | Simpler, faster, familiar Unix syntax |
| Storage location | Method on Language enum | Keeps extensions with their language |
| Variant handling | Algorithmic generation for TypeScript | Handles 12 variants (ESM/CJS/JSX) |
| Matching direction | Filename → Language (via iteration) | Allows priority-based resolution |

### Critical Finding for fs2

Serena's approach is **fundamentally different** from our planned `EXTENSION_MAP` dict:

| Aspect | fs2 Plan (Original) | Serena's Approach |
|--------|---------------------|-------------------|
| Data structure | `dict[str, Language]` | `Language.get_source_fn_matcher() -> FilenameMatcher` |
| Lookup direction | Extension → Language | Language → FilenameMatcher, then iterate |
| Pattern support | Exact match only | Glob patterns (`*.tsx`, `*.py*`) |
| Extensibility | Add dict entries | Add patterns to enum method |

---

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        ls_config.py                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐      ┌──────────────────────────────┐ │
│  │   FilenameMatcher   │      │      Language (Enum)          │ │
│  │   ─────────────────│      │   ────────────────────────── │ │
│  │   patterns: tuple   │◄─────│   get_source_fn_matcher()    │ │
│  │   is_relevant_      │      │   get_ls_class()             │ │
│  │   filename(fn)      │      │   get_priority()             │ │
│  └─────────────────────┘      │   is_experimental()          │ │
│           │                    └──────────────────────────────┘ │
│           │                                 │                    │
│           ▼                                 ▼                    │
│   fnmatch.fnmatch()              42 language variants           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### File Location

**Source**: `/workspaces/flow_squared/scratch/serena/src/solidlsp/ls_config.py`

| Component | Lines | Purpose |
|-----------|-------|---------|
| `FilenameMatcher` | 15-26 | Pattern matching wrapper |
| `Language` enum | 29-102 | 42 language definitions |
| `get_source_fn_matcher()` | 149-243 | Extension patterns per language |
| `get_ls_class()` | 245-430 | LSP server class per language |

---

## FilenameMatcher Class

### Source Code (lines 15-26)

```python
class FilenameMatcher:
    def __init__(self, *patterns: str) -> None:
        """
        :param patterns: fnmatch-compatible patterns
        """
        self.patterns = patterns

    def is_relevant_filename(self, fn: str) -> bool:
        for pattern in self.patterns:
            if fnmatch.fnmatch(fn, pattern):
                return True
        return False
```

### Design Analysis

| Aspect | Implementation | Notes |
|--------|----------------|-------|
| **Pattern storage** | `tuple[str, ...]` via `*patterns` | Immutable, memory-efficient |
| **Matching** | `fnmatch.fnmatch()` | Unix shell-style wildcards |
| **Short-circuit** | Returns on first match | Performance optimization |
| **Case sensitivity** | Platform-dependent | `fnmatch` follows OS behavior |

### fnmatch Pattern Syntax

| Pattern | Matches | Example |
|---------|---------|---------|
| `*` | Any characters | `*.py` matches `foo.py` |
| `?` | Single character | `?.py` matches `a.py` |
| `[seq]` | Any char in seq | `[abc].py` matches `a.py` |
| `[!seq]` | Any char not in seq | `[!a].py` matches `b.py` |

### Why fnmatch, Not Regex?

1. **Simpler syntax** - No escaping needed for `.`
2. **Faster** - Compiled to simple string ops
3. **Familiar** - Same as shell globbing
4. **Sufficient** - File extensions don't need regex power

---

## Language Enum

### Enum Definition (lines 29-102)

```python
class Language(str, Enum):
    """
    Enumeration of language servers supported by SolidLSP.
    """
    CSHARP = "csharp"
    PYTHON = "python"
    RUST = "rust"
    JAVA = "java"
    KOTLIN = "kotlin"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUBY = "ruby"
    DART = "dart"
    CPP = "cpp"
    # ... 32 more languages

    # Experimental/deprecated variants
    TYPESCRIPT_VTS = "typescript_vts"
    PYTHON_JEDI = "python_jedi"
    CSHARP_OMNISHARP = "csharp_omnisharp"
    # ... more experimental
```

### Key Methods

| Method | Purpose | Returns |
|--------|---------|---------|
| `get_source_fn_matcher()` | Extension patterns | `FilenameMatcher` |
| `get_ls_class()` | LSP server class | `type[SolidLanguageServer]` |
| `get_priority()` | Tie-breaking priority | `int` (0-2) |
| `is_experimental()` | Check if experimental | `bool` |
| `iter_all()` | Iterate languages | `Iterable[Language]` |

### Experimental Languages

These are NOT auto-detected and must be explicitly specified:

```python
def is_experimental(self) -> bool:
    return self in {
        self.TYPESCRIPT_VTS,
        self.PYTHON_JEDI,
        self.CSHARP_OMNISHARP,
        self.RUBY_SOLARGRAPH,
        self.MARKDOWN,
        self.YAML,
        self.TOML,
        self.GROOVY,
    }
```

### Priority System

Used for tie-breaking when multiple languages match:

```python
def get_priority(self) -> int:
    if self.is_experimental():
        return 0  # Lowest
    match self:
        case self.VUE:
            return 1  # Vue is superset of TypeScript
        case _:
            return 2  # Regular languages
```

---

## Extension Mapping Strategy

### Three Patterns Used

#### 1. Simple Explicit Patterns (Most Languages)

```python
case self.JAVA:
    return FilenameMatcher("*.java")
case self.GO:
    return FilenameMatcher("*.go")
case self.CSHARP:
    return FilenameMatcher("*.cs")
```

#### 2. Multiple Variant Patterns (Complex Languages)

```python
case self.CPP:
    return FilenameMatcher("*.cpp", "*.h", "*.hpp", "*.c", "*.hxx", "*.cc", "*.cxx")

case self.FORTRAN:
    return FilenameMatcher(
        "*.f90", "*.F90", "*.f95", "*.F95", "*.f03", "*.F03",
        "*.f08", "*.F08", "*.f", "*.F", "*.for", "*.FOR", "*.fpp", "*.FPP"
    )

case self.CLOJURE:
    return FilenameMatcher("*.clj", "*.cljs", "*.cljc", "*.edn")
```

#### 3. Algorithmic Generation (TypeScript/Vue)

```python
case self.TYPESCRIPT | self.TYPESCRIPT_VTS:
    # see https://github.com/oraios/serena/issues/204
    path_patterns = []
    for prefix in ["c", "m", ""]:      # c=CommonJS, m=ESM, ""=regular
        for postfix in ["x", ""]:       # x=JSX/TSX, ""=plain
            for base_pattern in ["ts", "js"]:
                path_patterns.append(f"*.{prefix}{base_pattern}{postfix}")
    return FilenameMatcher(*path_patterns)
```

**Generated patterns** (12 total):
```
*.cts  *.cjs   # CommonJS TypeScript/JavaScript
*.ctx  *.cjx   # CommonJS with JSX (rare)
*.mts  *.mjs   # ES Module TypeScript/JavaScript
*.mtx  *.mjx   # ES Module with JSX (rare)
*.ts   *.js    # Standard TypeScript/JavaScript
*.tsx  *.jsx   # JSX/TSX variants
```

### Why Algorithmic Generation?

1. **Combinatorial explosion** - 3 prefixes × 2 postfixes × 2 bases = 12 patterns
2. **Future-proof** - Easy to add new prefix/postfix variants
3. **DRY** - Avoids listing all 12 patterns manually
4. **Referenced issue** - https://github.com/oraios/serena/issues/204 (JSX support)

---

## Complete Extension Reference

### Tier 1: fs2 Target Languages

| Language | Enum Value | Patterns | Notes |
|----------|------------|----------|-------|
| **Python** | `PYTHON` | `*.py`, `*.pyi` | Stub files included, `.pyx` (Cython) excluded |
| **TypeScript** | `TYPESCRIPT` | 12 patterns (algorithmic) | Includes all JS variants |
| **Go** | `GO` | `*.go` | Simple, no variants |
| **C#** | `CSHARP` | `*.cs` | `.csx` scripts excluded |

### Tier 2: Common Languages

| Language | Enum Value | Patterns |
|----------|------------|----------|
| Java | `JAVA` | `*.java` |
| Rust | `RUST` | `*.rs` |
| Ruby | `RUBY` | `*.rb`, `*.erb` |
| C++ | `CPP` | `*.cpp`, `*.h`, `*.hpp`, `*.c`, `*.hxx`, `*.cc`, `*.cxx` |
| Kotlin | `KOTLIN` | `*.kt`, `*.kts` |
| Dart | `DART` | `*.dart` |
| PHP | `PHP` | `*.php` |
| Swift | `SWIFT` | `*.swift` |

### Tier 3: Scripting Languages

| Language | Enum Value | Patterns |
|----------|------------|----------|
| Bash | `BASH` | `*.sh`, `*.bash` |
| PowerShell | `POWERSHELL` | `*.ps1`, `*.psm1`, `*.psd1` |
| Lua | `LUA` | `*.lua` |
| Perl | `PERL` | `*.pl`, `*.pm`, `*.t` |
| R | `R` | `*.R`, `*.r`, `*.Rmd`, `*.Rnw` |

### Tier 4: Functional/Specialized

| Language | Enum Value | Patterns |
|----------|------------|----------|
| Haskell | `HASKELL` | `*.hs`, `*.lhs` |
| Scala | `SCALA` | `*.scala`, `*.sbt` |
| Clojure | `CLOJURE` | `*.clj`, `*.cljs`, `*.cljc`, `*.edn` |
| Elixir | `ELIXIR` | `*.ex`, `*.exs` |
| Erlang | `ERLANG` | `*.erl`, `*.hrl`, `*.escript`, `*.config`, `*.app`, `*.app.src` |
| F# | `FSHARP` | `*.fs`, `*.fsx`, `*.fsi` |
| Julia | `JULIA` | `*.jl` |
| Fortran | `FORTRAN` | 14 patterns (case variants) |

### Tier 5: Infrastructure/Config

| Language | Enum Value | Patterns |
|----------|------------|----------|
| Terraform | `TERRAFORM` | `*.tf`, `*.tfvars`, `*.tfstate` |
| Nix | `NIX` | `*.nix` |
| YAML | `YAML` | `*.yaml`, `*.yml` |
| TOML | `TOML` | `*.toml` |
| Rego | `REGO` | `*.rego` |

### Tier 6: Other

| Language | Enum Value | Patterns |
|----------|------------|----------|
| Vue | `VUE` | `*.vue` + all TypeScript patterns (13 total) |
| Elm | `ELM` | `*.elm` |
| Zig | `ZIG` | `*.zig`, `*.zon` |
| Pascal | `PASCAL` | `*.pas`, `*.pp`, `*.lpr`, `*.dpr`, `*.dpk`, `*.inc` |
| Groovy | `GROOVY` | `*.groovy`, `*.gvy` |
| MATLAB | `MATLAB` | `*.m`, `*.mlx`, `*.mlapp` |
| AL | `AL` | `*.al`, `*.dal` |
| Markdown | `MARKDOWN` | `*.md`, `*.markdown` |

---

## Liftability Assessment for fs2

### What to Lift

#### 1. FilenameMatcher Class ⭐⭐⭐⭐⭐

**Lift as-is** with minor modifications:

```python
# fs2 adaptation
import fnmatch
from typing import Sequence

class FilenameMatcher:
    """Match filenames against fnmatch glob patterns."""

    __slots__ = ("patterns",)

    def __init__(self, patterns: Sequence[str]) -> None:
        self.patterns = tuple(patterns)

    def matches(self, filename: str) -> bool:
        """Return True if filename matches any pattern."""
        return any(fnmatch.fnmatch(filename, p) for p in self.patterns)
```

**Changes from Serena**:
- Use `Sequence[str]` instead of `*patterns` for type clarity
- Add `__slots__` for memory efficiency
- Rename `is_relevant_filename` → `matches` for clarity

#### 2. Pattern-on-Enum Pattern ⭐⭐⭐⭐⭐

**Adopt the pattern** of storing patterns on the Language enum:

```python
class Language(str, Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    GO = "go"
    CSHARP = "csharp"

    @property
    def file_patterns(self) -> tuple[str, ...]:
        """Return fnmatch patterns for files of this language."""
        match self:
            case Language.PYTHON:
                return ("*.py", "*.pyi")
            case Language.TYPESCRIPT:
                return self._typescript_patterns()
            case Language.GO:
                return ("*.go",)
            case Language.CSHARP:
                return ("*.cs",)

    @staticmethod
    def _typescript_patterns() -> tuple[str, ...]:
        """Generate TypeScript patterns algorithmically."""
        patterns = []
        for prefix in ("c", "m", ""):
            for postfix in ("x", ""):
                for base in ("ts", "js"):
                    patterns.append(f"*.{prefix}{base}{postfix}")
        return tuple(patterns)
```

#### 3. Extension-to-Language Lookup

**Serena's approach**: Iterate all languages, check each matcher

```python
@classmethod
def from_filename(cls, filename: str) -> "Language | None":
    """Infer language from filename using pattern matching."""
    for lang in cls:
        if lang.file_matcher.matches(filename):
            return lang
    return None
```

**Alternative (optimized)**: Build reverse lookup on first use

```python
@classmethod
def from_extension(cls, ext: str) -> "Language | None":
    """Infer language from file extension."""
    if not hasattr(cls, "_ext_cache"):
        cls._ext_cache = cls._build_extension_cache()
    return cls._ext_cache.get(ext.lower())

@classmethod
def _build_extension_cache(cls) -> dict[str, "Language"]:
    """Build extension → language lookup cache."""
    cache = {}
    for lang in cls:
        for pattern in lang.file_patterns:
            # Extract extension from pattern like "*.tsx"
            if pattern.startswith("*."):
                ext = pattern[1:]  # ".tsx"
                if ext not in cache:  # First match wins
                    cache[ext] = lang
    return cache
```

### What NOT to Lift

| Component | Reason |
|-----------|--------|
| `get_ls_class()` | LSP server instantiation - Phase 3+ concern |
| `get_priority()` | Multi-language tie-breaking - not needed for root detection |
| `is_experimental()` | Serena-specific categorization |
| 38 extra languages | Only need Python, TypeScript, Go, C# for Phase 0b |

---

## Recommendations

### For Phase 0b (T006a: Language Enum)

#### Option A: Simple Patterns Property (Recommended)

```python
# scripts/lsp/language.py

from enum import Enum
from typing import ClassVar

class Language(str, Enum):
    """Supported languages for project root detection."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    GO = "go"
    CSHARP = "csharp"

    @property
    def markers(self) -> tuple[str, ...]:
        """Return project marker files (priority order)."""
        match self:
            case Language.PYTHON:
                return ("pyproject.toml", "setup.py", "setup.cfg")
            case Language.TYPESCRIPT:
                return ("tsconfig.json", "package.json")
            case Language.GO:
                return ("go.mod",)
            case Language.CSHARP:
                return (".csproj", ".sln")

    @property
    def file_patterns(self) -> tuple[str, ...]:
        """Return fnmatch patterns for source files."""
        match self:
            case Language.PYTHON:
                return ("*.py", "*.pyi")
            case Language.TYPESCRIPT:
                return self._typescript_patterns()
            case Language.GO:
                return ("*.go",)
            case Language.CSHARP:
                return ("*.cs",)

    @staticmethod
    def _typescript_patterns() -> tuple[str, ...]:
        """Generate TypeScript/JavaScript patterns algorithmically."""
        patterns = []
        for prefix in ("c", "m", ""):
            for postfix in ("x", ""):
                for base in ("ts", "js"):
                    patterns.append(f"*.{prefix}{base}{postfix}")
        return tuple(patterns)

    @classmethod
    def from_filename(cls, filename: str) -> "Language | None":
        """Infer language from filename using pattern matching."""
        import fnmatch
        for lang in cls:
            for pattern in lang.file_patterns:
                if fnmatch.fnmatch(filename, pattern):
                    return lang
        return None
```

**Pros**:
- Clean, self-contained enum
- Both `markers` and `file_patterns` on same class
- Serena's algorithmic TypeScript pattern generation
- No separate FilenameMatcher class needed

**Cons**:
- Iterates all languages on each lookup (4 languages = trivial)

#### Option B: With Cached Lookup (If Performance Matters)

Add caching for high-volume lookups:

```python
_EXTENSION_CACHE: ClassVar[dict[str, "Language"] | None] = None

@classmethod
def from_extension(cls, ext: str) -> "Language | None":
    """Infer language from extension (cached)."""
    if cls._EXTENSION_CACHE is None:
        cls._EXTENSION_CACHE = {}
        for lang in cls:
            for pattern in lang.file_patterns:
                if pattern.startswith("*."):
                    file_ext = pattern[1:]  # ".tsx"
                    if file_ext not in cls._EXTENSION_CACHE:
                        cls._EXTENSION_CACHE[file_ext] = lang
    return cls._EXTENSION_CACHE.get(ext.lower())
```

### Summary Decision

| Approach | Complexity | Performance | Serena Alignment |
|----------|------------|-------------|------------------|
| **Option A** | CS-2 | Adequate | High |
| Option B | CS-2 | Better | High |

**Recommendation**: Start with **Option A** (simple iteration). 4 languages × ~5 patterns = 20 checks per file. Only optimize if profiling shows issues.

---

## Appendix: TypeScript Pattern Matrix

The algorithmic generation produces these 12 patterns:

| Prefix | Base | Postfix | Pattern | Description |
|--------|------|---------|---------|-------------|
| `c` | `ts` | `` | `*.cts` | CommonJS TypeScript |
| `c` | `ts` | `x` | `*.ctx` | CommonJS TypeScript JSX (rare) |
| `c` | `js` | `` | `*.cjs` | CommonJS JavaScript |
| `c` | `js` | `x` | `*.cjx` | CommonJS JavaScript JSX (rare) |
| `m` | `ts` | `` | `*.mts` | ES Module TypeScript |
| `m` | `ts` | `x` | `*.mtx` | ES Module TypeScript JSX (rare) |
| `m` | `js` | `` | `*.mjs` | ES Module JavaScript |
| `m` | `js` | `x` | `*.mjx` | ES Module JavaScript JSX (rare) |
| `` | `ts` | `` | `*.ts` | Standard TypeScript |
| `` | `ts` | `x` | `*.tsx` | TypeScript JSX (React) |
| `` | `js` | `` | `*.js` | Standard JavaScript |
| `` | `js` | `x` | `*.jsx` | JavaScript JSX (React) |

**Note**: `*.ctx`, `*.cjx`, `*.mtx`, `*.mjx` are technically valid but rarely used. The algorithm includes them for completeness.

---

## References

- **Source file**: `/workspaces/flow_squared/scratch/serena/src/solidlsp/ls_config.py`
- **Issue #204**: https://github.com/oraios/serena/issues/204 (JSX support)
- **Python fnmatch docs**: https://docs.python.org/3/library/fnmatch.html
