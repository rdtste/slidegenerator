# ADR-003: Template Registry & Profile System

**Status:** Accepted  
**Date:** 2026-04-02  
**Decision Makers:** Architecture Team

## Context

Corporate users upload `.pptx` templates that define their brand: colors, fonts, logos, and slide layouts. The system must:

1. Understand what layouts a template offers (title slide, content, two-column, etc.)
2. Map each layout's placeholders to semantic slots (title, body, image, chart)
3. Extract the template's color DNA and typography rules
4. Match slide intents to appropriate template layouts at generation time

Currently, template analysis happens once at upload via Gemini Vision (screenshot each layout → classify). The results are stored in `.profile.json` alongside the template file. This works but is fragile — the profile format is ad-hoc and tightly coupled to the python-pptx renderer.

## Decision

Formalize the template system with a **TemplateDescriptor** as part of the shared domain model:

### TemplateDescriptor Schema
```
TemplateDescriptor:
  template_id: string        # Unique identifier
  filename: string            # Original upload filename
  layouts: TemplateLayout[]   # Available layouts with metadata
  color_scheme: dict          # Extracted color palette
  font_scheme: dict           # Typography rules

TemplateLayout:
  layout_index: int           # Index in the PPTX slide master
  layout_name: string         # Human-readable name
  supported_intents: SlideIntent[]  # Which slide types this layout supports
  placeholders: PlaceholderSlot[]   # Available placeholder slots

PlaceholderSlot:
  slot_id: string             # Unique within layout
  slot_type: string           # title, body, image, chart, footer
  x_cm, y_cm: float           # Position
  width_cm, height_cm: float  # Dimensions
```

### Analysis Pipeline
1. **Upload** → store `.pptx` in shared volume
2. **Structural Analysis** → python-pptx extracts layouts, placeholders, dimensions
3. **Visual Analysis** → Gemini Vision classifies each layout's purpose and supported intents
4. **Profile Generation** → creates `TemplateDescriptor` stored as `.profile.json`
5. **Registry** → backend maintains an in-memory registry of available templates

### Intent Matching
At generation time, the pipeline matches each `SlideSpec.intent` to the best `TemplateLayout` based on `supported_intents`. If no exact match exists, fall back to a generic content layout.

## Consequences

### Positive
- Formalized, typed template metadata shared between Python and TypeScript
- Deterministic layout selection based on structured data
- Template profiles are portable and cacheable
- Clear separation between analysis (one-time) and rendering (per-generation)

### Negative
- Existing `.profile.json` files need migration to the new format
- Visual analysis via Gemini adds latency to template upload (acceptable — one-time cost)
