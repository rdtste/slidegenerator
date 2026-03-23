"""Content validation service — validates LLM Markdown output before PPTX generation."""

from __future__ import annotations

import logging
import re
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ValidationIssue(BaseModel):
    """Single validation issue found"""
    slide_index: int
    severity: str  # "error", "warning"
    message: str
    suggestion: Optional[str] = None


class ContentValidationResult(BaseModel):
    """Result of content validation"""
    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    total_slides: int = 0


class MarkdownValidator:
    """Validates LLM Markdown output per PPTX Skill requirements"""

    # Design constraints from template profile
    VALID_LAYOUT_TYPES = {
        "title", "section", "content", "two_column",
        "image", "chart", "closing"
    }

    CONSTRAINTS = {
        "title": {
            "max_chars": 50,
            "max_bullets": 0,
            "requires_visual": False
        },
        "section": {
            "max_chars": 45,
            "max_bullets": 0,
            "requires_visual": False
        },
        "content": {
            "max_chars": 60,
            "max_bullets": 5,
            "max_bullet_chars": 80,
            "requires_visual": False
        },
        "two_column": {
            "max_chars": 50,
            "max_bullets": 4,
            "max_bullet_chars": 70,
            "requires_visual": False
        },
        "image": {
            "max_chars": 45,
            "max_bullets": 4,
            "max_bullet_chars": 60,
            "requires_visual": True
        },
        "chart": {
            "max_chars": 50,
            "max_bullets": 3,
            "max_bullet_chars": 70,
            "requires_visual": True
        },
        "closing": {
            "max_chars": 50,
            "max_bullets": 3,
            "max_bullet_chars": 70,
            "requires_visual": False
        }
    }

    def validate(self, markdown: str) -> ContentValidationResult:
        """
        Validate markdown content (PPTX Skill Content QA requirement).

        Markdown format:
        <!-- layout: TYPE -->
        # Title
        - Bullet 1
        - Bullet 2
        """

        issues = []
        slide_blocks = self._split_slides(markdown)

        for slide_idx, block in enumerate(slide_blocks, start=1):
            slide_issues = self._validate_slide(slide_idx, block)
            issues.extend(slide_issues)

        return ContentValidationResult(
            is_valid=len([i for i in issues if i.severity == "error"]) == 0,
            issues=issues,
            total_slides=len(slide_blocks)
        )

    def _split_slides(self, markdown: str) -> list[str]:
        """Split markdown by slide separators (--- or <!-- layout: *-->)"""
        # First try splitting by horizontal rules
        blocks = re.split(r"^\s*---\s*$", markdown, flags=re.MULTILINE)
        
        # If no splits found, try by layout markers
        if len(blocks) == 1:
            # Look for layout markers
            layout_matches = list(re.finditer(r"<!--\s*layout:\s*\w+\s*-->", markdown))
            if layout_matches:
                result = []
                for i, match in enumerate(layout_matches):
                    start = match.start()
                    end = layout_matches[i + 1].start() if i + 1 < len(layout_matches) else len(markdown)
                    result.append(markdown[start:end])
                return [b.strip() for b in result if b.strip()]
        
        return [b.strip() for b in blocks if b.strip()]

    def _validate_slide(self, slide_idx: int, block: str) -> list[ValidationIssue]:
        """Validate single slide block"""
        issues = []

        # Check 1: Extract and validate layout type
        layout_match = re.search(r"<!--\s*layout:\s*(\w+)\s*-->", block)
        if not layout_match:
            issues.append(ValidationIssue(
                slide_index=slide_idx,
                severity="error",
                message="Missing layout marker (<!-- layout: TYPE -->)",
                suggestion="Add layout type: title, content, image, chart, closing, section"
            ))
            return issues

        layout_type = layout_match.group(1).lower()

        if layout_type not in self.VALID_LAYOUT_TYPES:
            issues.append(ValidationIssue(
                slide_index=slide_idx,
                severity="error",
                message=f"Invalid layout type: {layout_type}",
                suggestion=f"Use one of: {', '.join(sorted(self.VALID_LAYOUT_TYPES))}"
            ))
            return issues

        constraints = self.CONSTRAINTS.get(layout_type, {})

        # Check 2: Validate title (first # line)
        title_match = re.search(r"^#\s+(.+)$", block, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            if "max_chars" in constraints:
                if len(title) > constraints["max_chars"]:
                    issues.append(ValidationIssue(
                        slide_index=slide_idx,
                        severity="warning",
                        message=f"Title too long: {len(title)} chars (max {constraints['max_chars']})",
                        suggestion=f"Shorten title to {constraints['max_chars']} characters or less"
                    ))
            
            # Check for special characters that might break markdown
            if re.search(r"[<>\\\"']", title):
                issues.append(ValidationIssue(
                    slide_index=slide_idx,
                    severity="warning",
                    message=f"Title contains special characters that may cause parsing issues",
                    suggestion="Remove or escape special characters: < > \\ \" '"
                ))
        else:
            if layout_type != "closing":
                issues.append(ValidationIssue(
                    slide_index=slide_idx,
                    severity="warning",
                    message="No title found (# Heading)",
                    suggestion="Add a title line: # Your Title"
                ))

        # Check 3: Validate bullets
        bullets = re.findall(r"^[-*]\s+(.+)$", block, re.MULTILINE)

        if "max_bullets" in constraints:
            if len(bullets) > constraints["max_bullets"]:
                issues.append(ValidationIssue(
                    slide_index=slide_idx,
                    severity="warning",
                    message=f"Too many bullets: {len(bullets)} (max {constraints['max_bullets']})",
                    suggestion=f"Reduce to {constraints['max_bullets']} bullets or fewer"
                ))

        if "max_bullet_chars" in constraints:
            for bullet_idx, bullet in enumerate(bullets, start=1):
                if len(bullet.strip()) > constraints["max_bullet_chars"]:
                    issues.append(ValidationIssue(
                        slide_index=slide_idx,
                        severity="warning",
                        message=f"Bullet {bullet_idx} too long: {len(bullet)} chars",
                        suggestion=f"Keep bullets under {constraints['max_bullet_chars']} characters"
                    ))

        # Check 4: Placeholder text detection (PPTX Skill requirement)
        placeholder_patterns = [
            (r"XXXX+", "XXXX repeated characters"),
            (r"Lorem\s+ipsum", "Lorem ipsum placeholder"),
            (r"this\s+(slide|page|layout|template)", "Template placeholder"),
            (r"\[PLACEHOLDER\]", "Explicit placeholder marker"),
        ]
        for pattern, description in placeholder_patterns:
            if re.search(pattern, block, re.IGNORECASE):
                issues.append(ValidationIssue(
                    slide_index=slide_idx,
                    severity="error",
                    message=f"Placeholder text detected: {description}",
                    suggestion="Replace with actual content from LLM"
                ))

        # Check 5: Visual element check (if required)
        if constraints.get("requires_visual", False):
            has_image_desc = re.search(r"!\[([^\]]+)\]", block)
            has_chart = re.search(r"```chart", block, re.IGNORECASE)
            
            if not has_image_desc and not has_chart:
                issues.append(ValidationIssue(
                    slide_index=slide_idx,
                    severity="warning",
                    message=f"Layout '{layout_type}' should have visual element (image or chart)",
                    suggestion="Add image: ![description](url) or chart: ```chart...```"
                ))

        logger.debug(f"Slide {slide_idx} ({layout_type}): validated with {len(issues)} issues")
        return issues
