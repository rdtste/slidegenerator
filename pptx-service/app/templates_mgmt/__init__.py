"""Template management — registry, analysis, storage, versioning.

Public API:
    from app.templates_mgmt import (
        # Core operations
        get_template_path, load_presentation, list_templates, find_layout,
        # Registry
        FileTemplateRegistry,
        # Profiling
        extract_profile,
        # Theme
        extract_theme, extract_structure, theme_to_css, TemplateTheme,
        # Validation
        TemplateValidator,
        # Models
        TemplateDescriptor, TemplatePlaceholderMap, TemplateProfile,
    )
"""
