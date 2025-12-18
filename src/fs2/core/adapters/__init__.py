"""Adapter layer - ABC interfaces and implementations.

Architecture:
- Each adapter ABC is in its own file: {name}_adapter.py or file_{name}.py
- Implementations go in: {name}_adapter_{impl}.py or file_{name}_impl.py
- Exceptions in: exceptions.py

Public API:
- LogAdapter: ABC for logging (debug/info/warning/error)
- ConsoleLogAdapter: Development logging to stdout/stderr
- FakeLogAdapter: Test double for logging (captures messages)
- ConsoleAdapter: ABC for console I/O (print/input)
- SampleAdapter: ABC demonstrating full adapter pattern (process/validate)
- FakeSampleAdapter: Test double for SampleAdapter (canonical implementation example)
- SampleAdapterConfig: Configuration for SampleAdapter
- FileScanner: ABC for file scanning with gitignore support
- FakeFileScanner: Test double for FileScanner
- FileSystemScanner: Production FileScanner using pathspec
- ASTParser: ABC for AST parsing with tree-sitter
- FakeASTParser: Test double for ASTParser
- TreeSitterParser: Production ASTParser using tree-sitter-language-pack
- AdapterError: Base exception for all adapter errors
- AuthenticationError: Authentication failed
- AdapterConnectionError: Connection failed
- FileScannerError: File scanning operation failed
- ASTParserError: AST parsing operation failed
- GraphStoreError: Graph storage operation failed
- LLMAdapter: ABC for LLM provider access
- FakeLLMAdapter: Test double for LLMAdapter
- OpenAIAdapter: OpenAI API integration
- AzureOpenAIAdapter: Azure OpenAI API integration
- LLMAdapterError: Base LLM adapter error
- LLMAuthenticationError: LLM authentication failed
- LLMRateLimitError: LLM rate limit exceeded
- LLMContentFilterError: LLM content filtered

See tests/docs/test_sample_adapter_pattern.py for complete usage documentation.
"""

from fs2.core.adapters.ast_parser import ASTParser
from fs2.core.adapters.ast_parser_fake import FakeASTParser
from fs2.core.adapters.ast_parser_impl import TreeSitterParser
from fs2.core.adapters.console_adapter import ConsoleAdapter
from fs2.core.adapters.exceptions import (
    AdapterConnectionError,
    AdapterError,
    ASTParserError,
    AuthenticationError,
    FileScannerError,
    GraphStoreError,
    LLMAdapterError,
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMRateLimitError,
)
from fs2.core.adapters.file_scanner import FileScanner
from fs2.core.adapters.file_scanner_fake import FakeFileScanner
from fs2.core.adapters.file_scanner_impl import FileSystemScanner
from fs2.core.adapters.log_adapter import LogAdapter
from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter
from fs2.core.adapters.log_adapter_fake import FakeLogAdapter
from fs2.core.adapters.llm_adapter import LLMAdapter
from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter
from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter
from fs2.core.adapters.sample_adapter import SampleAdapter
from fs2.core.adapters.sample_adapter_fake import FakeSampleAdapter, SampleAdapterConfig

__all__ = [
    "LogAdapter",
    "ConsoleLogAdapter",
    "FakeLogAdapter",
    "ConsoleAdapter",
    "SampleAdapter",
    "FakeSampleAdapter",
    "SampleAdapterConfig",
    "FileScanner",
    "FakeFileScanner",
    "FileSystemScanner",
    "ASTParser",
    "FakeASTParser",
    "TreeSitterParser",
    "AdapterError",
    "AuthenticationError",
    "AdapterConnectionError",
    "FileScannerError",
    "ASTParserError",
    "GraphStoreError",
    "LLMAdapter",
    "FakeLLMAdapter",
    "OpenAIAdapter",
    "AzureOpenAIAdapter",
    "LLMAdapterError",
    "LLMAuthenticationError",
    "LLMRateLimitError",
    "LLMContentFilterError",
]
