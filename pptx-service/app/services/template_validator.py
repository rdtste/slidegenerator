"""Template validator — backward-compatible re-exports.

All validation has been consolidated into app.templates_mgmt.validator.
This module re-exports for backward compatibility.
"""

from app.templates_mgmt.validator import (  # noqa: F401
    TemplateValidator,
    TemplateValidationResult,
    TemplateValidationIssue,
    TemplateMetadata,
    TemplateLayout,
)
