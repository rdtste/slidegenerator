# ADR-004: Visual Quality Gate (Das Auge)

**Status:** Accepted  
**Date:** 2026-04-02  
**Decision Makers:** Architecture Team

## Context

The most critical user-facing problem is slides that look "unfinished" — raw icon descriptors ("Monastery icon", "Hopfenpflanze"), placeholder text, AI generation prompts, and layout issues visible on the final output. These leaks destroy user trust immediately.

The existing QA pipeline has two layers:
1. **Structural validation** — Pydantic schema checks, content leak regex rules
2. **Visual review** — LibreOffice renders PPTX → PDF → JPEG → Gemini Vision scores the design

However, the visual review was explicitly told to "ignore text content" and focus only on layout aesthetics. This meant content leaks passed through unchecked by the visual layer — exactly the opposite of what's needed.

## Decision

Implement a mandatory **Visual Quality Gate** ("Das Auge") that blocks export until slides pass both structural AND visual checks:

### Three-Layer Quality Architecture

#### Layer 1: Structural Validation (Pre-render)
- Content leak detection (L001-L003 rules): regex patterns catch raw descriptors, placeholders, AI prompts
- Schema validation: all required fields present, correct types
- Runs on `PresentationSpec` before any rendering
- **Blocks rendering** if critical issues found

#### Layer 2: Visual Quality Review (Post-render)
- Each rendered slide screenshotted and sent to Gemini Vision
- **Priority #0: Content Leak Detection** — any visible raw descriptor, placeholder, or prompt text = automatic score 1 (fail)
- Priorities #1-7: Layout, typography, whitespace, alignment, color, density, flow
- **Blocks export** if any slide scores below threshold (currently 6/10)

#### Layer 3: Programmatic Fix Loop (Auto-repair)
- Vision review returns structured fix instructions (category, target, params)
- Fix categories: CONTENT_LEAK, FONT_SIZE, SPACING, POSITION, SIZE, PADDING, COLOR, REMOVE
- System applies fixes programmatically and re-renders
- Maximum 2 fix iterations to prevent infinite loops
- CONTENT_LEAK fixes: zero-size the element and clear its content

### Content Leak Detection (Highest Priority)
Content leaks are treated as the most severe defect category:

| Rule | Detects | Action |
|------|---------|--------|
| L001 | Raw icon descriptors, stock photo descriptions, AI prompts | Block + auto-fix |
| L002 | Empty visible fields that should have content | Warn |
| L003 | `image_description` / `generation_prompt` in visible text | Block + auto-fix |

Patterns detected:
- Icon hints: `"monastery icon"`, `"shield or scroll"`, `"Hopfenpflanze"`
- AI prompts: `"photorealistic"`, `"stock photo of"`, `"high quality"`
- Placeholders: `[placeholder]`, `{variable}`, `Lorem ipsum`, `TBD`, `TODO`
- Technical: filenames, JSON fragments, UUIDs

### Quality Score Structure
```
QualityScore:
  total: float (0-100)
  passed: bool
  dimensions:
    - name: "content_integrity"  # No leaks
    - name: "layout_quality"     # Whitespace, alignment
    - name: "typography"         # Hierarchy, sizing
    - name: "visual_balance"     # Weight distribution
    - name: "color_harmony"      # Palette usage
```

## Consequences

### Positive
- No slide with visible content leaks can reach the user
- Automated fix loop reduces manual intervention
- Quality scoring provides measurable improvement tracking
- Content leak detection as Priority #0 ensures it's never skipped

### Negative
- Additional latency per generation (screenshot + Vision API call per slide)
- Gemini Vision API costs for each review cycle
- Fix loop can add 2x rendering time in worst case

### Mitigations
- Structural validation (Layer 1) catches most issues before expensive rendering
- Fix loop capped at 2 iterations
- Vision review can be parallelized across slides
- Quality threshold configurable per deployment
