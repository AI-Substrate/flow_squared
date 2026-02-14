# Workshop: Agent Onboarding Experience

**Type**: CLI Flow
**Plan**: 026-agents-start-here
**Spec**: (pending -- this workshop informs the spec)
**Created**: 2026-02-14
**Status**: Draft

**Related Documents**:
- [Research Dossier](../research-dossier.md)
- [src/fs2/docs/agents.md](../../../../src/fs2/docs/agents.md) -- existing agent tool guide
- [src/fs2/docs/mcp-server-guide.md](../../../../src/fs2/docs/mcp-server-guide.md) -- MCP client setup

---

## Purpose

Design the complete agent experience from "fs2 is installed, now what?" to "agent is productively exploring code." The goal is that a human can install fs2 and simply tell their agent "explore this codebase with fs2" and the agent can self-serve from there.

## Key Questions Addressed

- Q1: What does the agent see when it first runs `fs2 agents-start-here`?
- Q2: How does the agent browse documentation via CLI (before MCP is connected)?
- Q3: What is the complete journey from zero to productive agent?
- Q4: How does the output adapt based on what's already set up?
- Q5: What two new commands are needed and how do they interact?

---

## The Bootstrap Problem

Today's agent journey has a chicken-and-egg problem:

```
Agent wants to use fs2
  -> Needs to know how to set up fs2
    -> Best docs are in the MCP docs system (docs_list/docs_get)
      -> But MCP isn't connected yet
        -> Agent can't read the docs that would tell it how to connect
```

**Solution**: Two new CLI commands that work without any setup:

| Command | Purpose |
|---------|---------|
| `fs2 agents-start-here` | One-shot orientation: what is fs2, what's the current state, what to do next |
| `fs2 docs [doc_id]` | Browse bundled documentation via CLI (mirrors MCP docs_list/docs_get) |

Both are **unguarded** (no `require_init`). Both work before `fs2 init`. Together they give agents full self-service capability from the terminal.

---

## The Agent Journey

```
Phase 1: ORIENT          Phase 2: INIT & CONFIG      Phase 3: SCAN & MCP
(what is this?)          (get it configured)          (index + connect)

fs2 agents-start-here    fs2 init                     fs2 scan
     |                   fs2 docs configuration-guide  fs2 docs mcp-server-guide
     v                   edit .fs2/config.yaml         claude mcp add fs2 ...
fs2 docs                 fs2 doctor                    -> now using MCP tools
fs2 docs agents          fs2 doctor llm (optional)       tree(), search(), docs_get()
```

**Key insight**: MCP is the destination, not an optional extra. The CLI commands
(`fs2 tree`, `fs2 search`, `fs2 docs`) are the bootstrap path -- the agent uses
them to get fs2 configured and scanned. Once that's done, the agent sets up MCP
and switches to native tool access. CLI is the stepping stone, MCP is the goal.

**Key insight**: Configuration is not a hand-wave step. An agent needs to:
1. Read `fs2 docs configuration-guide` to understand providers (Azure, OpenAI, etc.)
2. Read the `DEFAULT_CONFIG` template that `fs2 init` creates (it has worked examples)
3. Edit `.fs2/config.yaml` with the right provider settings
4. Validate with `fs2 doctor` and optionally `fs2 doctor llm`

The `agents-start-here` output must surface config docs prominently at the right moment.

### Phase 1: Orient (CLI only, zero config)

The agent runs shell commands. No MCP connection yet. No config files.

**Step 1**: Agent runs `fs2 agents-start-here`

```
$ fs2 agents-start-here

fs2 - Code Intelligence for AI Agents
======================================

fs2 indexes your codebase and makes it searchable via CLI or MCP server.
Use it to explore code structure, find implementations, and search by meaning.

Project Status
--------------
  [green] fs2 installed (v0.8.0)
  [red]   Project not initialized       -> Run: fs2 init
  [red]   Codebase not scanned          -> Run: fs2 scan
  [dim]   LLM not configured            -> Optional: edit .fs2/config.yaml
  [dim]   Embeddings not configured      -> Optional: edit .fs2/config.yaml

Next Step
---------
  Run `fs2 init` to create project configuration.

Browse Documentation
--------------------
  fs2 docs                          List all available guides
  fs2 docs agents                   How to use fs2 tools (read this first)
  fs2 docs cli                      CLI command reference
  fs2 docs configuration-guide      Full configuration guide
  fs2 docs mcp-server-guide         Set up MCP for your AI client

All Commands
------------
  fs2 init          Create project configuration
  fs2 scan          Index the codebase
  fs2 tree          Explore code structure
  fs2 search        Search by text, regex, or meaning
  fs2 get-node      Get full source of a code element
  fs2 doctor        Check configuration health
  fs2 mcp           Start MCP server for native AI integration
```

**Step 2**: Agent browses docs to understand setup

```
$ fs2 docs

Available Documentation
=======================

Getting Started:
  agents                  AI Agent Guidance (read this first)

How-To Guides:
  scanning                Scanning Guide
  mcp-server-guide        MCP Server Guide
  multi-graphs            Multi-Graph Configuration Guide
  wormhole-mcp-guide      Wormhole MCP Guide

Reference:
  cli                     CLI Reference
  configuration-guide     Complete Configuration Guide
  configuration           Configuration Quick Reference

Usage: fs2 docs <id>     Read a specific document
       fs2 docs --json   Output as JSON (for programmatic use)
```

**Step 3**: Agent reads the agents guide

```
$ fs2 docs agents

AI Agent Guidance
=================

[Full markdown content of agents.md rendered to terminal]

...183 lines of tool usage patterns, workflows, and best practices...
```

### Phase 2: Initialize and Configure

The agent now knows what to do. It follows the checklist from `agents-start-here`.

**Step 4**: Initialize the project

```
$ fs2 init
Current directory: /Users/dev/my-project

Actions:
  [green] Created local config at .fs2/config.yaml
  [green] Created .fs2/.gitignore
  [dim]   Skipped global config (already exists at ~/.config/fs2)

  Edit .fs2/config.yaml to customize scan settings.
  Then run fs2 scan to scan your codebase.
```

**Step 5**: Agent reads the configuration guide to understand provider options

This is the critical step the agent should NOT skip. The config template has
commented examples, but the agent needs to understand what providers are available
and how to choose the right one for this project.

```
$ fs2 docs configuration-guide

Complete Configuration Guide
============================

## Configuration Files

fs2 uses a layered configuration system:

  Priority (highest to lowest):
  1. Environment variables (FS2_*)
  2. Project config (.fs2/config.yaml)
  3. User config (~/.config/fs2/config.yaml)
  4. Defaults

## LLM Configuration (for smart content)

### Azure AI Foundry (API Key)
  llm:
    provider: azure
    api_key: ${AZURE_OPENAI_API_KEY}
    base_url: https://YOUR-RESOURCE.openai.azure.com/
    azure_deployment_name: gpt-4o
    azure_api_version: "2024-12-01-preview"
    model: gpt-4o

### Azure AI Foundry (az login - no API key)
  llm:
    provider: azure
    base_url: https://YOUR-RESOURCE.openai.azure.com/
    azure_deployment_name: gpt-4o
    azure_api_version: "2024-12-01-preview"
    model: gpt-4o
  # Requires: pip install fs2[azure-ad] && az login

### OpenAI
  llm:
    provider: openai
    api_key: ${OPENAI_API_KEY}
    model: gpt-4o

## Embedding Configuration (for semantic search)

### Azure AI Foundry (API Key)
  embedding:
    mode: azure
    dimensions: 1024
    azure:
      endpoint: https://YOUR-RESOURCE.openai.azure.com/
      api_key: ${AZURE_EMBEDDING_API_KEY}
      deployment_name: text-embedding-3-small
      api_version: "2024-02-01"

...

## Secrets Management

  Use environment variables or .fs2/secrets.env:
    AZURE_OPENAI_API_KEY=sk-...
  Never commit API keys to .fs2/config.yaml!

...
```

**Step 6**: Agent edits the config based on what it learned

The agent now understands the provider options. It reads the template config
and edits it with the appropriate provider settings:

```
$ cat .fs2/config.yaml
# fs2 configuration file
# Full docs: https://github.com/AI-Substrate/flow_squared

scan:
  scan_paths:
    - "."
  respect_gitignore: true
  max_file_size_kb: 500
  follow_symlinks: false

# --- LLM (for smart content) ---
# [commented examples for Azure, OpenAI, etc.]
#
# --- Embedding (for semantic search) ---
# [commented examples for Azure, OpenAI, etc.]
```

The agent can uncomment and fill in the appropriate provider block. The
template's comments serve as inline documentation -- the agent already
understands the options from reading the configuration guide.

**Step 7**: Agent validates the configuration

```
$ fs2 doctor

fs2 Configuration Health Check
  Current Directory: /Users/dev/my-project

Config Files:
    1. [green] .fs2/config.yaml
    2. [green] ~/.config/fs2/config.yaml

Provider Status:
  [green] LLM: azure (configured)
  [green] Embeddings: azure (configured)

Secrets & Placeholders:
  [green] ${AZURE_OPENAI_API_KEY} -> resolved
```

**Optional Step 7a**: Test live connectivity

```
$ fs2 doctor llm

LLM Provider Test
  [green] LLM (azure): Connected
    Response: HEALTH_CHECK_OK

Embedding Provider Test
  [green] Embeddings (azure): Connected
    Dimensions: 1024
```

### Phase 3: Scan & MCP (the destination)

The agent scans the codebase and then sets up MCP -- CLI was just the bootstrap.

**Step 8**: Scan the codebase

```
$ fs2 scan
Scanning /Users/dev/my-project...
  Parsed 142 files (Python: 98, TypeScript: 44)
  Built graph: 1,247 nodes
  Saved to .fs2/graph.pickle

Done in 3.2s
```

**Step 8a**: Agent re-checks status (optional but natural)

```
$ fs2 agents-start-here

Project Status
--------------
  [green] fs2 installed (v0.8.0)
  [green] Project initialized (.fs2/config.yaml)
  [green] Codebase scanned (1,247 nodes)
  [green] LLM configured (azure)
  [green] Embeddings configured (azure)

Ready to Go!
-------------
  Next Step: Set up MCP for native tool access
    Read: fs2 docs mcp-server-guide
```

**Note**: When scanned, the "Ready to Go" section always points to MCP setup as
the next step. When LLM/embeddings are configured, it includes `--mode semantic`
in search examples. When they are NOT configured, it shows only text/regex search.

**Step 9**: Set up MCP for native tool access

The agent reads the MCP guide and configures the client:

```
$ fs2 docs mcp-server-guide

MCP Server Guide
================

...

## Client Setup

### Claude Code CLI

  claude mcp add fs2 --scope user -- fs2 mcp

### Claude Desktop

  Edit claude_desktop_config.json:
  {
    "mcpServers": {
      "fs2": {
        "command": "fs2",
        "args": ["mcp"]
      }
    }
  }

...
```

Once MCP is connected, the agent switches from CLI to native tools:
- `tree(pattern=".")` instead of `fs2 tree .`
- `search(pattern="auth", mode="semantic")` instead of `fs2 search "auth" --mode semantic`
- `docs_list()` / `docs_get(id)` instead of `fs2 docs` / `fs2 docs <id>`

**This is the goal state.** The agent now has direct tool access without shell commands.
CLI was the stepping stone to get here.

---

## Command Design: `fs2 agents-start-here`

### Registration

```python
# In main.py -- unguarded (no require_init)
app.command(name="agents-start-here")(agents_start_here)
```

### Signature

```python
def agents_start_here() -> None:
    """Get started with fs2 - orientation for AI agents and new users.

    Shows what fs2 is, checks project status, and provides next steps.
    Works before init, scan, or any configuration.

    \b
    Example:
        $ fs2 agents-start-here
        [Shows status and next steps]

    \b
    Exit codes:
        0 - Always succeeds
    """
```

### State Detection Logic

The command checks project state and adapts its output:

```
State 1: Nothing set up
  - config missing, graph missing
  - Next Step: "Run fs2 init"
  - Browse Documentation highlights: agents, configuration-guide

State 2: Initialized, no providers configured, not scanned
  - config exists, no llm/embedding sections, no graph
  - Next Step: "Configure providers, then run fs2 scan"
  - Browse Documentation highlights: configuration-guide, configuration
  - Shows: "Read `fs2 docs configuration-guide` for provider setup"

State 3: Initialized, providers configured, not scanned
  - config exists, llm/embedding present, no graph
  - Next Step: "Run fs2 scan"
  - Suggests: "Run fs2 doctor to validate config first"

State 4: Scanned, no providers (basic mode)
  - config + graph exist, no LLM/embedding
  - "Ready to go!" with text/regex search
  - Next Step: "Set up MCP for native tool access"
  - Shows: "Read `fs2 docs mcp-server-guide`"
  - Also suggests: "For semantic search, read `fs2 docs configuration-guide`"

State 5: Fully configured (scanned + providers)
  - config + graph + providers all set
  - "Ready to go!" with ALL commands including semantic search
  - Next Step: "Set up MCP for native tool access"
  - Shows: "Read `fs2 docs mcp-server-guide`"
  - This is the final CLI step -- after MCP, agent switches to native tools
```

The key adaptation: the "Next Step" and "Browse Documentation" sections change
based on what's missing. When config exists but providers are not set up, the
command actively pushes the agent toward the configuration guide rather than
just saying "edit config.yaml."

**State-dependent "Browse Documentation" section**:

| State | Top Recommendations |
|-------|-------------------|
| Nothing set up | `fs2 docs agents` (what is this?), `fs2 docs configuration-guide` (how to configure) |
| Initialized, no providers | `fs2 docs configuration-guide` (set up providers), `fs2 docs configuration` (quick ref) |
| Initialized, has providers | `fs2 docs scanning` (scan options), `fs2 docs cli` (command reference) |
| Scanned, no providers | `fs2 docs mcp-server-guide` (connect MCP -- the goal), `fs2 docs configuration-guide` (add providers) |
| Fully configured | `fs2 docs mcp-server-guide` (connect MCP -- the goal), `fs2 docs agents` (usage patterns) |

### Output Sections

| Section | Always Shown | Content |
|---------|-------------|---------|
| Header | Yes | "fs2 - Code Intelligence for AI Agents" + one-liner |
| Project Status | Yes | Checklist with green/red/dim indicators |
| Next Step | Yes | Single most important next action (state-dependent) |
| Configure Providers | When init done but no providers | Points to `fs2 docs configuration-guide` |
| Browse Documentation | Yes | `fs2 docs` commands with state-dependent top picks |
| All Commands | Yes | Command summary table |
| MCP Setup Hint | When scanned | "Set up MCP for native tool access" (the goal) |

### Key Design Decisions

**Why plain text, not Rich panels?**
Agents parse terminal output as text. Rich panels with box-drawing characters add noise. Use simple markers (`[green]`, `[red]`, `[dim]`) that degrade gracefully with `NO_COLOR=1`. The output should be easily parseable by any LLM.

**Why show ALL commands even before init?**
Agents benefit from knowing the full vocabulary upfront. Commands that require init are naturally guarded -- the agent will get a helpful error if it tries them too early.

**Why a separate command instead of enhancing `--help`?**
`--help` is Typer-generated and shows option syntax. `agents-start-here` shows project state, next steps, and documentation pointers -- a fundamentally different purpose. It's an orientation guide, not a usage reference.

**Why not `fs2 start` or `fs2 setup`?**
The name `agents-start-here` is explicitly discoverable. An agent searching for "where to start" or "getting started" will find it. The hyphenated name also appears prominently in `--help` output. It signals "this is for you, the agent."

---

## Command Design: `fs2 docs [doc_id]`

### Registration

```python
# In main.py -- unguarded (no require_init)
app.command(name="docs")(docs)
```

### Signature

```python
def docs(
    doc_id: Annotated[
        str | None,
        typer.Argument(help="Document ID to read (omit to list all)"),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category"),
    ] = None,
    tags: Annotated[
        str | None,
        typer.Option("--tags", "-t", help="Filter by tags (comma-separated)"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Browse fs2 documentation.

    Without arguments, lists all available documents.
    With a document ID, displays the full document content.

    \b
    Examples:
        $ fs2 docs                      List all documents
        $ fs2 docs agents               Read the agents guide
        $ fs2 docs --category how-to    List how-to guides only
        $ fs2 docs --tags config        List config-related docs
        $ fs2 docs agents --json        Output as JSON

    \b
    Exit codes:
        0 - Success
        1 - Document not found
    """
```

### Behavior: List Mode (no doc_id)

```
$ fs2 docs

Available Documentation
=======================

Getting Started:
  agents                  AI Agent Guidance (read this first)

How-To Guides:
  mcp-server-guide        MCP Server Guide
  scanning                Scanning Guide
  multi-graphs            Multi-Graph Configuration Guide
  wormhole-mcp-guide      Wormhole MCP Guide

Reference:
  cli                     CLI Reference
  configuration-guide     Complete Configuration Guide
  configuration           Configuration Quick Reference

Usage: fs2 docs <id>     Read a specific document
```

**Ordering**: "Getting Started" category first (tagged `getting-started`), then how-to guides, then reference docs. Within each group, alphabetical.

**With category filter**:
```
$ fs2 docs --category reference

Reference:
  cli                     CLI Reference
  configuration-guide     Complete Configuration Guide
  configuration           Configuration Quick Reference
```

**With tag filter**:
```
$ fs2 docs --tags config

  configuration-guide     Complete Configuration Guide
  configuration           Configuration Quick Reference
  multi-graphs            Multi-Graph Configuration Guide
```

### Behavior: Read Mode (with doc_id)

```
$ fs2 docs agents

AI Agent Guidance
=================

[Full markdown content rendered to terminal via Rich Markdown]
```

The document content is rendered using `rich.markdown.Markdown` for readable terminal output. Code blocks are syntax-highlighted. Headers use Rich styling.

**Document not found**:
```
$ fs2 docs nonexistent

Error: Document 'nonexistent' not found.

Available documents:
  agents, cli, configuration, configuration-guide,
  mcp-server-guide, multi-graphs, scanning, wormhole-mcp-guide

Run `fs2 docs` to see all documents with descriptions.
```
Exit code: 1

### Behavior: JSON Mode

**List as JSON**:
```
$ fs2 docs --json

{
  "docs": [
    {
      "id": "agents",
      "title": "AI Agent Guidance",
      "summary": "Best practices for AI agents...",
      "category": "how-to",
      "tags": ["agents", "mcp", "getting-started"]
    },
    ...
  ],
  "count": 8
}
```

**Read as JSON**:
```
$ fs2 docs agents --json

{
  "id": "agents",
  "title": "AI Agent Guidance",
  "content": "# AI Agent Guidance\n\n...",
  "metadata": {
    "category": "how-to",
    "tags": ["agents", "mcp", "getting-started"],
    "summary": "Best practices for AI agents..."
  }
}
```

**Why JSON mode?**
Agents that parse structured output (like Claude Code) may prefer JSON over rendered markdown. This also exactly mirrors the MCP `docs_list`/`docs_get` response format, creating consistency between CLI and MCP access.

### Implementation Notes

- Uses `DocsService` from `fs2.core.dependencies.get_docs_service()` -- same as MCP tools
- No config or graph needed (DocsService loads from bundled package resources)
- Rendered markdown uses `Console().print(Markdown(content))` for human-readable output
- JSON mode uses `print(json.dumps(...))` to stdout (standard pattern)
- Error messages go to `Console(stderr=True)`

---

## Complete Worked Example: Agent Session

Here is what a real agent session looks like. The human has installed fs2 and
tells the agent: "Help me set up fs2 for this project."

The agent can self-serve the entire setup by reading docs via CLI.

### Scenario A: Full Setup (Human wants LLM + Embeddings)

```
HUMAN: Help me set up fs2 for this project.

AGENT: I'll set up fs2 for this project. Let me start by checking the current state.

$ fs2 agents-start-here

fs2 - Code Intelligence for AI Agents
======================================

fs2 indexes your codebase and makes it searchable via CLI or MCP server.
Use it to explore code structure, find implementations, and search by meaning.

Project Status
--------------
  + fs2 installed (v0.8.0)
  - Project not initialized       -> Run: fs2 init
  - Codebase not scanned          -> Run: fs2 scan
    LLM not configured            -> Optional: for smart content
    Embeddings not configured      -> Optional: for semantic search

Next Step
---------
  Run `fs2 init` to create project configuration.

Browse Documentation
--------------------
  fs2 docs                          List all available guides
  fs2 docs agents                   How to use fs2 tools (read this first)
  fs2 docs configuration-guide      Full configuration guide
  fs2 docs mcp-server-guide         Set up MCP for your AI client

All Commands
------------
  fs2 init          Create project configuration
  fs2 scan          Index the codebase
  fs2 tree          Explore code structure
  fs2 search        Search by text, regex, or meaning
  fs2 get-node      Get full source of a code element
  fs2 doctor        Check configuration health
  fs2 mcp           Start MCP server for native AI integration


AGENT: fs2 is not initialized yet. Let me initialize the project first.

$ fs2 init
Current directory: /Users/dev/my-project

Actions:
  + Created local config at .fs2/config.yaml
  + Created .fs2/.gitignore
  + Created global config at ~/.config/fs2

  Edit .fs2/config.yaml to customize scan settings.
  Then run fs2 scan to scan your codebase.


AGENT: Configuration created. Before scanning, let me check what provider
options are available so we can configure LLM and embedding support. Let me
read the configuration guide.

$ fs2 docs configuration-guide

Complete Configuration Guide
============================

## Configuration Files

  fs2 uses a layered configuration system:
    1. Environment variables (FS2_*)
    2. Project config (.fs2/config.yaml)
    3. User config (~/.config/fs2/config.yaml)
    4. Defaults

## LLM Configuration (for smart content)

  Choose ONE provider:

  Azure AI Foundry (API Key):
    llm:
      provider: azure
      api_key: ${AZURE_OPENAI_API_KEY}
      base_url: https://YOUR-RESOURCE.openai.azure.com/
      azure_deployment_name: gpt-4o
      azure_api_version: "2024-12-01-preview"
      model: gpt-4o

  Azure AI Foundry (az login -- no API key):
    llm:
      provider: azure
      base_url: https://YOUR-RESOURCE.openai.azure.com/
      azure_deployment_name: gpt-4o
      azure_api_version: "2024-12-01-preview"
      model: gpt-4o
    # Requires: pip install fs2[azure-ad] && az login

  OpenAI:
    llm:
      provider: openai
      api_key: ${OPENAI_API_KEY}
      model: gpt-4o

## Embedding Configuration (for semantic search)
  ...

## Secrets Management
  Use environment variables or .fs2/secrets.env
  ...


AGENT: I see three LLM provider options: Azure with API key, Azure with
az login (no key needed), and OpenAI. Do you use Azure or OpenAI? And do
you have API keys set up, or prefer the az login approach?

HUMAN: We use Azure with API keys. We have the keys as environment variables
already.

AGENT: Great, Azure with API keys. Let me configure both LLM and embeddings.
I'll edit .fs2/config.yaml to uncomment the Azure provider blocks.

[Agent edits .fs2/config.yaml, uncommenting the Azure API key sections
for both LLM and embedding, replacing YOUR-RESOURCE with the actual
Azure resource name]

Let me validate the configuration:

$ fs2 doctor

fs2 Configuration Health Check
  Current Directory: /Users/dev/my-project

Config Files:
    1. + .fs2/config.yaml
    2. + ~/.config/fs2/config.yaml

Provider Status:
  + LLM: azure (configured)
  + Embeddings: azure (configured)

Secrets & Placeholders:
  + ${AZURE_OPENAI_API_KEY} -> resolved


AGENT: Configuration looks good. Let me test the live connections:

$ fs2 doctor llm

LLM Provider Test
  + LLM (azure): Connected
    Response: HEALTH_CHECK_OK

Embedding Provider Test
  + Embeddings (azure): Connected
    Dimensions: 1024


AGENT: Everything is connected. Now let me scan your codebase:

$ fs2 scan
Scanning /Users/dev/my-project...
  Parsed 142 files (Python: 98, TypeScript: 44)
  Built graph: 1,247 nodes
  Saved to .fs2/graph.pickle

Done in 3.2s


AGENT: Codebase scanned -- 1,247 indexed code nodes with LLM smart content
and semantic search enabled. Now let me set up the MCP server so I have
native tool access instead of running shell commands.

$ fs2 docs mcp-server-guide
[...reads MCP setup instructions...]

$ claude mcp add fs2 --scope user -- fs2 mcp

AGENT: MCP is configured. After restarting, I'll have native fs2 tools:
tree(), search(), get_node(), docs_list(), docs_get(). No more shell
commands needed -- I can explore your codebase directly.

Want me to start with an overview of the project structure?
```

### Scenario B: Basic Setup (No providers, just scanning)

```
HUMAN: Set up fs2 for this project. I don't need AI features,
just code search.

AGENT: I'll set up fs2 with basic code search. Let me check the state.

$ fs2 agents-start-here
[...shows State 1: nothing set up...]


AGENT: Let me initialize and scan.

$ fs2 init
[...creates config...]

$ fs2 scan
Scanning /Users/dev/my-project...
  Parsed 142 files (Python: 98, TypeScript: 44)
  Built graph: 1,247 nodes
  Saved to .fs2/graph.pickle

Done in 3.2s


AGENT: Codebase scanned with text and regex search. Now let me set up
MCP for native tool access.

$ fs2 docs mcp-server-guide
[...reads MCP setup instructions...]

$ claude mcp add fs2 --scope user -- fs2 mcp

AGENT: MCP is configured. After restarting, I'll have native fs2 tools
for exploring your codebase directly.

Note: If you later want semantic search (search by meaning) or smart
content summaries, I can help configure an LLM provider -- just ask.
```

**Key observation**: Both scenarios end with MCP connected -- that's the goal state.
Scenario B takes ~5 commands (`agents-start-here`, `init`, `scan`, read mcp guide, add mcp).
Scenario A takes ~10 commands but the agent self-serves the entire provider config
by reading docs via CLI. In both cases, CLI is the bootstrap; MCP is the destination.

---

## Implementation Summary

### New Files

| File | Purpose |
|------|---------|
| `src/fs2/cli/agents_start_here.py` | `agents-start-here` command implementation |
| `src/fs2/cli/docs_cmd.py` | `docs` command implementation |
| `tests/unit/cli/test_agents_start_here_cli.py` | Tests for agents-start-here |
| `tests/unit/cli/test_docs_cmd_cli.py` | Tests for docs command |

### Modified Files

| File | Change |
|------|--------|
| `src/fs2/cli/main.py` | Register two new unguarded commands |
| `src/fs2/docs/registry.yaml` | (Optional) Add `agents-start-here` entry if new bundled doc created |

### Dependencies

| Component | Used By | Purpose |
|-----------|---------|---------|
| `DocsService` | Both commands | Load/serve bundled documentation |
| `Rich Console` | Both commands | Terminal formatting |
| `typer` | Both commands | CLI framework |
| `ConfigurationService` | `agents-start-here` | Detect project state |
| `Path checks` | `agents-start-here` | Check for graph file |

### What Is NOT Needed

- No graph access (both commands work pre-scan)
- No `require_init` guard (both work pre-init)
- No embedding adapter
- No LLM service

---

## Open Questions

### Q1: Should `agents-start-here` also exist as a bundled doc?

**LEANING YES**: Create `src/fs2/docs/agents-start-here.md` with the onboarding
journey as a document. This way, once MCP is connected, agents can also
`docs_get(id="agents-start-here")` to revisit the setup guide. The CLI command
would show the state-adaptive version; the doc would be the static reference.

### Q2: Should `fs2 docs` use Rich Markdown rendering or raw text?

**LEANING RICH**: Use `rich.markdown.Markdown` for human-readable rendering with
syntax highlighting. Agents that prefer raw text can use `--json` mode. This
matches the dual-audience design (humans read rendered, agents parse JSON).

### Q3: Should state detection read the YAML config or just check file existence?

**LEANING YAML READ**: Checking just file existence misses State 2 vs State 3
(initialized-without-providers vs initialized-with-providers). Reading the YAML
to detect `llm:` and `embedding:` sections enables better guidance. This aligns
with `doctor`'s approach.

### Q4: Should `fs2 docs` group documents or just list alphabetically?

**LEANING GROUPED**: Group by category (Getting Started, How-To, Reference) with
"Getting Started" first. This mirrors how the registry.yaml categories work and
helps agents find the most relevant doc first.

### Q5: What about the `agents.md` bundled doc -- does it need updates?

**LEANING MINOR UPDATE**: The existing `agents.md` covers tool usage well (183 lines)
but assumes a working setup. Add a brief "Getting Started" section at the top that
points to `fs2 agents-start-here` and `fs2 docs configuration-guide` for setup.
This ensures agents who find the doc via MCP also know about the CLI bootstrap path.

---

## Quick Reference

```bash
# Phase 1: Orient (CLI bootstrap)
fs2 agents-start-here              # What is fs2? What's set up? What's next?
fs2 docs                           # List all available documentation
fs2 docs agents                    # Read the agent usage guide

# Phase 2: Init & Config (CLI bootstrap)
fs2 init                           # Create .fs2/config.yaml
fs2 docs configuration-guide       # Read provider setup options
# [edit .fs2/config.yaml]
fs2 doctor                         # Validate configuration
fs2 doctor llm                     # Test live provider connections

# Phase 3: Scan & MCP (the destination)
fs2 scan                           # Index the codebase
fs2 docs mcp-server-guide          # Read MCP setup instructions
# [configure MCP client]           # e.g. claude mcp add fs2 ...
# -> Now using native MCP tools:   tree(), search(), docs_get()
```

---

**Workshop Complete**: 2026-02-14
**Status**: Draft
**Next**: Create spec with `/plan-1b-specify` or proceed to architecture with `/plan-3-architect`
