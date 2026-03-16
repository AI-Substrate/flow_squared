"""fs2 init command implementation.

Creates both local .fs2/config.yaml and global ~/.config/fs2/ configuration
in a single command. Shows current directory, warns if no .git folder,
and creates .gitignore to protect secrets.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from fs2.config.paths import get_user_config_dir

console = Console()

DEFAULT_CONFIG = """\
# fs2 configuration file
# Full docs: https://github.com/AI-Substrate/flow_squared

scan:
  scan_paths:
    - "."
  ignore_patterns:
    - "node_modules"
    - ".venv"
    - "*.pyc"
    - "__pycache__"
  respect_gitignore: true
  max_file_size_kb: 500
  follow_symlinks: false

# ─── LLM (for smart content) ───────────────────────────────────────
# Smart content generates AI summaries for every code node.
# Local mode uses Ollama — no API key needed, runs on your machine.
#
# Setup: Install Ollama from https://ollama.com then run:
#   ollama pull qwen2.5-coder:7b
#
# Uncomment below to enable smart content:
# llm:
#   provider: local
#   base_url: http://localhost:11434
#   model: qwen2.5-coder:7b

# ─── Alternative LLM providers ─────────────────────────────────────
# Azure AI Foundry (API key):
# llm:
#   provider: azure
#   api_key: ${AZURE_OPENAI_API_KEY}
#   base_url: https://YOUR-RESOURCE.openai.azure.com/
#   azure_deployment_name: gpt-4o
#   azure_api_version: "2024-12-01-preview"
#   model: gpt-4o
#
# Azure AI Foundry (az login — no API key needed):
# llm:
#   provider: azure
#   base_url: https://YOUR-RESOURCE.openai.azure.com/
#   azure_deployment_name: gpt-4o
#   azure_api_version: "2024-12-01-preview"
#   model: gpt-4o
#   # Requires: pip install fs2[azure-ad] && az login
#
# OpenAI:
# llm:
#   provider: openai
#   api_key: ${OPENAI_API_KEY}
#   model: gpt-4o

# ─── Smart Content (AI summaries for code nodes) ──────────────────
# Controls AI summary generation. Requires LLM provider above.
smart_content:
  # max_workers: 30          # Parallel workers (default: 50, use 1 for local Ollama)
  max_input_tokens: 50000
  enabled_categories: ["file"]            # Files only (~85% faster)
  # enabled_categories: ["file", "type"]  # Files + classes (~67% faster)
  # To process all categories, remove enabled_categories or set to null

# ─── Embedding (for semantic search) ──────────────────────────────
# Local embeddings (default — no API key needed):
# Requires: pip install fs2[local-embeddings]
embedding:
  mode: local
  dimensions: 384
  # local:
  #   model: BAAI/bge-small-en-v1.5
  #   device: auto
  #   max_seq_length: 512
#
# Azure AI Foundry (API key):
# embedding:
#   mode: azure
#   dimensions: 1024
#   azure:
#     endpoint: https://YOUR-RESOURCE.openai.azure.com/
#     api_key: ${AZURE_EMBEDDING_API_KEY}
#     deployment_name: text-embedding-3-small
#     api_version: "2024-02-01"
#
# Azure AI Foundry (az login — no API key needed):
# embedding:
#   mode: azure
#   dimensions: 1024
#   azure:
#     endpoint: https://YOUR-RESOURCE.openai.azure.com/
#     deployment_name: text-embedding-3-small
#     api_version: "2024-02-01"
#   # Requires: pip install fs2[azure-ad] && az login
#
# OpenAI-compatible:
# embedding:
#   mode: openai_compatible
#   dimensions: 1024
#   openai_compatible:
#     endpoint: https://api.openai.com/v1
#     api_key: ${OPENAI_API_KEY}
#     model: text-embedding-3-small

# ─── Cross-File Relationships (LSP-powered) ──────────────────────
# Resolves call/reference relationships between code nodes using Serena (LSP).
# Enabled by default when serena-mcp-server is available on PATH.
# Install: uv tool install "serena-agent @ git+https://github.com/oraios/serena.git"
# NOTE: Add .serena/ to your project .gitignore (created at project root by Serena)
#
# cross_file_rels:
#   enabled: true
#   parallel_instances: 20
#   serena_base_port: 8330
#   timeout_per_node: 5.0
#   languages:
#     - python
"""

# .gitignore for .fs2 directory - ignores everything except config.yaml
FS2_GITIGNORE = """\
# Ignore everything in .fs2/ except config.yaml
*
!.gitignore
!config.yaml
"""


def _detect_ollama() -> tuple[bool, str | None]:
    """Check if Ollama is running and has a code model pulled.

    Returns:
        (ollama_running, model_name) — model_name is None if no code model found.
    """
    import json
    import urllib.request

    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            for preferred in [
                "qwen2.5-coder:7b",
                "qwen2.5-coder:3b",
                "codellama:7b",
                "llama3:8b",
            ]:
                if preferred in models:
                    return True, preferred
            if models:
                return True, models[0]
            return True, None
    except Exception:
        return False, None


def init(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing local config"),
    ] = False,
) -> None:
    """Initialize fs2 configuration for this project.

    Creates both local (.fs2/) and global (~/.config/fs2/) configuration.
    Global config is created only if it doesn't exist.

    \b
    Example:
        $ fs2 init
        Current directory: /path/to/project
        ✓ Created local config at .fs2/config.yaml
        ✓ Created global config at ~/.config/fs2/
    """
    cwd = Path.cwd()
    local_config_dir = cwd / ".fs2"
    local_config_file = local_config_dir / "config.yaml"
    local_gitignore = local_config_dir / ".gitignore"

    global_config_dir = get_user_config_dir()
    global_config_file = global_config_dir / "config.yaml"

    # Show current directory
    console.print(f"[bold]Current directory:[/bold] {cwd}")
    console.print()

    # Check for .git (file or directory - supports worktrees)
    git_path = cwd / ".git"
    if not git_path.exists():
        console.print(
            "[bold red]⚠ WARNING:[/bold red] No .git folder found!\n"
            "  Are you sure this is a project root?\n"
        )

    # Track what we did
    actions = []

    # === Handle global config ===
    if global_config_file.exists():
        actions.append(f"Skipped global config (already exists at {global_config_dir})")
    else:
        # Create global config directory and file
        global_config_dir.mkdir(parents=True, exist_ok=True)
        global_config_file.write_text(DEFAULT_CONFIG)
        actions.append(f"Created global config at {global_config_dir}")

    # === Handle local config ===
    if local_config_file.exists() and not force:
        console.print(
            "[yellow]⚠[/yellow] Local config already exists at .fs2/config.yaml\n"
            "  Use [bold]--force[/bold] to overwrite."
        )
        # Still report global action
        for action in actions:
            if "global" in action.lower():
                console.print(f"[dim]{action}[/dim]")
        return

    # Create local config directory if needed
    local_config_dir.mkdir(exist_ok=True)

    # Detect Ollama and auto-configure LLM if available
    ollama_running, ollama_model = _detect_ollama()
    config_text = DEFAULT_CONFIG

    if ollama_running and ollama_model:
        # Auto-enable local LLM by uncommenting the config block
        config_text = config_text.replace(
            "# Uncomment below to enable smart content:\n"
            "# llm:\n"
            "#   provider: local\n"
            "#   base_url: http://localhost:11434\n"
            "#   model: qwen2.5-coder:7b",
            f"llm:\n"
            f"  provider: local\n"
            f"  base_url: http://localhost:11434\n"
            f"  model: {ollama_model}",
        )

    # Write local config
    local_config_file.write_text(config_text)
    actions.append("Created local config at .fs2/config.yaml")

    # Create .gitignore in .fs2/
    local_gitignore.write_text(FS2_GITIGNORE)
    actions.append("Created .fs2/.gitignore")

    # Report all actions
    console.print("[bold]Actions:[/bold]")
    for action in actions:
        if action.startswith("Skipped"):
            console.print(f"  [dim]• {action}[/dim]")
        else:
            console.print(f"  [green]✓[/green] {action}")

    console.print()
    console.print(
        "  Edit .fs2/config.yaml to customize scan settings.\n"
        "  Then run [bold]fs2 scan[/bold] to scan your codebase."
    )

    # Smart content status messaging
    console.print()
    if ollama_running and ollama_model:
        console.print(
            f"  [green]✓[/green] Smart content enabled "
            f"(Ollama + {ollama_model} detected)"
        )
    elif ollama_running:
        console.print(
            "  [yellow]ℹ[/yellow] Ollama detected but no code model found.\n"
            "    Run: [bold]ollama pull qwen2.5-coder:7b[/bold]\n"
            "    Then: [bold]fs2 init --force[/bold]"
        )
    else:
        console.print(
            "  [dim]💡 For AI code summaries, install Ollama:[/dim]\n"
            "    [dim]https://ollama.com → ollama pull qwen2.5-coder:7b "
            "→ fs2 init --force[/dim]"
        )
