# Fix Tasks: Simple Mode — Local LLM Smart Content

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Catch real OpenAI SDK transport exceptions in `LocalOllamaAdapter`
- **Severity**: HIGH
- **File(s)**:
  - `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/llm_adapter_local.py`
  - `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_llm_adapter_local.py`
- **Issue**: Real closed-port and timeout failures from the OpenAI SDK arrive as `openai.APIConnectionError` and `openai.APITimeoutError`, so the current builtin exception handlers never run. Users get the generic fallback message instead of the actionable Ollama guidance promised by AC04 and AC12.
- **Fix**: Import/catch the real SDK exception types in the adapter and update the tests to raise the same exception classes the production client raises.
- **Patch hint**:
  ```diff
  -from openai import AsyncOpenAI
  +from openai import APIConnectionError, APITimeoutError, AsyncOpenAI
   
  -        except TimeoutError as e:
  +        except APITimeoutError as e:
               raise LLMAdapterError(...timeout guidance...) from e
   
  -        except (ConnectionError, ConnectionRefusedError, OSError) as e:
  +        except APIConnectionError as e:
               raise LLMAdapterError(...install/start guidance...) from e
  ```
  ```diff
  -create=AsyncMock(side_effect=ConnectionError("Connection refused"))
  +create=AsyncMock(side_effect=APIConnectionError(...))
   
  -create=AsyncMock(side_effect=TimeoutError())
  +create=AsyncMock(side_effect=APITimeoutError(...))
  ```

### FT-002: Make the new adapter test file pass Ruff
- **Severity**: HIGH
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_llm_adapter_local.py`
- **Issue**: The scoped Ruff run fails on this file with `F401`, `SIM117`, and `UP041`, so the phase is not merge-ready under the repo’s enforced lint gate.
- **Fix**: Remove the unused import, collapse the nested `with` blocks, and use builtin `TimeoutError` in the test file so `uv run ruff check ...` passes cleanly.
- **Patch hint**:
  ```diff
  -from fs2.config.service import ConfigurationService
   from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter
  ```
  ```diff
  -with patch.object(...):
  -    with pytest.raises(LLMAdapterError) as exc_info:
  -        await adapter.generate("test")
  +with patch.object(...), pytest.raises(LLMAdapterError) as exc_info:
  +    await adapter.generate("test")
  ```
  ```diff
  -create=AsyncMock(side_effect=asyncio.TimeoutError())
  +create=AsyncMock(side_effect=TimeoutError())
  ```

## Medium / Low Fixes

### FT-003: Register the new local-LLM guide for MCP docs discovery
- **Severity**: MEDIUM
- **File(s)**:
  - `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/registry.yaml`
  - `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/configuration-guide.md`
  - `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/local-llm.md`
- **Issue**: `flowspace-docs_list()` does not show `local-llm`, `flowspace-docs_get("local-llm")` returns null, and the `configuration-guide` metadata still describes Azure/OpenAI only. AC11 is therefore incomplete for MCP docs discovery.
- **Fix**: Add a `local-llm` entry to the docs registry, refresh `configuration-guide` registry metadata/tags for local/Ollama support, and rebuild docs discovery artifacts using the repo’s normal docs workflow.
- **Patch hint**:
  ```diff
    - id: configuration-guide
  -   summary: "Comprehensive reference for all fs2 configuration. Covers file locations, secrets, LLM/embedding providers (Azure/OpenAI), ..."
  +   summary: "Comprehensive reference for all fs2 configuration. Covers local/Ollama, Azure/OpenAI, embeddings, chunking, and troubleshooting."
  +   tags:
  +     - local
  +     - ollama
  +
  + - id: local-llm
  +   title: "Local LLM Smart Content"
  +   summary: "Set up Ollama-powered local smart-content generation without API keys."
  +   category: how-to
  +   tags:
  +     - llm
  +     - local
  +     - ollama
  +     - smart-content
  +     - setup
  +   path: local-llm.md
  ```

### FT-004: Remove the duplicate provider-selection branch from `scan.py`
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/scan.py`
- **Issue**: The phase adds a fourth provider branch to the CLI-side smart-content factory instead of reusing `LLMService.create()`, preserving the RF-02 drift hazard identified in the plan.
- **Fix**: Delegate adapter/provider selection to `LLMService.create(config)` and keep only SmartContentService composition / CLI error reporting in `scan.py`.
- **Patch hint**:
  ```diff
  -        if llm_config.provider == "azure":
  -            llm_adapter = AzureOpenAIAdapter(config)
  -        elif llm_config.provider == "openai":
  -            ...
  -        elif llm_config.provider == "local":
  -            ...
  -        elif llm_config.provider == "fake":
  -            ...
  -        else:
  -            return None, f"unsupported provider: {llm_config.provider}"
  -
  -        llm_service = LLMService(config, llm_adapter)
  +        try:
  +            llm_service = LLMService.create(config)
  +        except ValueError:
  +            return None, f"unsupported provider: {llm_config.provider}"
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Scoped Ruff command passes cleanly
- [ ] Local adapter tests cover real SDK exception classes
- [ ] Docs registry exposes `local-llm` via MCP docs discovery
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
