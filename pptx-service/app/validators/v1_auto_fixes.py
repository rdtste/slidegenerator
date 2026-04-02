"""Auto-fix logic for V1 SlideContent model.

Mirrors auto_fixes.py (V2) but operates on the simpler V1 SlideContent model.
Applied before rendering to prevent text overflow and improve visual quality.
"""

from __future__ import annotations

import logging

from app.models.schemas import SlideContent, PresentationData
from app.validators.v1_slide_rules import (
    MAX_HEADLINE_LEN,
    MAX_BULLET_LEN,
    MAX_CHARS,
    _BULLET_LIMITS,
    V1Finding,
)

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _truncate_at_word_boundary(text: str, max_len: int) -> str:
    """Truncate *text* to at most *max_len* chars, cutting at a word boundary."""
    if len(text) <= max_len:
        return text
    truncated = text[: max_len - 1]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "\u2026"


# ── Fix functions ─────────────────────────────────────────────────────────────

def truncate_title(slide: SlideContent, max_len: int = MAX_HEADLINE_LEN) -> bool:
    """Truncate the title at a word boundary if it exceeds max_len. Returns True if changed."""
    if len(slide.title) > max_len:
        original = slide.title
        slide.title = _truncate_at_word_boundary(slide.title, max_len)
        logger.info(f"[V1 Auto-Fix] Title truncated: '{original[:50]}…' → '{slide.title[:50]}…'")
        return True
    return False


def trim_bullets(slide: SlideContent, max_count: int | None = None) -> bool:
    """Remove excess bullets. Returns True if changed."""
    if max_count is None:
        max_count = _BULLET_LIMITS.get(slide.layout)
    if max_count is None:
        return False
    if len(slide.bullets) > max_count:
        removed = len(slide.bullets) - max_count
        slide.bullets = slide.bullets[:max_count]
        logger.info(f"[V1 Auto-Fix] Removed {removed} excess bullet(s) (max {max_count} for '{slide.layout}')")
        return True
    return False


def truncate_bullet_text(slide: SlideContent, max_len: int = MAX_BULLET_LEN) -> bool:
    """Truncate each bullet's text at a word boundary. Returns True if any changed."""
    changed = False
    for i, bullet in enumerate(slide.bullets):
        if len(bullet) > max_len:
            slide.bullets[i] = _truncate_at_word_boundary(bullet, max_len)
            changed = True
    if changed:
        logger.info(f"[V1 Auto-Fix] Truncated long bullet text(s) to {max_len} chars")
    return changed


def truncate_body(slide: SlideContent) -> bool:
    """Truncate body text if total chars exceed the layout limit. Returns True if changed."""
    limit = MAX_CHARS.get(slide.layout, 300)
    total = len(slide.title) + len(slide.subtitle) + len(slide.body)
    total += sum(len(b) for b in slide.bullets)
    total += len(slide.left_column) + len(slide.right_column)

    if total <= limit:
        return False

    # Only truncate body — it's the most expendable field
    overshoot = total - limit
    if len(slide.body) > overshoot:
        new_len = len(slide.body) - overshoot
        slide.body = _truncate_at_word_boundary(slide.body, max(new_len, 20))
        logger.info(f"[V1 Auto-Fix] Body truncated to stay within {limit} char limit")
        return True
    return False


def truncate_columns(slide: SlideContent) -> bool:
    """Balance and truncate two_column content if too long. Returns True if changed."""
    if slide.layout != "two_column":
        return False

    max_col_chars = 150  # ~150 chars per column for readability
    changed = False

    if len(slide.left_column) > max_col_chars:
        slide.left_column = _truncate_at_word_boundary(slide.left_column, max_col_chars)
        changed = True
    if len(slide.right_column) > max_col_chars:
        slide.right_column = _truncate_at_word_boundary(slide.right_column, max_col_chars)
        changed = True

    if changed:
        logger.info("[V1 Auto-Fix] Truncated column content for readability")
    return changed


# ── Main entry point ──────────────────────────────────────────────────────────

def apply_v1_auto_fixes(slide: SlideContent, slide_index: int) -> SlideContent:
    """Apply all applicable auto-fixes to a V1 slide. Returns the mutated slide."""
    fixes_applied = 0
    fixes_applied += truncate_title(slide)
    fixes_applied += trim_bullets(slide)
    fixes_applied += truncate_bullet_text(slide)
    fixes_applied += truncate_columns(slide)
    fixes_applied += truncate_body(slide)

    if fixes_applied:
        logger.info(f"[V1 Auto-Fix] Slide {slide_index + 1}: {fixes_applied} fix(es) applied")
    return slide


def auto_fix_presentation(data: PresentationData) -> PresentationData:
    """Apply auto-fixes to all slides in a V1 PresentationData."""
    for i, slide in enumerate(data.slides):
        apply_v1_auto_fixes(slide, i)
    return data
