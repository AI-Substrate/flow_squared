Feasibility of a Generic Headless LSP Harness
Developing a generic, headless LSP client harness for multiple languages is feasible because the Language Server Protocol defines a common set of requests for code intelligence. In principle, one can issue the same JSON-RPC requests – such as textDocument/definition, textDocument/references, textDocument/documentSymbol, workspace/symbol, etc. – to any compliant language server. All major LSP servers support a core set of features like go-to-definition and find-references, though the completeness of cross-file analysis varies by language and server. A single harness can manage multiple language servers by lazily launching each one for the languages detected, minimizing per-language custom code. Minimal wrapper logic is needed mainly to start the correct server with proper initialization settings (e.g. project path or config), since the query interface is standardized
.
Consistency of LSP Feature Support Across Languages
Most LSP implementations for popular languages implement cross-file semantic queries in a consistent way. Once a language server is running, the client can send uniform requests for features like:
Find all references (textDocument/references),
Go to definition (textDocument/definition),
Go to type definition (textDocument/typeDefinition),
Go to implementation (textDocument/implementation),
Document symbols (outline) (textDocument/documentSymbol),
Workspace-wide symbol search (workspace/symbol).
These requests have the same shape regardless of language. In practice, support is strong for definitions and references (virtually every mature server implements these), and decent for document/workspace symbols. Support for type definitions and implementations is present in languages where those concepts apply (e.g. static languages with explicit types or interfaces) but may be omitted in dynamic languages. The table below summarizes the best-known LSP server for each target language and whether it supports the key cross-file semantic requests:
Language	Major LSP Server	Definitions	References	Type Definitions	Implementations	Document Symbols	Workspace Symbols
C++	Clangd (LLVM)	Yes ✅
Yes ✅
Yes (since Clangd 11+) ✅
Partial (no formal “interface” in C++, but finds subclass overrides via references) ✅
Yes ✅ (outline of classes/functions)	Yes ✅
Rust	rust-analyzer (Official)	Yes ✅
Yes ✅
N/A (dynamic types)	Yes ✅ (find impls of traits)	Yes ✅ (module/function symbols)	Yes ✅ (search by name)
Ruby	Solargraph (Gem)	Yes (best-effort) ✅
Yes (best-effort) ✅ (via YARD docs)	N/A (dynamic typing)	N/A (no static interfaces)	Yes ✅ (classes, methods per file)	Yes ✅ (global symbol search)
Ruby (alt)	Shopify Ruby LSP	Limited ❌ (Go-to-def added recently, ~2024)
No ❌ (not yet supported)
No ❌
No ❌
Yes ✅ (basic outline)	No (focus on core features only)
GDScript	Godot GDScript LSP	Yes ✅ (jump to node/script)	Yes ✅ (added in Godot 4.2)
N/A (no static types)	N/A (no interface concept)	Yes ✅ (functions, signals, etc.)	Limited (no global search yet)
Bash	bash-language-server	Yes ✅
Yes ✅
N/A	N/A	Yes ✅
Yes ✅
C#	OmniSharp (Roslyn)	Yes ✅
Yes ✅
Yes ✅
Yes ✅
Yes ✅
Yes ✅
Go	gopls (Official)	Yes ✅
Yes ✅
Implicit (types are definitions)	Yes ✅ (find implementers of interfaces)
Yes ✅ (file outline)	Yes ✅
Java	Eclipse JDT LS	Yes ✅ (classes, methods)	Yes ✅ (fields, methods across project)
N/A (objects vs primitives only)	Yes ✅ (find subclass or interface impl)	Yes ✅ (outline by class/method)	Yes ✅ (project-wide symbol search)
JavaScript/TS	TypeScript LS (via tsserver)	Yes ✅ (JS & TS)	Yes ✅ (full project)	Yes ✅ (especially in TS: e.g. go to interface)	Yes ✅ (TS: e.g. find class impl, JS: mostly N/A)	Yes ✅ (outline by file)	Yes ✅ (symbol search via TS project)
Python	Pyright (Microsoft)	Yes ✅ (including across modules)	Yes ✅ (find usages across files)	No ❌ (not in capabilities)
No ❌ (not supported for method overrides)
Yes ✅ (functions, classes per file)	Yes ✅
Table: Support for cross-file semantic LSP requests by language and server. “Yes ✅” indicates the server implements the LSP request. “No ❌” indicates it lacks that feature; “N/A” means the concept doesn’t apply to that language. (Some dynamic languages effectively have no “type definition” or “implementation” concept to navigate.)
Widely-Used Language Servers and Feature Coverage
For each target language, there is a de-facto standard LSP server that is stable, editor-agnostic, and suitable for headless use (no GUI required). These are typically the same servers used in popular editors (VS Code, Vim/Emacs LSP plugins, etc.), and they can all run as standalone processes (often via stdin/stdout or TCP). Below we identify the primary server for each language and its support for cross-file semantic queries:
C++: Clangd (from LLVM) is the most widely used LSP server for C/C++. It provides robust cross-file analysis. It supports go-to-definition and find-references across large codebases. Clangd added support for the textDocument/typeDefinition request (to jump to type declarations) in version 14
. It also supports finding references, including smart handling of C++ inheritance (a references query on a virtual method can return overrides/base references as well)
. Alternatives: ccls is another C++ server with similar goals, but clangd is generally more up-to-date.
Rust: rust-analyzer (the official Rust LSP) is the go-to choice. It implements “go to definition” and “find all references” reliably
, using the Rust compiler’s understanding of Cargo projects. It also supports implementation queries (e.g. jump from a trait to structs that implement it) and has excellent cross-crate analysis, thanks to Rust’s explicit types and the server’s built-in compiler. (The older RLS is deprecated in favor of rust-analyzer.)
Ruby: Solargraph (a Ruby gem) has been the long-standing LSP for Ruby. It supports definitions and references, but due to Ruby’s dynamic nature the results are not always perfect
. Solargraph parses YARD documentation and code to provide suggestions, but “Go to definition works [only about half the time]” in practice for complex metaprogramming
. A newer Ruby LSP by Shopify is emerging, but it currently lacks key semantic features – initially it did not support go-to-definition or find-references at all
. (Recent updates have added basic go-to-def for Ruby ≥3.0
, but references are still not fully implemented as of late 2024.) For a headless harness today, Solargraph remains the more feature-complete choice, albeit with limitations in accuracy.
GDScript (Godot Engine): Godot provides a built-in GDScript language server as part of the engine/editor. In Godot 4.x, this LSP supports completions, definitions, and (since Godot 4.2) cross-file find-references
. It can navigate to scene nodes or other script files for definitions. The GDScript server is a special case: it runs inside the Godot editor or engine process. To use it headlessly, one must launch Godot in editor mode with no GUI (e.g. godot --headless --editor --no-window --lsp-port=<port> --path <project>
). This will start the LSP server listening on the given port. Once running, the server now fully supports references lookups and other queries, making cross-file analysis of GDScript feasible. (In earlier Godot versions, references were not implemented
.) There is no alternative server for GDScript; the official one is used.
Bash: bash-language-server (an open-source Node.js tool) is the standard for shell scripts. It supports cross-file navigation such as jumping to declarations and finding references of functions or variables across scripts
. It builds an AST via Tree-sitter, enabling document symbol outlines and even workspace symbol search
. For example, if a function is defined in one .sh file and used in another, the LSP’s references query should find that usage (provided the project files are open or within the workspace). The server also integrates linters (shellcheck) and formatting, but those are optional. No special wrapper is needed beyond invoking bash-language-server start for the harness.
C#: OmniSharp (Roslyn) is widely used for C# outside Visual Studio. The OmniSharp server can operate in an LSP mode (OmniSharp.exe -lsp) using the Roslyn compiler under the hood. It provides full IDE-like features: go-to-definition, find references, inheritance navigation, etc., comparable to Visual Studio’s capabilities. Indeed, when OmniSharp’s LSP capabilities are inspected, it advertises providers for definitions, type definitions, implementations, references, document symbols, workspace symbols, and more
. This means a generic client can request, for example, textDocument/implementation to list all classes implementing a given interface, or use workspace/symbol to search for a class by name. Note: historically, OmniSharp’s own protocol differed from LSP, but today it can speak standard LSP, making integration easier. The harness should ensure the correct project directory is set so OmniSharp can load the .sln/project files for full cross-file analysis.
Go: gopls (the official Go language server) is built by the Go team and is highly capable. It indexes the entire workspace (respecting Go modules) and supports all relevant LSP requests. For example, textDocument/definition on an identifier will jump to its declaration, even following import paths across files
. A textDocument/references query returns all usages of a symbol, including in other packages (if those packages are within the workspace/module)
. Go’s interface implementation relationships are discoverable via textDocument/implementation – gopls will list all types implementing an interface, or all interface methods that a concrete type fulfills
. The server also provides document symbols (functions, types in a file) and workspace symbol search. Configuration is minimal (it auto-detects the Go module or GOPATH). A generic client can launch gopls and immediately use these features.
Java: Eclipse JDT LS (Java Development Tools Language Server) is the backbone of Java support in VS Code (the Red Hat extension) and others. It is a mature server that deeply understands Java projects (Maven/Gradle classpaths, etc.). JDT LS supports find-references and definitions across project files (and even into library source or stubs if available)
. It can answer textDocument/implementation for interfaces or abstract classes – returning the classes that implement or extend them. It also supports workspace/symbol for global name lookup. The harness will need to launch the JDT LS (which is a Java JAR package) and point it to the project’s classpath settings (often the VS Code extension or jdt.ls launch script handles this). In a headless scenario, a minimal wrapper might be needed to start the JDT LS Java process with the correct workspace directory and initialization options. Once running, the LSP methods are uniform and can be invoked like any other server.
JavaScript/TypeScript: TypeScript Language Server is typically used for both JS and TS. This is often implemented by running the TypeScript compiler’s tsserver under an LSP wrapper (for example, the typescript-language-server npm package). It leverages TypeScript’s own analysis to provide cross-file intelligence. In a TypeScript project, all symbols are typed, so go-to-definition and find-references work reliably across files (including jumping to definitions in dependency files). It supports textDocument/typeDefinition (e.g. go to an interface or type alias that a symbol is an instance of) and textDocument/implementation (e.g. find all class implementations of an interface, or all overrides of a method in subclasses). These features are present in VS Code’s TS support and exposed via the LSP wrapper
. In pure JavaScript, some of these requests may return limited results (since types are inferred, not declared), but the underlying engine still attempts to find references by static analysis of the project. Document symbols (outline of a JS/TS file’s exported functions, classes, etc.) and workspace symbol search by name are also implemented. The harness can spawn typescript-language-server --stdio for a given project (ensuring that tsserver from TypeScript is installed) and then issue the standard requests. One caveat observed is that the TS server might sometimes return only open-file results for references unless the project is properly configured; however, when the project has a tsconfig and all files are indexed, Find References should cover the whole codebase
. Overall, the LSP interface for JS/TS is consistent with other languages.
Python: Pyright (open-source core of Microsoft’s Pylance) is a fast, static type analysis server for Python that also speaks LSP. It provides cross-module definitions and references by analyzing import statements and type hints. For example, a textDocument/definition on an imported class or function will jump to the file where it’s defined (even if that file is in another package)
. textDocument/references will find all usages of a symbol across the workspace (given Python’s dynamic nature, it can miss some, but Pyright tries by leveraging static types where possible). Notably, Pyright (and most Python LSPs) do not implement textDocument/implementation, since Python has no concept of interface vs implementation and method overrides are duck-typed. As confirmed in an issue, Pyright’s LSP capabilities show no implementationProvider (the client log says “server does not support textDocument/implementation”)
. They also don’t advertise a typeDefinition provider
 – a request like “go to type” isn’t commonly needed in Python. However, Pyright does support document symbols and workspace symbols. In fact, in an editor, you can navigate the outline of a Python file or search for symbols globally (Pyright lists classes, functions, etc., by name in the project)
. Another Python LSP is pylsp (Python LSP Server, formerly Palantir’s pyls), which similarly supports definitions/references but is generally slower/less feature-rich than Pyright. For a headless harness focusing on semantic relationships, Pyright is a strong choice due to its focus on static analysis for type inference. The harness would simply run the pyright-langserver (or use the pylance engine via VS Code’s implementation if available) and then issue references/definition queries.
Known Limitations and Gaps in LSP Implementations
While the LSP feature set is broad and standardized, not every server implements every request or handles every scenario perfectly. Here are some limitations to consider when building a cross-file semantic graph:
Dynamic Language Challenges: In languages like Ruby, Python, and JavaScript, the dynamic typing and metaprogramming can defeat static analysis. The LSP servers might not find references that are not explicit. For instance, Ruby’s Solargraph might miss a method call that’s invoked via reflection or a Rails magic method. Similarly, Python LSPs won’t catch uses of a function if it’s called via getattr or through dependency injection. This means the “reference” graph may be incomplete for highly dynamic patterns. The harness should be aware that absence of references doesn’t always mean none exist – it might be a limitation of static analysis.
Partial or Missing Feature Implementations: A few language servers do not implement certain LSP requests at all:
The early version of Shopify’s Ruby LSP lacked go-to-definition and find-references entirely
.
Pyright (Python) does not provide implementations or type definitions
.
Some older or simpler servers might omit workspace/symbol to avoid indexing overhead.
In such cases, the harness may need to skip those queries or implement a fallback. For example, if a server lacks a workspaceSymbol method, the harness could resort to scanning all document symbols from all files as a crude workaround.
Indexing and Project Configuration: Many language servers require the project to be set up correctly to index all files:
Clangd (C++) needs a compile_commands.json or other build system integration to index all source files. If some files are not indexed, cross-file references may be incomplete
. The harness might need to ensure the project is loaded (e.g., by providing the compile_commands or opening a folder).
JDT LS (Java) and OmniSharp (C#) rely on project files (pom.xml, .csproj, etc.). If those aren’t present or resolved, the server may not see all classpath files. The harness should open the root workspace folder and let the server auto-configure project classpaths.
TypeScript LS benefits from a tsconfig.json to know which files belong to the project. Without it, the server might only consider open files. In one anecdote, users found references queries only returned results from open buffers until the TS project was properly configured
.
Godot’s GDScript LSP will only index scripts in the context of an open Godot project (the engine must load the project scene files). The harness must launch the server pointed at the project’s directory as shown above
.
Performance on Large Codebases: Building a complete cross-file graph means issuing many references/definition queries. Some servers can become slow if you naively ask for “all references of all symbols”. For example, asking for references of every identifier in a huge C++ project would be heavy even though clangd is optimized (it might throttle or limit results
). A pragmatic harness might instead use workspace/symbol to list global symbols and then selectively call references/definitions for ones of interest. It’s important to note if the server has any internal limits (clangd by default returns a maximum number of references, but as of Clangd 14 “all references from the current file are always returned, even if there are enough to exceed our usual limit”
). Knowing such quirks can help the harness adjust (e.g., splitting queries or configuring the server for higher limits).
Call Hierarchy vs References: The question specifically mentions method calls across files. While textDocument/references will find all call sites of a function (which achieves the goal), some modern LSPs support a dedicated Call Hierarchy (LSP methods textDocument/prepareCallHierarchy, callHierarchy/incomingCalls, etc.). Not all servers implement this yet, but several do (e.g. rust-analyzer, Pyright, clangd). If available, this can directly provide a tree of callers/callees across files. However, since call hierarchy is a newer addition, a generic harness might stick to the more universally supported references requests. The harness designer should be aware of these extended capabilities but not rely on them universally.
Language-Specific Quirks: A few idiosyncrasies may affect cross-file graph accuracy:
C++: The distinction between declarations and definitions – clangd’s textDocument/definition might take you to a header declaration first; one may need to use textDocument/implementation (which clangd maps to finding derived classes or actual function definitions) or its custom queries. Clangd and ccls have some custom LSP extensions (like call hierarchy or inheritance hierarchy) beyond the base spec
. The harness could ignore extensions for portability or leverage them conditionally.
Java: JDT LS will not return references in library code unless source or source stubs are attached (it can find references to library classes in user code, but obviously not inside the JDK itself unless configured).
Go: gopls will only return references for the active build tags/OS platform by default (it won’t mix Linux/Windows files in one session)
. For a complete picture, one might need to query per build context if relevant.
Bash: The Bash LS notes that improving scope-aware analysis is an ongoing effort
, meaning current references might occasionally include false positives or miss shadowed variables. But for the most part, its cross-file support (via sourcing of other scripts) is rudimentary – the harness might have to manually handle source/. commands as needed.
In summary, no fundamental blockers emerged that would prevent building an LSP-based cross-file relationship extractor. All listed languages have at least one viable LSP server that can be run headlessly and answer standardized queries about symbols. The main hurdles are ensuring each server is properly configured for the project and handling the cases where a server doesn’t support a query.
Normalizing Responses to a Unified Representation
Since LSP uses a common protocol, the format of responses for things like definitions or references is mostly uniform across servers. However, the harness will need to perform some normalization for consistency:
Location Structures: Most servers return references and definitions as a list of Location objects (with a file URI and range). Some servers (especially newer spec versions) may return LocationLink objects, which include additional context (like origin selection range). A normalization step can convert all results to a simple form (e.g., file path + position). This is a straightforward mapping since the data is similar.
Document Symbols: The textDocument/documentSymbol request can return either a flat list of SymbolInformation or a hierarchical DocumentSymbol tree. The harness should handle both. It may be easiest to flatten hierarchical symbols into a list of SymbolInformation for graph purposes. Each symbol has a kind (function, class, variable, etc.) which is standardized numeric codes across LSP. Normalization might involve mapping those codes to a common enum and attaching the container relations (e.g., a method belongs to a class).
Workspace Symbols: This request returns SymbolInformation with a location. Different servers might include slightly different scoping information (e.g., the containerName field might be formatted differently). The harness can ignore cosmetic differences and use the symbol name, kind, and location. A possible normalization is to index symbols by their fully-qualified name (if the server provides it) or by a combination of name + container (for languages with namespaces).
Inconsistent Capabilities: As noted, not every server supports every request. The harness can detect supported methods via the server’s capabilities in the LSP handshake (the initialize response includes flags like referencesProvider, implementationProvider, etc.). For example, Pyright’s capabilities show referencesProvider: true but no implementationProvider
. The harness should read these and only issue requests that are supported, to avoid errors. In cases where a feature is crucial (say we want class implementations in C# but OmniSharp’s LSP didn’t initially support textDocument/implementation in older versions), one might need a per-language workaround. Fortunately, OmniSharp does support it now
. If a server truly cannot provide a needed relationship, the options are either to supplement with a custom analysis or accept a gap in the graph.
Intermediate Representation: Converging data from different languages into one graph format will require abstracting language-specific details. For example, you might represent a graph node as a “Symbol” with properties like name, kind (function, class, etc.), file, and perhaps language. Edges could be of types like “references”, “defines”, “calls”, “inherits” depending on what you derive:
A definition query can link a symbol usage to the symbol definition (creating a “defines” or “is definition of” edge).
A references query essentially gives all “uses” edges pointing to a symbol’s definition.
An implementation query in OOP languages yields “inherits/implements” relationships between types.
The harness may unify these under a general graph schema (e.g., a directed edge from symbol A to B with a label “calls” if A’s body calls B, which you determine by finding references of B inside A’s scope, etc.). Constructing such a graph is beyond LSP’s direct output but can be built by correlating the LSP data.
Edge-case Differences: Watch out for minor differences like URI formats. Some servers return file URIs (file:///path/to/file), others may return relative paths or platform-specific casing. Normalizing to a consistent path format is advisable (e.g., strip the file:// prefix and handle Windows drive letters properly). Also, ensure that the lazy-loading nature of the harness doesn’t miss data – e.g., some servers might only index opened files until a “workspace symbol” or an explicit “workspace/reference” operation triggers a full index (though most do index upfront or on first query).
Overall, the effort to normalize is manageable. All servers output data in well-defined JSON shapes that map to a common concept of symbols and locations. The harness will act as an aggregator: it issues the same queries to each server and then unifies the results into one composite model. This is far easier than writing separate parsers or analyzers for each language from scratch. It leverages each language’s own compiler intelligence via LSP, with the trade-off that we must adapt to each server’s support level and output nuances.
Conclusion
In conclusion, building a headless, multi-language LSP harness for cross-file semantic relationships is not only feasible but aligns with the core purpose of LSP – enabling language-agnostic tooling. With a careful choice of stable language servers for C++ (clangd), Rust (rust-analyzer), Ruby (Solargraph), GDScript (Godot’s LSP), Bash (bash-language-server), C# (OmniSharp), Go (gopls), Java (JDT LS), TypeScript/JavaScript (TypeScript LS), and Python (Pyright), one can achieve broad coverage of semantic graph extraction. The harness can issue uniform requests (definitions, references, implementations, symbols) to each server
 and combine the answers. While there are some inconsistencies and gaps – especially in dynamically typed languages and a few unimplemented LSP methods – these are well-documented and often improving over time. By handling these variations (using fallbacks or acknowledging limitations), the harness can construct an accurate cross-file dependency and reference graph for multi-language codebases. The result would be a powerful, editor-independent code analysis tool that requires only thin per-language adapters and lets each language’s LSP do the heavy lifting of understanding code semantics. Sources:
LLVM clangd – feature support (cross-references, type definitions)
rust-analyzer official documentation – supports go-to-def and find-references
Bash Language Server README – lists “Find references” and “Workspace symbols” features
OmniSharp (C#) LSP capabilities as seen in client config – implements definitions, references, typeDefinition, etc.
Pyright (Python) issue – server has references provider but no implementation provider
Ruby LSP discussion – initially lacked go-to-def and find-references (Solargraph used as alternative)
Godot 4.2 release notes – GDScript LSP now implements reference lookup
Eclipse JDT LS info – supports standard LSP features like references, etc.
Go gopls docs – supports references, implementations for interfaces, and workspace symbol search
.
Citations
Getting C# Autocomplete on Windows Emacs | Zacalot.XYZ

https://zacalot.xyz/post/tech/csharp-lsp-on-windows/

GitHub - bash-lsp/bash-language-server: A language server for Bash

https://github.com/bash-lsp/bash-language-server
Extra Clang Tools 14.0.0 Release Notes — Extra Clang Tools 14.0.0 documentation

https://releases.llvm.org/14.0.0/tools/clang/tools/extra/docs/ReleaseNotes.html
Extra Clang Tools 14.0.0 Release Notes — Extra Clang Tools 14.0.0 documentation

https://releases.llvm.org/14.0.0/tools/clang/tools/extra/docs/ReleaseNotes.html

⚙ D44882 [clangd] Implementation of workspace/symbol request

https://reviews.llvm.org/D44882

Introduction - rust-analyzer

https://rust-analyzer.github.io/manual.html

Solargraph vs Ruby LSP: which one to choose? | A. Christian Toscano

https://achris.me/posts/solargraph-vs-ruby-lsp/

Solargraph vs Ruby LSP: which one to choose? | A. Christian Toscano

https://achris.me/posts/solargraph-vs-ruby-lsp/

shopify/ruby-lsp as an alternate language server · Issue #4834 · zed ...

https://github.com/zed-industries/zed/issues/4834

Godot 4.2 arrives in style! – Godot Engine

https://godotengine.org/article/godot-4-2-arrives-in-style/

GitHub - bash-lsp/bash-language-server: A language server for Bash

https://github.com/bash-lsp/bash-language-server

GitHub - bash-lsp/bash-language-server: A language server for Bash

https://github.com/bash-lsp/bash-language-server
Getting C# Autocomplete on Windows Emacs | Zacalot.XYZ

https://zacalot.xyz/post/tech/csharp-lsp-on-windows/
Getting C# Autocomplete on Windows Emacs | Zacalot.XYZ

https://zacalot.xyz/post/tech/csharp-lsp-on-windows/
Getting C# Autocomplete on Windows Emacs | Zacalot.XYZ

https://zacalot.xyz/post/tech/csharp-lsp-on-windows/
Getting C# Autocomplete on Windows Emacs | Zacalot.XYZ

https://zacalot.xyz/post/tech/csharp-lsp-on-windows/

Gopls: Navigation features - The Go Programming Language

https://go.dev/gopls/features/navigation

Gopls: Navigation features - The Go Programming Language

https://go.dev/gopls/features/navigation

Gopls: Navigation features - The Go Programming Language

https://go.dev/gopls/features/navigation

Gopls: Navigation features - The Go Programming Language

https://go.dev/gopls/features/navigation

Eclipse JDT: how to get data model for Java content assist

https://stackoverflow.com/questions/34320848/eclipse-jdt-how-to-get-data-model-for-java-content-assist

lsp-goto-implementation not working · Issue #60 · emacs-lsp/lsp-pyright · GitHub

https://github.com/emacs-lsp/lsp-pyright/issues/60

lsp-goto-implementation not working · Issue #60 · emacs-lsp/lsp-pyright · GitHub

https://github.com/emacs-lsp/lsp-pyright/issues/60

lsp-goto-implementation not working · Issue #60 · emacs-lsp/lsp-pyright · GitHub

https://github.com/emacs-lsp/lsp-pyright/issues/60

Connecting Gdscript language server without editor (headless Godot) - Archive - Godot Forum

https://forum.godotengine.org/t/connecting-gdscript-language-server-without-editor-headless-godot/6269

Implement lsp-references support in the GDScript language server · Issue #3687 · godotengine/godot-proposals · GitHub

https://github.com/godotengine/godot-proposals/issues/3687

GitHub - bash-lsp/bash-language-server: A language server for Bash

https://github.com/bash-lsp/bash-language-server

Gopls: Navigation features - The Go Programming Language

https://go.dev/gopls/features/navigation

Gopls: Navigation features - The Go Programming Language

https://go.dev/gopls/features/navigation

Gopls: Navigation features - The Go Programming Language

https://go.dev/gopls/features/navigation

GitHub - typescript-language-server/typescript-language-server: TypeScript & JavaScript Language Server

https://github.com/typescript-language-server/typescript-language-server

'Telescope lsp_references' only finds references in open buffers ...

https://www.reddit.com/r/neovim/comments/1c6wy98/telescope_lsp_references_only_finds_references_in/

Can `pyright` LSP navigate to different module? - Stack Overflow

https://stackoverflow.com/questions/70371671/can-pyright-lsp-navigate-to-different-module

Why does clangd not find all references? - c++ - Stack Overflow

https://stackoverflow.com/questions/79433540/why-does-clangd-not-find-all-references

Connecting Gdscript language server without editor (headless Godot) - Archive - Godot Forum

https://forum.godotengine.org/t/connecting-gdscript-language-server-without-editor-headless-godot/6269
Extra Clang Tools 14.0.0 Release Notes — Extra Clang Tools 14.0.0 documentation

https://releases.llvm.org/14.0.0/tools/clang/tools/extra/docs/ReleaseNotes.html

Landing support for LSP protocol extensions? - LLVM Discourse

https://discourse.llvm.org/t/landing-support-for-lsp-protocol-extensions/50805

Gopls: Navigation features - The Go Programming Language

https://go.dev/gopls/features/navigation

GitHub - bash-lsp/bash-language-server: A language server for Bash

https://github.com/bash-lsp/bash-language-server

Gopls: Navigation features - The Go Programming Language

https://go.dev/gopls/features/navigation
All Sources
zacalot

github
releases.llvm

reviews.llvm

rust-analyzer.github

achris

godotengine

go

stackoverflow

forum.godotengine

reddit
