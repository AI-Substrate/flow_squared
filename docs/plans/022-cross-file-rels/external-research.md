You can get a *useful* cross-language relationship graph with Tree-sitter + Python-only packaging, but you need to be explicit about the target fidelity:

* **High precision / high coverage:** file-to-file dependencies (imports/includes/links/$ref/etc.)
* **Medium precision / medium coverage:** symbol-to-symbol resolution for *explicitly named* things (e.g., `from x import foo`, `import {foo} from "x"`, `Foo.bar(...)`)
* **Lower precision / lower coverage (but often “good enough”):** member/method resolution off variables (your `p.add`) via light type inference + ranking

Below are the realistic options that stay inside “pip-installable, runnable via uvx, no per-language LSP installs”.

---

## Option 1 (recommended): Build a “good enough” indexer on top of Tree-sitter queries

You already have the hard part (parsing). The missing piece is **an index + resolver** that’s intentionally shallow but scalable across many languages.

### What you build

1. **Dependency extractor (file → file edges)**
   For each file, extract:

   * import/include/require statements
   * string-literal “module specifiers” (`"./calc"`, `"requests"`, `"pkg.Class"`)
   * structured references (Markdown links, YAML/JSON `$ref`, OpenAPI refs, protobuf imports, Terraform modules, etc.)

2. **Definition index (name → locations)**
   Store definitions like:

   * classes
   * functions
   * methods
   * exported/public symbols (when easy)

3. **Reference index (use sites)**
   Store:

   * identifier references (`foo`)
   * member references (`p.add`, `Calc.add`)
   * call sites (so you can answer “who calls what”)

4. **Resolver (best-effort)**
   A deterministic resolver that returns:

   * best match
   * *plus* alternates with a confidence score

### Why this works well in practice

* You’ll cover the majority of “what files relate to what other files” just from imports/links.
* “Go to definition” for imported names is often straightforward.
* Member calls (`p.add`) are the hard case—but you can still do surprisingly well with a few heuristics (below).

### How you implement it with minimal dependencies

* **Parsing:** `tree-sitter` Python bindings are pip-installable and ship wheels. ([PyPI][1])

* **Many languages in one pip dependency:** `tree-sitter-language-pack` bundles 160+ parsers with a simple `get_language/get_parser` API. ([PyPI][2])
  (If you already use `tree-sitter-languages`, same concept; the point is “no compiling grammars at install time”.)

* **Pattern extraction:** Tree-sitter **queries** (S-expression patterns) via `Query` / `QueryCursor` in Python. ([GitHub][3])

### The key design choice: “confidence-scored edges”

Instead of pretending you can always resolve `p.add → Calc.add`, return:

* **Resolved edge (high confidence):** explicit import + explicit class + explicit method
* **Candidate edges (medium/low confidence):** name match + proximity + export likelihood

That makes the system reliable operationally: it’s *honest* about ambiguity.

---

## Option 2: Use Stack Graphs via Python bindings (better “go to definition” where supported)

If you want something closer to SCIP-style “definitions at position” *without* installing language servers, stack graphs are one of the few approaches built specifically for cross-file name binding on top of Tree-sitter.

There’s a pip-installable package:

* `stack-graphs-python-bindings`
  It exposes an `Indexer` and a `Querier` and can return **definitions for a reference at a given (file, line, column)** for supported languages. ([PyPI][4])

**Pros**

* More principled name resolution than DIY heuristics for the languages it supports.
* No per-language LSP install.

**Cons / risks**

* Language coverage is limited (the package itself references Java/Python/TypeScript/JavaScript as the supported set). ([PyPI][4])
* The upstream `github/stack-graphs` repository was archived (read-only) in 2025, which is a maintenance risk if you’re betting on it long-term. ([GitHub][5])
* Stack graphs help mostly with **name binding**; they do not magically solve full type-driven member dispatch in dynamic code.

**Where it fits best**

* You implement Option 1 as your universal baseline.
* For the subset of languages where stack graphs are strong, you plug it in as a “high confidence resolver”.

---

## Option 3: `graph-sitter` (turnkey, but limited language set)

`graph-sitter` is a pip-installable library that advertises building a graph of functions/classes/imports/usages on top of Tree-sitter (and uses `rustworkx` internally). It explicitly states support for Python/TypeScript/JavaScript/React codebases. ([PyPI][6])

**Pros**

* Very close to what you’re describing (graph + usages).
* Python package, CLI support, designed for large-scale refactors. ([PyPI][6])

**Cons**

* Not “hundreds of formats”.
* You’re adopting its model and constraints (including Python version constraints).

If your “core” languages are in its supported set, it can save significant build time.

---

## Option 4: Semgrep as a cross-language relationship extractor (pattern-based, not semantic)

Semgrep is pip-installable with wheels. ([PyPI][7])
It is excellent for:

* “find all imports of X”
* “find all call sites matching pattern Y”
* some interfile analysis modes (depending on product/features)

But it is fundamentally **pattern matching**, not “true go-to-definition”.

Use it if:

* you want a quick way to extract edges like imports/requires/calls-with-known-name
* you’re okay with not resolving member dispatch (`p.add`) beyond heuristics

---

## If you want “good enough” member resolution (`var p = new Calc(); p.add(...)`) without LSP

You won’t solve this universally across hundreds of languages without doing *some* language-specific work, but you can do an 80/20 solution with a small set of reusable heuristics.

### Heuristic recipe (portable across many languages)

When you see a member reference like:

* receiver: `p`
* member: `add`

Try to infer a type for `p` using **nearest dominating assignment/declaration** patterns:

**Tier 1: Explicit type declarations (high confidence)**

* Java/C#/C++: `Calc p = ...`
* TS: `let p: Calc = ...`
* Python: `p: Calc = ...`

**Tier 2: Constructor patterns (high confidence)**

* JS/TS: `const p = new Calc(...)`
* Python: `p = Calc(...)`  *(constructor call heuristic)*
* Ruby: `p = Calc.new(...)`
* Rust: `let p = Calc::new(...)`
* Go: `p := &Calc{...}` or `p := new(Calc)`

**Tier 3: Simple assignment propagation (medium confidence)**

* `p2 = p` implies `type(p2) = type(p)` if `type(p)` known

Then resolve `Calc` to a file:

1. Check imports in scope that bind `Calc` (JS `import`, Python `from`, Java `import`, etc.)
2. If not imported, search same package/directory/module namespace for a class named `Calc`
3. Rank candidates by:

   * same folder > same package > elsewhere
   * filename similarity (`calc.*` is a strong hint)
   * export visibility (if you track it)

Finally resolve method:

* look up `Calc.add` in your definition index.

### What you return

* If you found `p`’s type and a unique `Calc.add`: **single target**
* Otherwise: **ranked candidate list** (still very useful for navigation and graph edges)

This approach is deterministic, fast, and works well enough for most “normal” code—even though it will never be perfect.

---

## Practical build plan that stays “one Python tool, many languages”

### 1) Standardize your internal schema

Store everything in a language-agnostic schema:

* `File(path, language, digest, module_id?)`
* `Symbol(id, kind, name, qualname, file, range, container_symbol_id?, exported?)`
* `Reference(id, kind, name, receiver_name?, file, range, context_symbol_id?)`
* `Edge(src_ref_id, dst_symbol_id, edge_kind, confidence, rule_id)`

Keep it simple. SQLite is usually enough.

### 2) Extract dependencies everywhere

For each language/format family, implement extractors:

* “module specifier” extractor (imports/includes/requires)
* “path-like” extractor (Markdown links, JSON `$ref`, YAML anchors, etc.)

This alone gives you a **reliable file-to-file graph**.

### 3) Extract definitions using Tree-sitter queries

Tree-sitter’s Python bindings support query execution via `Query`/`QueryCursor`. ([GitHub][3])
You’ll need per-language queries *for definitions* (classes/functions/methods), but:

* you can start with only the languages you care about most
* for everything else, you still get file-level dependency edges

### 4) Extract references (identifiers + member expressions)

This is easier than definitions (identifiers exist everywhere). Member-expression node shapes differ, but again: target your top languages first.

### 5) Resolve with confidence scoring

Implement the resolver as a pipeline of rules:

* lexical/local resolution
* import-bound resolution
* constructor/type-hint resolution for member calls
* fallback fuzzy match

---

## What I would choose given your constraints

If your goal is “reliable relationships across hundreds of formats” *and* “good enough symbol navigation”:

1. **Baseline:** Option 1 (Tree-sitter + your own index/resolver), because it scales to all your formats and stays dependency-light.
2. **Augment for better go-to-definition:** Add stack graphs bindings *optionally* for JS/TS/Python/Java if you want improved cross-file name binding without LSP installs. ([PyPI][4])
3. **Only if your main languages match:** consider `graph-sitter` as an accelerator, but expect narrower language coverage. ([PyPI][6])

---

## A concrete “good enough” promise (so you can scope it)

You can usually get all of the following without LSP and without per-language heavy tooling:

* **100% of explicit file dependencies** (imports/includes/links)
* **High-quality go-to-definition for imported symbols**
* **Decent member/method resolution** when:

  * the receiver is declared with a type, or
  * the receiver is assigned from an obvious constructor (`new X`, `X()`, `X.new`, etc.)

And you’ll still have graceful degradation (ranked candidates) in dynamic/ambiguous cases.

---

If you want, I can sketch a reference implementation structure (modules/classes + SQLite schema + a first pass for Python + JS/TS) that you can drop into your project. The key is making “language plugins” very small: mostly just a handful of Tree-sitter queries for **imports**, **definitions**, **member references**, and **constructor assignments**.

[1]: https://pypi.org/project/tree-sitter/?utm_source=chatgpt.com "Python Tree-sitter"
[2]: https://pypi.org/project/tree-sitter-language-pack/ "tree-sitter-language-pack · PyPI"
[3]: https://github.com/tree-sitter/py-tree-sitter "GitHub - tree-sitter/py-tree-sitter: Python bindings to the Tree-sitter parsing library"
[4]: https://pypi.org/project/stack-graphs-python-bindings/ "stack-graphs-python-bindings · PyPI"
[5]: https://github.com/github/stack-graphs/blob/main/.github/workflows/publish-tree-sitter-stack-graphs.yml?utm_source=chatgpt.com "publish-tree-sitter-stack-graphs.yml"
[6]: https://pypi.org/project/graph-sitter/ "graph-sitter · PyPI"
[7]: https://pypi.org/project/semgrep/ "semgrep · PyPI"
