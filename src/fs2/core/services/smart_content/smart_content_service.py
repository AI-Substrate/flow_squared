"""SmartContentService for AI-powered code node summaries.

Provides:
- Single-node smart content generation via LLMService
- Hash-based skip logic (AC5) and regeneration (AC6)
- Token-based content truncation (AC13)
- Error handling with graceful degradation (CD07)

Per CD01: Accepts ConfigurationService, extracts config internally.
Per CD03: Returns new CodeNode instances (frozen immutability).
Per CD12: Catches domain exceptions only, never SDK exceptions.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from fs2.config.objects import SmartContentConfig
from fs2.core.adapters.exceptions import (
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMRateLimitError,
    TokenCounterError,
)
from fs2.core.services.smart_content.exceptions import SmartContentProcessingError

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.token_counter_adapter import TokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.template_service import TemplateService


logger = logging.getLogger(__name__)


# Minimum content length to warrant LLM processing
_MIN_CONTENT_LENGTH = 10


class SmartContentService:
    """Service for generating AI-powered summaries of code nodes.

    Uses LLMService for generation, TemplateService for prompts, and
    TokenCounterAdapter for truncation decisions.

    Example:
        >>> config = FS2ConfigurationService()
        >>> service = SmartContentService(
        ...     config=config,
        ...     llm_service=LLMService.create(config),
        ...     template_service=TemplateService(config),
        ...     token_counter=TiktokenTokenCounterAdapter(config),
        ... )
        >>> updated_node = await service.generate_smart_content(node)
        >>> print(updated_node.smart_content)
    """

    def __init__(
        self,
        config: ConfigurationService,
        llm_service: LLMService,
        template_service: TemplateService,
        token_counter: TokenCounterAdapter,
    ) -> None:
        """Initialize the service with required dependencies.

        Per CD01: Extracts SmartContentConfig via config.require() internally.

        Args:
            config: ConfigurationService for accessing configuration.
            llm_service: LLMService for AI generation.
            template_service: TemplateService for prompt rendering.
            token_counter: TokenCounterAdapter for token counting.

        Raises:
            ConfigurationError: If SmartContentConfig is not registered.
        """
        self._config = config.require(SmartContentConfig)
        self._llm_service = llm_service
        self._template_service = template_service
        self._token_counter = token_counter

    async def generate_smart_content(self, node: CodeNode) -> CodeNode:
        """Generate smart content for a single code node.

        Implements hash-based skip logic (AC5), regeneration (AC6),
        truncation (AC13), and error handling (CD07).

        Args:
            node: The CodeNode to process.

        Returns:
            A new CodeNode with smart_content and smart_content_hash set.
            Returns the original node unchanged if hash matches (AC5).

        Raises:
            LLMAuthenticationError: Auth failures propagate up (CD07).
            SmartContentProcessingError: Rate limit or other recoverable errors.
        """
        # AC5: Skip if content unchanged
        if self._should_skip(node):
            return node

        # CD08: Skip empty/trivial content
        if self._is_empty_or_trivial(node):
            return self._create_placeholder_node(node)

        # Prepare content (with truncation if needed)
        content = self._prepare_content(node)

        # Build prompt via TemplateService (AC8)
        context = self._build_context(node, content)
        prompt = self._template_service.render_for_category(node.category, context)

        # Call LLM with error handling (CD07)
        smart_content = await self._generate_with_error_handling(node, prompt)

        # Create new node with updated smart_content and hash (CD03)
        return replace(
            node,
            smart_content=smart_content,
            smart_content_hash=node.content_hash,
        )

    def _should_skip(self, node: CodeNode) -> bool:
        """Check if node should skip regeneration (AC5).

        Returns True if:
        - smart_content_hash matches content_hash
        - AND smart_content is already set
        """
        return (
            node.smart_content_hash is not None
            and node.smart_content_hash == node.content_hash
            and node.smart_content is not None
        )

    def _is_empty_or_trivial(self, node: CodeNode) -> bool:
        """Check if content is too short to warrant LLM processing (CD08)."""
        return len(node.content.strip()) < _MIN_CONTENT_LENGTH

    def _create_placeholder_node(self, node: CodeNode) -> CodeNode:
        """Create node with placeholder smart_content for empty/trivial content."""
        return replace(
            node,
            smart_content=f"[Empty content - no summary generated for {node.category} '{node.name or 'anonymous'}']",
            smart_content_hash=node.content_hash,
        )

    def _prepare_content(self, node: CodeNode) -> str:
        """Prepare content for prompt, truncating if needed (AC13)."""
        content = node.content
        try:
            token_count = self._token_counter.count_tokens(content)
        except TokenCounterError as e:
            raise SmartContentProcessingError(
                f"Token counting failed for node {node.node_id}: {e}"
            ) from e
        max_tokens = self._config.max_input_tokens

        if token_count > max_tokens:
            logger.warning(
                "Content truncated for node %s: %d tokens -> %d tokens",
                node.node_id,
                token_count,
                max_tokens,
            )
            # Truncate content (simple approach: truncate characters proportionally)
            # A more sophisticated approach would use token boundaries
            ratio = max_tokens / token_count
            truncate_at = int(len(content) * ratio * 0.9)  # 10% safety margin
            content = content[:truncate_at] + "\n\n[TRUNCATED]"

        return content

    def _build_context(self, node: CodeNode, content: str) -> dict:
        """Build context dictionary for template rendering (AC8)."""
        return {
            "name": node.name or "anonymous",
            "qualified_name": node.qualified_name,
            "category": node.category,
            "ts_kind": node.ts_kind,
            "language": node.language,
            "content": content,
            "signature": node.signature or "",
        }

    async def _generate_with_error_handling(
        self, node: CodeNode, prompt: str
    ) -> str:
        """Call LLM with error handling per CD07."""
        try:
            # Get max_tokens for output from config
            max_output_tokens = self._template_service.resolve_max_tokens(node.category)

            response = await self._llm_service.generate(
                prompt,
                max_tokens=max_output_tokens,
            )
            content = response.content

            # Check for empty/whitespace response
            if not content or not content.strip():
                raise SmartContentProcessingError(
                    f"LLM returned empty/blank response for node {node.node_id}"
                )

            return content.strip()

        except LLMAuthenticationError:
            # Auth errors must propagate (config issue, batch should fail)
            raise

        except LLMContentFilterError:
            # Content filter: return fallback placeholder
            return "[Content filtered] - summary could not be generated due to content policies"

        except LLMRateLimitError as e:
            # Rate limit: log warning and raise recoverable error
            logger.warning(
                "Rate limit hit for node %s: %s",
                node.node_id,
                str(e),
            )
            raise SmartContentProcessingError(
                f"Rate limit exceeded for node {node.node_id}: {e}"
            ) from e
