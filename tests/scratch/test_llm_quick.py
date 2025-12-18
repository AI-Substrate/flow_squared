#!/usr/bin/env python3
"""Quick test script for LLM service.

Usage:
    uv run python tests/scratch/test_llm_quick.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


async def main():
    from fs2.config import FS2ConfigurationService
    from fs2.core.services.llm_service import LLMService

    print("Loading configuration...")
    config = FS2ConfigurationService()

    print("Creating LLM service...")
    service = LLMService.create(config)
    print(f"Provider: {service._adapter.provider_name}")

    print("\nSending test prompt...")
    prompt = "Reply with just the word 'hello' and nothing else."

    try:
        response = await service.generate(prompt, max_tokens=500)

        print("\n" + "=" * 40)
        print("SUCCESS!")
        print("=" * 40)
        print(f"Content: {response.content}")
        print(f"Tokens: {response.tokens_used}")
        print(f"Model: {response.model}")
        print(f"Provider: {response.provider}")
        print(f"Finish: {response.finish_reason}")
        print(f"Filtered: {response.was_filtered}")

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
