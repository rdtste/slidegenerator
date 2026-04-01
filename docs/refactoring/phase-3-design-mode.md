# Phase 3: Design Mode

## Goal
Upgrade visual quality toward Gamma.app-level output through better theme integration, typography, and spacing.

## Work Packages

### D-01: ColorDNA Integration
When a template is selected in Design Mode:
- Load template's `ColorDNA` from profile
- Use `accent1` as `accent_color` instead of hardcoded value
- Use `chart_colors` for chart rendering
- Apply `heading` color to headlines, `text` color to body

### D-02: Dimension-Aware Blueprints
Current blueprints use fixed positions for 33.9cm x 19.1cm slides.
- Parametrize blueprint positions by slide dimensions
- Scale positions proportionally for 4:3 templates
- Add blueprint variants for different slide aspect ratios

### D-03: Typography Improvements
- Increase contrast between typography levels
- Add letter-spacing support for headlines
- Use template fonts when available (from TypographyDNA)
- Improve auto-fitting with character-width tables per font

### D-04: Whitespace Control
- Define minimum padding rules (distance from slide edges)
- Define minimum spacing between elements
- Validate element spacing in Layout Engine
- Auto-adjust when elements would overlap

### D-05: Design Review Enhancement
- Add rules for minimum whitespace percentage
- Check text contrast against background color
- Verify visual hierarchy (headline larger than body)
- Check alignment consistency within slides

## Acceptance Criteria
- [ ] Design Mode uses template colors when template provided
- [ ] Blueprints work correctly for 16:9 and 4:3 slides
- [ ] Typography hierarchy is visually distinct (clear size/weight steps)
- [ ] No element overlaps in generated presentations
- [ ] Design Review catches common visual issues

## Risk: Medium
Visual quality is subjective. Needs testing with diverse content and templates.
