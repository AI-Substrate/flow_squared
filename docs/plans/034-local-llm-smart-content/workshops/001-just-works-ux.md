# Workshop: Making Local LLM Smart Content "Just Work"

> **Plan**: 034-local-llm-smart-content
> **Topic**: UX for zero-friction local LLM setup
> **Date**: 2026-03-15

---

## Problem Statement

The current UX for enabling local LLM smart content requires users to:
1. Read config comments to discover Ollama exists
2. Manually install Ollama (external download)
3. Manually pull a model (`ollama pull qwen2.5-coder:7b`)
4. Manually uncomment 4 YAML lines in `.fs2/config.yaml`
5. Know they also need a `smart_content:` section (not in default config)
6. Run `fs2 scan` and hope it works

**Goal**: Make it so a user with Ollama installed gets smart content with ZERO config editing.

---

## Current UX Journey (Pain Points)

```
fs2 init                    → Config generated, LLM section COMMENTED OUT
fs2 scan                    → Scan works, but "SMART CONTENT (skipped)"
                               User may not even notice it was skipped
User reads config.yaml      → Sees Ollama instructions, uncomments
fs2 scan                    → "not configured (no smart_content section)"
                               ❌ FRUSTRATING — they just configured LLM!
User adds smart_content:    → Manual YAML editing, error-prone
fs2 scan                    → Finally works
```

**Total friction**: 4 manual steps, 2 potential failure points, ~15 minutes.

---

## Proposed UX: Progressive Auto-Detection

### Design Principle: Detect → Suggest → Enable

```
fs2 init
  → Detects Ollama running on localhost:11434
  → Auto-enables LLM config (uncommented)  
  → Auto-adds smart_content section
  → Prints: "✓ Detected Ollama — smart content enabled with qwen2.5-coder:7b"

fs2 scan
  → Smart content just works
```

If Ollama is NOT detected:
```
fs2 init
  → LLM config stays commented out
  → Prints: "ℹ Smart content: Install Ollama for AI code summaries"
  →         "  https://ollama.com → ollama pull qwen2.5-coder:7b"
```

### Implementation: 5 Changes

#### Change 1: `fs2 init` auto-detects Ollama

In `init.py`, after writing the config, probe Ollama:

```python
def _detect_ollama() -> tuple[bool, str | None]:
    """Check if Ollama is running and has a code model."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as resp:
            import json
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            # Prefer code models
            for preferred in ["qwen2.5-coder:7b", "qwen2.5-coder:3b", "codellama:7b"]:
                if preferred in models:
                    return True, preferred
            # Any model is better than none
            if models:
                return True, models[0]
            return True, None  # Ollama running but no models
    except Exception:
        return False, None
```

Then in the init command:
```python
ollama_running, ollama_model = _detect_ollama()
if ollama_running and ollama_model:
    config_text = config_text.replace("# llm:", "llm:")
    config_text = config_text.replace("#   provider: local", "  provider: local")
    # ... uncomment the section
    console.print(f"✓ Detected Ollama — smart content enabled with {ollama_model}")
elif ollama_running:
    console.print("ℹ Ollama detected but no models. Run: ollama pull qwen2.5-coder:7b")
else:
    console.print("ℹ For AI code summaries, install Ollama: https://ollama.com")
```

**Effort**: ~30 lines. **Impact**: Eliminates 3 of 4 manual steps.

#### Change 2: Add `smart_content:` to DEFAULT_CONFIG

The LLM config is useless without a `smart_content:` section. Add it:

```yaml
# ─── Smart Content ─────────────────────────────────────────────────
# Controls AI summary generation. Requires LLM provider above.
smart_content:
  max_workers: 50
  max_input_tokens: 50000
```

**Effort**: 4 lines. **Impact**: Eliminates the "no smart_content section" error.

#### Change 3: `fs2 scan` graceful Ollama detection

When LLM is configured as local but Ollama isn't running, show a one-line helpful message instead of per-node errors:

```
⚠ Smart content: Ollama not running (start with: ollama serve)
```

Currently it tries every node and shows N errors. Better to fail-fast with one clear message.

**Effort**: ~10 lines in `_create_smart_content_service` or SmartContentStage.

#### Change 4: `fs2 init` output mentions smart content

Current output:
```
Edit .fs2/config.yaml to customize scan settings.
Then run fs2 scan to scan your codebase.
```

Better:
```
Edit .fs2/config.yaml to customize scan settings.
Then run fs2 scan to scan your codebase.

💡 For AI code summaries: install Ollama (https://ollama.com)
   Then: ollama pull qwen2.5-coder:7b && fs2 init --force
```

Or if Ollama was auto-detected:
```
✓ Smart content enabled (Ollama + qwen2.5-coder:7b detected)
✓ Run fs2 scan to generate AI summaries for your codebase
```

**Effort**: ~5 lines.

#### Change 5: `agents-start-here` mentions Ollama

The agents-start-here currently says:
```
[ ] Providers configured (optional — enables smart content + semantic search)
```

Better when Ollama is detected:
```
[✓] LLM provider: Ollama (local, qwen2.5-coder:7b)
```

Or when not:
```
[ ] LLM provider: not configured
    → For AI summaries: install Ollama (https://ollama.com)
```

**Effort**: ~15 lines.

---

## Decision Matrix

| Change | Effort | UX Impact | Recommendation |
|--------|--------|-----------|----------------|
| 1. Auto-detect Ollama in init | ~30 lines | **High** — eliminates manual config | ✅ Do now |
| 2. Add smart_content to DEFAULT_CONFIG | 4 lines | **High** — prevents cryptic error | ✅ Do now |
| 3. Fail-fast on Ollama down | ~10 lines | **Medium** — cleaner error | ✅ Do now |
| 4. Init output mentions smart content | ~5 lines | **Medium** — discoverability | ✅ Do now |
| 5. agents-start-here Ollama status | ~15 lines | **Low** — secondary path | ⏳ Later |

**Total effort for changes 1-4**: ~50 lines of code.

---

## "Just Works" UX After Changes

### Scenario A: User has Ollama + model

```
$ fs2 init
✓ Created .fs2/config.yaml
✓ Detected Ollama — smart content enabled with qwen2.5-coder:7b
  Run fs2 scan to generate AI summaries for your codebase.

$ fs2 scan
  ...
  ✓ Smart content: enabled
  → Smart content: 150/523 (28.7%) processed, 373 remaining
  ...
  ✓ Enriched: 523 nodes
```

**Steps**: 2 commands. Zero config editing.

### Scenario B: User has Ollama but no model

```
$ fs2 init
✓ Created .fs2/config.yaml
ℹ Ollama detected but no code model found.
  Run: ollama pull qwen2.5-coder:7b
  Then: fs2 init --force

$ ollama pull qwen2.5-coder:7b
$ fs2 init --force
✓ Detected Ollama — smart content enabled with qwen2.5-coder:7b
```

**Steps**: 4 commands. Clear guidance at each step.

### Scenario C: User has no Ollama

```
$ fs2 init
✓ Created .fs2/config.yaml
ℹ For AI code summaries, install Ollama: https://ollama.com
  Then: ollama pull qwen2.5-coder:7b && fs2 init --force

$ fs2 scan
  ...
  SMART CONTENT (skipped) — not configured
  ...
```

**Steps**: 1 command. Works fine without smart content. Clear breadcrumb for later.

---

## Testing Plan

| Test | Validates |
|------|-----------|
| `test_init_detects_ollama_with_model` | Auto-uncomments LLM config when Ollama running with model |
| `test_init_detects_ollama_no_model` | Prints model pull instruction |
| `test_init_no_ollama` | LLM stays commented, prints install URL |
| `test_init_default_config_has_smart_content_section` | smart_content: section present |
| `test_scan_ollama_down_fails_fast` | One error message, not per-node errors |

---

## Summary

The core insight is: **fs2 should detect what's available and auto-configure, not require users to read YAML comments and manually edit config files**.

With ~50 lines of code across 4 changes, we go from "read config, install Ollama, uncomment YAML, add smart_content section, run scan" to "install Ollama, pull model, fs2 init, fs2 scan".
