"""Template service — backward-compatible re-exports.

All template operations have been consolidated into app.templates_mgmt.service.
This module re-exports for backward compatibility.
"""

from app.templates_mgmt.service import (  # noqa: F401
    template_dirs as _template_dirs,
    load_potx_as_presentation as _load_potx_as_presentation,
    list_templates,
    get_template_path,
    load_presentation,
    get_layout_names,
    find_layout,
    inspect_template as _inspect_template,
    get_default_template_info as _get_default_template_info,
)
