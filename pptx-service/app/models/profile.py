"""Template profile models — backward-compatible re-exports.

All profile models have been consolidated into app.templates_mgmt.models.
This module re-exports for backward compatibility.
"""

from app.templates_mgmt.models import (  # noqa: F401
    ColorDNA,
    TypographyDNA,
    PlaceholderDetail,
    LayoutDetail,
    ChartGuidelines,
    ImageGuidelines,
    TemplateProfile,
)
