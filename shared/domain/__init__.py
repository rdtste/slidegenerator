"""Shared domain models for the Slidegenerator platform.

These models define the contract between:
- Python pipeline (content intelligence, planning, validation)
- TypeScript render-service (visual rendering, PPTX export)
"""

from .presentation_spec import (  # noqa: F401
    PresentationSpec,
    SlideSpec,
    ContentBlock,
    ContentBlockType,
    VisualAsset,
    VisualAssetType,
    VisualAssetRole,
    ChartSpec,
    ChartType,
    SlideIntent,
    RenderMode,
    QualityScore,
    QualityDimension,
    TemplateDescriptor,
    TemplateLayout,
    PlaceholderSlot,
    BulletItem,
)
