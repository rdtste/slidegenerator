"""Auto-fix logic for slide-level issues."""

from __future__ import annotations

from app.schemas.models import (
    BulletsBlock, CardBlock, ImageRole, SlidePlan, SlideType,
    TimelineEntryBlock,
)

# Re-use limits from slide_rules to stay consistent.
_BULLET_LIMITS: dict[SlideType, int] = {
    SlideType.BULLETS_FOCUSED: 3,
    SlideType.CHART_INSIGHT: 2,
    SlideType.CLOSING: 3,
}

MAX_HEADLINE_LEN = 70
MAX_BULLET_LEN = 80


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _truncate_at_word_boundary(text: str, max_len: int) -> str:
    """Truncate *text* to at most *max_len* chars, cutting at a word boundary."""
    if len(text) <= max_len:
        return text
    truncated = text[: max_len - 1]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "\u2026"


# ---------------------------------------------------------------------------
# public fix functions
# ---------------------------------------------------------------------------

def truncate_headline(slide: SlidePlan, max_len: int = MAX_HEADLINE_LEN) -> SlidePlan:
    """Truncate the headline at a word boundary if it exceeds *max_len*."""
    if len(slide.headline) > max_len:
        slide.headline = _truncate_at_word_boundary(slide.headline, max_len)
    return slide


def trim_bullets(slide: SlidePlan, max_count: int | None = None) -> SlidePlan:
    """Remove excess bullets from the first BulletsBlock."""
    if max_count is None:
        max_count = _BULLET_LIMITS.get(slide.slide_type)
    if max_count is None:
        return slide
    for block in slide.content_blocks:
        if isinstance(block, BulletsBlock) and len(block.items) > max_count:
            block.items = block.items[:max_count]
    return slide


def truncate_bullet_text(slide: SlidePlan, max_len: int = MAX_BULLET_LEN) -> SlidePlan:
    """Truncate each bullet's text at a word boundary if it exceeds *max_len*."""
    for block in slide.content_blocks:
        if isinstance(block, BulletsBlock):
            for item in block.items:
                if len(item.text) > max_len:
                    item.text = _truncate_at_word_boundary(item.text, max_len)
    return slide


def fix_decorative_image(slide: SlidePlan) -> SlidePlan:
    """Upgrade decorative images to 'supporting' role (except fullbleed)."""
    if slide.slide_type == SlideType.IMAGE_FULLBLEED:
        return slide
    if slide.visual and slide.visual.image_role == ImageRole.DECORATIVE:
        slide.visual.image_role = ImageRole.SUPPORTING
    return slide


def truncate_content_block_text(slide: SlidePlan) -> SlidePlan:
    """Truncate overly long text in content blocks."""
    for block in slide.content_blocks:
        if isinstance(block, CardBlock):
            block.title = _truncate_at_word_boundary(block.title, 35)
            block.body = _truncate_at_word_boundary(block.body, 120)
        elif isinstance(block, TimelineEntryBlock):
            block.date = _truncate_at_word_boundary(block.date, 25)
            block.title = _truncate_at_word_boundary(block.title, 50)
            block.description = _truncate_at_word_boundary(block.description, 100)
    return slide


def needs_llm_regeneration(slide: SlidePlan, errors: list[str]) -> bool:
    """Check if errors require LLM regeneration (can't be fixed by simple truncation)."""
    llm_keywords = [
        "underfilled", "topic label", "not a statement",
        "content block(s)", "minimum is", "functional purpose",
        "thin description", "thin body",
    ]
    for err in errors:
        err_lower = err.lower()
        if any(kw in err_lower for kw in llm_keywords):
            return True
    return False


def apply_auto_fixes(slide: SlidePlan) -> SlidePlan:
    """Apply all applicable auto-fixes to *slide* and return the mutated copy."""
    slide = truncate_headline(slide)
    slide = trim_bullets(slide)
    slide = truncate_bullet_text(slide)
    slide = fix_decorative_image(slide)
    slide = truncate_content_block_text(slide)
    return slide
