# Phase 2: Template Mode

## Goal
Build robust corporate template filling using analyzed template profiles and structured placeholder mapping.

## Work Packages

### T-01: PlaceholderMapping Model
Define structured mapping from semantic roles to template placeholders:
```python
class PlaceholderSlot:
    role: str           # "title", "body", "bullets", "image", "chart"
    ph_index: int       # Placeholder index in the layout
    ph_type: int        # OOXML placeholder type
    max_chars: int      # Content limit
    width_cm: float     # Available width
    height_cm: float    # Available height

class LayoutMapping:
    layout_index: int
    layout_name: str
    semantic_type: str  # "title", "content", "image", etc.
    slots: list[PlaceholderSlot]

class TemplatePlaceholderMap:
    template_id: str
    layouts: list[LayoutMapping]
```

### T-02: Slot Mapper
Maps content blocks to template placeholder slots:
- Input: `SlideSpec` + `LayoutMapping`
- Output: `dict[int, ContentBlock]` (placeholder index → content)
- Handles overflow (content too long for slot → truncation with warning)
- Handles missing slots (content block has no matching placeholder → skip with warning)

### T-03: Refactor Template Analyzer
Move `profile_service.py` logic into `templates/analyzer.py`:
- Keep all existing analysis logic
- Add `PlaceholderMapping` generation from `LayoutDetail`
- Store mapping in `.profile.json` alongside existing data

### T-04: Template Mode Renderer
Extract placeholder-filling logic from `pptx_service.py` into `rendering/template_renderer.py`:
- Uses `PlaceholderMapping` instead of heuristic placeholder search
- Falls back to keyword scoring when mapping unavailable
- Wraps existing `_handle_*` functions

### T-05: Dynamic Layout Mapping
Replace `_REWE_LAYOUT_MAP` in `pptx_renderer_v2.py`:
- Load layout mapping from template profile
- Map V2 `SlideType` to template layout index via analyzed profile
- Fallback to keyword scoring

### T-06: Template Versioning
Add version tracking to template upload:
- Increment version counter in `.meta.json`
- Rename old file to `{id}.v{n}.{ext}`
- Re-analyze on version change

## Acceptance Criteria
- [ ] Template Mode produces correct PPTX for REWE template
- [ ] Template Mode produces correct PPTX for any uploaded template
- [ ] No hardcoded layout maps remain
- [ ] Placeholder mapping stored in profile
- [ ] Template re-upload preserves previous version
- [ ] Content overflow handled gracefully

## Risk: Medium
Touches rendering code. Extensive testing needed with actual templates.
