"""Smart content service components.

Phase 1: Exception hierarchy for stable contracts
Phase 2: TemplateService for Jinja2 prompt rendering
Phase 3: SmartContentService for AI-powered summaries
"""

from fs2.core.services.smart_content.exceptions import (
    SmartContentError,
    SmartContentProcessingError,
    TemplateError,
)
from fs2.core.services.smart_content.smart_content_service import SmartContentService
from fs2.core.services.smart_content.template_service import TemplateService

__all__ = [
    "SmartContentError",
    "TemplateError",
    "SmartContentProcessingError",
    "TemplateService",
    "SmartContentService",
]
