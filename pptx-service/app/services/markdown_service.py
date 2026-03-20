"""Markdown parser — converts LLM Markdown output into structured SlideContent objects."""

from __future__ import annotations

import logging
import re

from app.models.schemas import PresentationData, SlideContent

logger = logging.getLogger(__name__)

_LAYOUT_RE = re.compile(r"<!--\s*layout:\s*(\w+)\s*-->")
_NOTES_RE = re.compile(r"<!--\s*notes:\s*(.*?)\s*-->", re.DOTALL)
_HEADING1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_HEADING2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_BULLET_RE = re.compile(r"^[-*]\s+(.+)$", re.MULTILINE)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_CHART_BLOCK_RE = re.compile(r"```chart\s*\n(.*?)\n```", re.DOTALL)
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

VALID_LAYOUTS = {"title", "section", "content", "two_column", "image", "chart", "closing"}


def parse_markdown(markdown: str) -> PresentationData:
    """Parse the structured Markdown into a PresentationData object."""
    # Strip Marp YAML front matter before splitting into slides
    clean = _FRONTMATTER_RE.sub("", markdown.strip())
    raw_slides = _split_slides(clean)
    slides: list[SlideContent] = []
    presentation_title = "Presentation"

    for i, raw in enumerate(raw_slides):
        slide = _parse_slide(raw.strip())
        if slide:
            slides.append(slide)
            if i == 0 and slide.title:
                presentation_title = slide.title

    logger.info(f"Parsed {len(slides)} slides from Markdown")
    return PresentationData(title=presentation_title, slides=slides)


def _split_slides(markdown: str) -> list[str]:
    """Split Markdown by horizontal rule '---' slide separators."""
    parts = re.split(r"^\s*---\s*$", markdown, flags=re.MULTILINE)
    return [p for p in parts if p.strip()]


def _parse_slide(raw: str) -> SlideContent | None:
    """Parse a single slide block into a SlideContent object."""
    if not raw.strip():
        return None

    layout_match = _LAYOUT_RE.search(raw)
    layout = layout_match.group(1) if layout_match else "content"
    if layout not in VALID_LAYOUTS:
        layout = "content"

    notes_match = _NOTES_RE.search(raw)
    notes = notes_match.group(1).strip() if notes_match else ""

    clean = _LAYOUT_RE.sub("", raw)
    clean = _NOTES_RE.sub("", clean).strip()

    headings_h1 = _HEADING1_RE.findall(clean)
    headings_h2 = _HEADING2_RE.findall(clean)
    bullets = _BULLET_RE.findall(clean)

    # Extract image description from ![alt](url) syntax
    image_match = _IMAGE_RE.search(clean)
    image_description = image_match.group(1).strip() if image_match else ""

    # Extract chart data from ```chart ... ``` block
    chart_match = _CHART_BLOCK_RE.search(clean)
    chart_data = chart_match.group(1).strip() if chart_match else ""

    title = headings_h1[0].strip() if headings_h1 else ""
    subtitle = headings_h2[0].strip() if headings_h2 else ""

    body_lines = []
    for line in clean.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            continue
        if stripped.startswith("## Links") or stripped.startswith("## Rechts"):
            continue
        if _IMAGE_RE.match(stripped):
            continue
        if stripped.startswith("```"):
            continue
        if chart_data and stripped in chart_data:
            continue
        if stripped:
            body_lines.append(stripped)
    body = "\n".join(body_lines)

    left_column = ""
    right_column = ""
    if layout == "two_column":
        left_column, right_column = _parse_two_columns(clean)

    return SlideContent(
        layout=layout,
        title=title,
        subtitle=subtitle,
        body=body,
        bullets=bullets,
        notes=notes,
        image_description=image_description,
        chart_data=chart_data,
        left_column=left_column,
        right_column=right_column,
    )


def _parse_two_columns(text: str) -> tuple[str, str]:
    """Extract left/right column content from two_column layout."""
    left_markers = ["## Links", "## Left"]
    right_markers = ["## Rechts", "## Right"]

    left_start = -1
    right_start = -1

    text_lower = text.lower()
    for marker in left_markers:
        idx = text_lower.find(marker.lower())
        if idx >= 0:
            left_start = idx + len(marker)
            break

    for marker in right_markers:
        idx = text_lower.find(marker.lower())
        if idx >= 0:
            right_start = idx + len(marker)
            break

    if left_start < 0 and right_start < 0:
        return "", ""

    if left_start >= 0 and right_start >= 0:
        if left_start < right_start:
            left_text = text[left_start:right_start - len("## Rechts")]
            right_text = text[right_start:]
        else:
            right_text = text[right_start:left_start - len("## Links")]
            left_text = text[left_start:]
    elif left_start >= 0:
        left_text = text[left_start:]
        right_text = ""
    else:
        left_text = ""
        right_text = text[right_start:]

    left_bullets = _BULLET_RE.findall(left_text)
    right_bullets = _BULLET_RE.findall(right_text)

    return "\n".join(f"- {b}" for b in left_bullets), "\n".join(f"- {b}" for b in right_bullets)
