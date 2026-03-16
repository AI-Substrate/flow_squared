# Local LLM Smart Content

Generate AI-powered code summaries using a local LLM via [Ollama](https://ollama.com) — no API keys, no network access, no cost.

## Quick Start

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh   # Linux
# Or download from https://ollama.com/download   # Mac/Windows

# 2. Pull the recommended code model
ollama pull qwen2.5-coder:7b

# 3. Initialize fs2 (or update existing config)
fs2 init

# 4. Scan your codebase
fs2 scan
```

Smart content summaries will appear in `fs2 tree`, `fs2 search`, and MCP tool responses.

## Configuration

Add to `.fs2/config.yaml`:

```yaml
llm:
  provider: local
  base_url: http://localhost:11434
  model: qwen2.5-coder:7b
```

### Configuration Options

| Field | Default | Description |
|-------|---------|-------------|
| `provider` | — | Set to `local` for Ollama |
| `base_url` | — | Ollama endpoint (usually `http://localhost:11434`) |
| `model` | — | Model name (must be pulled in Ollama first) |
| `temperature` | `0.1` | Generation temperature (lower = more consistent) |
| `max_tokens` | `1024` | Maximum tokens per summary |
| `timeout` | `30` | Request timeout in seconds (up to 300 for local) |

## Model Selection

| Model | Size | Quality | Speed | Best For |
|-------|------|---------|-------|----------|
| `qwen2.5-coder:7b` | 4.7 GB | ★★★★★ | ★★★ | **Recommended** — best code understanding |
| `qwen2.5-coder:3b` | 2.0 GB | ★★★★ | ★★★★ | Resource-constrained machines |
| `codellama:7b` | 3.8 GB | ★★★ | ★★★ | Alternative if Qwen unavailable |

Pull any model with: `ollama pull <model-name>`

## Speeding Up First Scan

For large codebases, limit smart content to file-level summaries only:

```yaml
smart_content:
  max_workers: 50
  max_input_tokens: 50000
  enabled_categories: ["file"]  # ~85% faster — files only
```

All nodes (classes, methods, etc.) still exist in the graph with full source code and embeddings — only the AI summary is skipped for non-file nodes.

## How It Works

1. **First scan**: fs2 sends each code node (class, function, file) to the local LLM for summarization. This takes ~2-3 hours for large codebases (~5000 nodes).
2. **Incremental scans**: Only changed nodes are re-summarized. Unchanged nodes keep their previous summaries via content hash matching. Re-scans typically take seconds to minutes.
3. **Cross-platform**: Ollama auto-detects your GPU — Apple Metal, NVIDIA CUDA, or CPU fallback.

## Troubleshooting

### Ollama not running

```
LLMAdapterError: Cannot connect to Ollama
```

**Fix**: Start Ollama with `ollama serve` or launch the Ollama app.

### Model not found

```
LLMAdapterError: Model 'qwen2.5-coder:7b' not found
```

**Fix**: Pull the model with `ollama pull qwen2.5-coder:7b`

### Timeout errors

```
LLMAdapterError: Ollama request timed out after 30s
```

**Fix**: Increase timeout in config:
```yaml
llm:
  provider: local
  base_url: http://localhost:11434
  model: qwen2.5-coder:7b
  timeout: 120  # up to 300 for CPU-only machines
```

### Check setup with doctor

```bash
fs2 doctor llm
```

This checks Ollama connectivity, model availability, and performs a test generation.

## Switching from Cloud to Local

Replace your existing LLM config:

```yaml
# Before (cloud):
# llm:
#   provider: azure
#   api_key: ${AZURE_OPENAI_API_KEY}
#   ...

# After (local):
llm:
  provider: local
  base_url: http://localhost:11434
  model: qwen2.5-coder:7b
```

Run `fs2 scan --force` to regenerate summaries with the new model.

## Platform Support

| Platform | GPU | Performance |
|----------|-----|-------------|
| macOS (Apple Silicon) | Metal (automatic) | ~35 files/min |
| Linux (NVIDIA) | CUDA (automatic) | ~60+ files/min |
| Linux/Mac/Windows | CPU fallback | ~10-15 files/min |

Ollama handles GPU detection automatically — no configuration needed.
