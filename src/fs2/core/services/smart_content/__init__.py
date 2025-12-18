"""Smart content service components (Phase 3+).

Phase 1 provides only the exception hierarchy to establish stable contracts
for later phases.
"""

from fs2.core.services.smart_content.exceptions import (
    SmartContentError,
    SmartContentProcessingError,
    TemplateError,
)
from fs2.core.services.smart_content.template_service import TemplateService

__all__ = [
    "SmartContentError",
    "TemplateError",
    "SmartContentProcessingError",
    "TemplateService",
]
