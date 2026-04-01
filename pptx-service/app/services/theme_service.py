"""Theme service — backward-compatible re-exports.

All theme operations have been consolidated into app.templates_mgmt.theme.
This module re-exports for backward compatibility.
"""

from app.templates_mgmt.theme import (  # noqa: F401
    extract_theme,
    extract_structure,
    theme_to_css,
    TemplateTheme,
    PlaceholderConstraint,
    LayoutConstraint,
    classify_layout as _classify_layout,
)
