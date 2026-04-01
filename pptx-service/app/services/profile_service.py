"""Profile service — backward-compatible re-exports.

All profiling operations have been consolidated into app.templates_mgmt.profiler.
This module re-exports for backward compatibility.
"""

from app.templates_mgmt.profiler import extract_profile  # noqa: F401
