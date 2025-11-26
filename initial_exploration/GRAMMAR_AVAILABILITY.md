# Grammar Availability Report

**Generated**: 2025-11-26
**Package**: `tree-sitter-language-pack==0.11.0`
**tree-sitter**: `0.25.2`

---

## Target Languages Status

All 16 target languages are **AVAILABLE** in the language pack.

| Format | Grammar Name | Status | Notes |
|--------|--------------|--------|-------|
| Python | `python` | AVAILABLE | |
| JavaScript | `javascript` | AVAILABLE | |
| TypeScript | `typescript` | AVAILABLE | Also: `tsx` for JSX |
| Go | `go` | AVAILABLE | Also: `gomod`, `gosum` |
| Rust | `rust` | AVAILABLE | |
| C++ | `cpp` | AVAILABLE | Also: `c`, `cuda` |
| C# | `csharp` | AVAILABLE | Note: NOT `c_sharp` |
| Dart | `dart` | AVAILABLE | |
| Markdown | `markdown` | AVAILABLE | Also: `markdown_inline` |
| Terraform | `hcl` | AVAILABLE | Use `hcl` not `terraform` |
| Dockerfile | `dockerfile` | AVAILABLE | |
| YAML | `yaml` | AVAILABLE | |
| JSON | `json` | AVAILABLE | Also: `jsonnet` |
| TOML | `toml` | AVAILABLE | |
| SQL | `sql` | AVAILABLE | |
| Shell | `bash` | AVAILABLE | Also: `fish`, `powershell` |

---

## Extension to Grammar Mapping

Use this mapping in `parse_to_json.py`:

```python
EXTENSION_TO_GRAMMAR = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'tsx',
    '.go': 'go',
    '.rs': 'rust',
    '.cpp': 'cpp',
    '.cc': 'cpp',
    '.cxx': 'cpp',
    '.hpp': 'cpp',
    '.h': 'cpp',  # Ambiguous: could be C
    '.cs': 'csharp',
    '.dart': 'dart',
    '.md': 'markdown',
    '.tf': 'hcl',
    '.hcl': 'hcl',
    'Dockerfile': 'dockerfile',  # No extension
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.json': 'json',
    '.toml': 'toml',
    '.sql': 'sql',
    '.sh': 'bash',
    '.bash': 'bash',
}
```

---

## Total Available Grammars

The language pack includes **172 grammars** total. Notable additional languages:

### Programming Languages
- Java, Kotlin, Scala (JVM)
- Swift, Objective-C (Apple)
- Ruby, Perl, PHP (Scripting)
- Haskell, OCaml, F#, Elm (Functional)
- Lua, Julia, R (Scientific/Scripting)
- Zig, Nim, Odin (Modern systems)
- Solidity (Blockchain)

### Markup & Config
- HTML, XML, CSS, SCSS
- LaTeX, RST, Org
- INI, Properties
- Protobuf, GraphQL, Thrift

### Domain-Specific
- Makefile, CMake, Ninja, Meson (Build)
- Nix (Package management)
- Vim, Elisp (Editor configs)
- GLSL, HLSL, WGSL (Shaders)
- Verilog, VHDL (Hardware)

---

## API Usage

```python
from tree_sitter_language_pack import get_parser, get_language

# Get a parser for a language
parser = get_parser('python')

# Parse source code
source = b'def foo(): pass'
tree = parser.parse(source)
root = tree.root_node

# Access node properties
print(root.type)        # 'module'
print(root.start_byte)  # 0
print(root.end_byte)    # 15
```

---

## Gotchas Discovered

1. **C# grammar name**: Use `csharp` (no underscore), not `c_sharp`
2. **Terraform**: Use `hcl` grammar, not `terraform`
3. **Dockerfile**: Special case - filename is `Dockerfile` (no extension)
4. **Ambiguous `.h` files**: Could be C or C++ - we default to `cpp`
5. **TypeScript vs TSX**: Use `typescript` for `.ts`, `tsx` for `.tsx`
