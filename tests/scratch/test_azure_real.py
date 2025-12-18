#!/usr/bin/env python3
"""Scratch script for real Azure OpenAI API testing.

This is NOT run in CI. It's for manual development testing with real API.

Usage:
    # Set environment variable
    export AZURE_OPENAI_API_KEY="your-key-here"

    # Run the script
    uv run python tests/scratch/test_azure_real.py

Prerequisites:
    - Azure OpenAI resource with deployment
    - API key in AZURE_OPENAI_API_KEY environment variable
    - Update AZURE_ENDPOINT and AZURE_DEPLOYMENT below
"""

import asyncio
import os
import sys

# Add src to path for development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


# Configuration - UPDATE THESE FOR YOUR AZURE DEPLOYMENT
AZURE_ENDPOINT = "https://YOUR-RESOURCE.openai.azure.com/"
AZURE_DEPLOYMENT = "gpt-4"
AZURE_API_VERSION = "2024-12-01-preview"


async def main():
    """Run a test generation against real Azure OpenAI."""
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.services.llm_service import LLMService

    # Check for API key
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if not api_key:
        print("ERROR: AZURE_OPENAI_API_KEY environment variable not set")
        print("Set it with: export AZURE_OPENAI_API_KEY='your-key-here'")
        sys.exit(1)

    print(f"Using endpoint: {AZURE_ENDPOINT}")
    print(f"Using deployment: {AZURE_DEPLOYMENT}")
    print()

    # Create a simple mock config service that returns our LLMConfig
    class SimpleConfigService:
        def require(self, config_type):
            if config_type == LLMConfig:
                return LLMConfig(
                    provider="azure",
                    api_key=api_key,
                    base_url=AZURE_ENDPOINT,
                    azure_deployment_name=AZURE_DEPLOYMENT,
                    azure_api_version=AZURE_API_VERSION,
                    model="gpt-4",
                    temperature=0.1,
                    max_tokens=100,
                    timeout=120,
                    max_retries=3,
                )
            raise ValueError(f"Unknown config type: {config_type}")

    config = SimpleConfigService()
    service = LLMService.create(config)

    print("Sending test prompt...")
    print()

    try:
        response = await service.generate(
            "Say hello in exactly 5 words.",
            max_tokens=50,
        )

        print("=== Response ===")
        print(f"Content: {response.content}")
        print(f"Tokens used: {response.tokens_used}")
        print(f"Model: {response.model}")
        print(f"Provider: {response.provider}")
        print(f"Finish reason: {response.finish_reason}")
        print(f"Was filtered: {response.was_filtered}")
        print()
        print("SUCCESS!")

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
