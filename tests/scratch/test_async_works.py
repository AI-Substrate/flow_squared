"""Quick test to verify async test mode works."""

import pytest


@pytest.mark.unit
async def test_async_works():
    """Verify pytest-asyncio is working with asyncio_mode=auto."""
    # Simple async operation
    result = await async_add(1, 2)
    assert result == 3


async def async_add(a: int, b: int) -> int:
    """Simple async function for testing."""
    return a + b
