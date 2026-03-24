---
name: pptx
description: Use this skill any time a .pptx file is involved in any way — as input, output, or both. This includes creating slide decks, pitch decks, or presentations; reading, parsing, or extracting text from any .pptx file (even if the extracted content will be used elsewhere, like in an email or summary); editing, modifying, or updating existing presentations; combining or splitting slide files; working with templates, layouts, speaker notes, or comments. Trigger whenever the user mentions "deck," "slides," "presentation," or references a .pptx filename, regardless of what they plan to do with the content afterward. If a .pptx file needs to be opened, created, or touched, use this skill.

---

<!-- Tip: Use /create-skill in chat to generate content with agent assistance -->


# Quick Reference

| Task | How to |
|------|--------|
| Read/analyze content | `python -m markitdown presentation.pptx` |
| Edit or create from template | See editing workflow below |
| Create from scratch | Use pptxgenjs or similar tools |

# Reading Content

Extract text: `python -m markitdown presentation.pptx`
Visual overview: `python scripts/thumbnail.py presentation.pptx`

# Editing Workflow

1. Analyze template with `thumbnail.py`
2. Unpack → manipulate slides → edit content → clean → pack

# Creating from Scratch

Use when no template or reference presentation is available. See pptxgenjs or equivalent libraries.

# Design Ideas

## Before Starting
* Pick a bold, content-informed color palette
* One color should dominate, with 1-2 supporting tones and one accent
* Use dark backgrounds for title/conclusion, light for content, or commit to a consistent scheme
* Commit to a visual motif and repeat it across slides

## For Each Slide
* Every slide needs a visual element (image, chart, icon, or shape)
* Vary layouts: two-column, icon+text rows, grids, half-bleed images, etc.
* Use large stat callouts, comparison columns, timelines/process flows
* Add icons, accent text, and ensure strong contrast

## Typography & Spacing
* Choose interesting font pairings (not just Arial)
* Slide title: 36-44pt bold; Section header: 20-24pt bold; Body: 14-16pt
* 0.5" minimum margins, 0.3-0.5" between blocks

## Avoid (Common Mistakes)
* Don't repeat the same layout
* Don't center body text (left-align paragraphs/lists)
* Don't default to blue; pick topic-specific colors
* Don't create text-only slides
* Don't use low-contrast elements
* NEVER use accent lines under titles

# QA (Required)

## Content QA
* Check for missing content, typos, wrong order: `python -m markitdown output.pptx`
* For templates, check for leftover placeholder text:
	`python -m markitdown output.pptx | grep -iE "xxxx|lorem|ipsum|this.*(page|slide).*layout"`

## Visual QA
* Convert slides to images for inspection (see below)
* Inspect for: overlapping elements, text overflow, low-contrast text/icons, uneven gaps, leftover placeholders

## Verification Loop
1. Generate slides → Convert to images → Inspect
2. List issues found (if none, look again more critically)
3. Fix issues
4. Re-verify affected slides
5. Repeat until a full pass reveals no new issues

# Converting to Images

Convert presentations to images for visual QA:
```
python scripts/office/soffice.py --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 150 output.pdf slide
```
This creates `slide-01.jpg`, `slide-02.jpg`, etc.

# Dependencies

* `pip install "markitdown[pptx]"` - text extraction
* `pip install Pillow` - thumbnail grids
* `npm install -g pptxgenjs` - creating from scratch
* LibreOffice (`soffice`) - PDF conversion
* Poppler (`pdftoppm`) - PDF to images

# Keywords

presentation, pptx, slide deck, PowerPoint, template, layout, speaker notes, extract, edit, QA, design, color palette, typography, visual QA, automation