#!/usr/bin/env python3
"""Scratch script for testing Azure AD (az login) authentication.

This is NOT run in CI. It verifies the Azure AD credential path works
with a real az login session.

Usage:
    .venv/bin/python tests/scratch/test_azure_ad_auth.py

Prerequisites:
    - az login (have a valid session)
    - pip install azure-identity (or: pip install fs2[azure-ad])
    - Cognitive Services OpenAI User RBAC role on the resource
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# Use the same endpoints from user config, but NO api_key
LLM_ENDPOINT = "https://jordoopenai2.openai.azure.com/"
LLM_DEPLOYMENT = "gpt-5-mini"
LLM_API_VERSION = "2024-12-01-preview"

EMBEDDING_ENDPOINT = "https://oaijodoaustralia.openai.azure.com/"
EMBEDDING_DEPLOYMENT = "text-embedding-3-small-no-rate"
EMBEDDING_API_VERSION = "2024-02-01"


async def test_llm_azure_ad():
    """Test LLM adapter with Azure AD auth (no api_key)."""
    from fs2.config.objects import LLMConfig
    from fs2.core.services.llm_service import LLMService

    class AzureADConfigService:
        def require(self, config_type):
            if config_type == LLMConfig:
                return LLMConfig(
                    provider="azure",
                    api_key=None,  # <-- No key! Uses az login
                    base_url=LLM_ENDPOINT,
                    azure_deployment_name=LLM_DEPLOYMENT,
                    azure_api_version=LLM_API_VERSION,
                    model=LLM_DEPLOYMENT,
                    temperature=1.0,
                    max_tokens=1000,
                    timeout=120,
                    max_retries=0,
                )
            raise ValueError(f"Unknown config type: {config_type}")

    print("=== LLM Azure AD Auth Test ===")
    print(f"Endpoint: {LLM_ENDPOINT}")
    print(f"Deployment: {LLM_DEPLOYMENT}")
    print("Auth: Azure AD (az login)")
    print()

    config = AzureADConfigService()
    service = LLMService.create(config)

    print("Sending test prompt...")
    response = await service.generate("Say hello in exactly 5 words.", max_tokens=50)

    print(f"Content: {response.content}")
    print(f"Tokens: {response.tokens_used}")
    print(f"Model: {response.model}")
    print(f"Provider: {response.provider}")
    print(f"Filtered: {response.was_filtered}")
    print("LLM: SUCCESS!")
    print()


async def test_embedding_azure_ad():
    """Test Embedding adapter with Azure AD auth (no api_key)."""
    from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
    from fs2.core.adapters.embedding_adapter import create_embedding_adapter_from_config

    class AzureADEmbeddingConfigService:
        def require(self, config_type):
            if config_type == EmbeddingConfig:
                return EmbeddingConfig(
                    mode="azure",
                    dimensions=1024,
                    azure=AzureEmbeddingConfig(
                        endpoint=EMBEDDING_ENDPOINT,
                        api_key=None,  # <-- No key! Uses az login
                        deployment_name=EMBEDDING_DEPLOYMENT,
                        api_version=EMBEDDING_API_VERSION,
                    ),
                )
            raise ValueError(f"Unknown config type: {config_type}")

    print("=== Embedding Azure AD Auth Test ===")
    print(f"Endpoint: {EMBEDDING_ENDPOINT}")
    print(f"Deployment: {EMBEDDING_DEPLOYMENT}")
    print("Auth: Azure AD (az login)")
    print()

    config = AzureADEmbeddingConfigService()
    adapter = create_embedding_adapter_from_config(config)

    print("Embedding test text...")
    result = await adapter.embed_text("Hello, world!")

    print(f"Dimensions: {len(result)}")
    print(f"First 5 values: {result[:5]}")
    print(f"Type: {type(result[0])}")
    print("Embedding: SUCCESS!")
    print()


async def main():
    try:
        await test_llm_azure_ad()
    except Exception as e:
        print(f"LLM FAILED: {type(e).__name__}: {e}")

    try:
        await test_embedding_azure_ad()
    except Exception as e:
        print(f"Embedding FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
