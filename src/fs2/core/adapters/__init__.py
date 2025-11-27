"""Adapter layer - ABC interfaces and implementations.

Architecture:
- Each adapter ABC is in its own file: {name}_adapter.py
- Implementations go in: {name}_adapter_{impl}.py (e.g., log_adapter_console.py)
- Exceptions in: exceptions.py

Public API:
- LogAdapter: ABC for logging (debug/info/warning/error)
- ConsoleAdapter: ABC for console I/O (print/input)
- SampleAdapter: ABC demonstrating full adapter pattern (process/validate)
- FakeSampleAdapter: Test double for SampleAdapter (canonical implementation example)
- SampleAdapterConfig: Configuration for SampleAdapter
- AdapterError: Base exception for all adapter errors
- AuthenticationError: Authentication failed
- AdapterConnectionError: Connection failed

See tests/docs/test_sample_adapter_pattern.py for complete usage documentation.
"""

from fs2.core.adapters.console_adapter import ConsoleAdapter
from fs2.core.adapters.exceptions import (AdapterConnectionError, AdapterError,
                                          AuthenticationError)
from fs2.core.adapters.log_adapter import LogAdapter
from fs2.core.adapters.sample_adapter import SampleAdapter
from fs2.core.adapters.sample_adapter_fake import (FakeSampleAdapter,
                                                   SampleAdapterConfig)

__all__ = [
    "LogAdapter",
    "ConsoleAdapter",
    "SampleAdapter",
    "FakeSampleAdapter",
    "SampleAdapterConfig",
    "AdapterError",
    "AuthenticationError",
    "AdapterConnectionError",
]
