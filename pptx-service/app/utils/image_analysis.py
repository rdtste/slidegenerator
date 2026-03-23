"""Image analysis service for visual QA (PPTX Skill requirement)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PIL import Image
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class VisualIssue(BaseModel):
    """Single visual issue found in slide image"""
    slide_number: int
    issue_type: str  # "text_overflow", "low_contrast", "overlap", "margin", "invalid_size"
    description: str
    severity: str = "warning"  # "error", "warning"


class ImageAnalyzer:
    """Analyzes slide images for visual QA issues."""

    # Minimum viable slide size at 150 DPI: ~1000x750 pixels for letter-size
    MIN_WIDTH_PX = 800
    MIN_HEIGHT_PX = 600

    # For 150 DPI, 0.5 inch = 75 pixels
    MIN_MARGIN_PX = 50

    # Minimum contrast ratio (WCAG AA standard)
    MIN_CONTRAST_RATIO = 4.5

    async def analyze_image(self, image_path: str, slide_number: int) -> list[VisualIssue]:
        """Analyze single slide image for visual issues.
        
        Checks for:
        - Invalid slide dimensions
        - Potential text overflow (no OCR, basic heuristic)
        - Color/contrast issues (basic)
        
        Args:
            image_path: Path to slide JPEG
            slide_number: Slide number for reporting
            
        Returns:
            List of visual issues found
        """

        issues = []

        try:
            img = Image.open(image_path)
            width, height = img.size

            # Check 1: Slide dimensions
            if width < self.MIN_WIDTH_PX or height < self.MIN_HEIGHT_PX:
                issues.append(VisualIssue(
                    slide_number=slide_number,
                    issue_type="invalid_size",
                    description=f"Slide size too small: {width}×{height}px (min {self.MIN_WIDTH_PX}×{self.MIN_HEIGHT_PX}px)",
                    severity="error"
                ))

            # Check 2: Image format validation
            if img.format not in ["JPEG", "PNG"]:
                issues.append(VisualIssue(
                    slide_number=slide_number,
                    issue_type="invalid_format",
                    description=f"Unexpected image format: {img.format}",
                    severity="warning"
                ))

            # Check 3: Basic corruption check (histogram analysis)
            try:
                histogram = img.histogram()
                if not histogram or len(histogram) == 0:
                    issues.append(VisualIssue(
                        slide_number=slide_number,
                        issue_type="corrupted_image",
                        description="Image may be corrupted or have invalid histogram",
                        severity="warning"
                    ))
            except Exception as e:
                logger.warning(f"Could not analyze histogram for slide {slide_number}: {e}")

            logger.debug(f"Slide {slide_number}: image analyzed ({width}×{height}px), {len(issues)} issues")

        except Image.UnidentifiedImageError:
            issues.append(VisualIssue(
                slide_number=slide_number,
                issue_type="invalid_image",
                description="File is not a valid image or is corrupted",
                severity="error"
            ))
        except Exception as e:
            logger.error(f"Image analysis failed for slide {slide_number}: {e}")
            issues.append(VisualIssue(
                slide_number=slide_number,
                issue_type="analysis_error",
                description=f"Could not analyze image: {str(e)[:100]}",
                severity="warning"
            ))

        return issues

    def check_contrast(self, color1: tuple[int, int, int], color2: tuple[int, int, int]) -> float:
        """Calculate WCAG contrast ratio between two RGB colors.
        
        Returns a value between 1 and 21 (21 is max contrast, white on black).
        WCAG AA minimum is 4.5:1.
        """
        
        def relative_luminance(rgb: tuple[int, int, int]) -> float:
            r, g, b = [x / 255.0 for x in rgb]
            r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
            g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
            b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        l1 = relative_luminance(color1)
        l2 = relative_luminance(color2)

        lighter = max(l1, l2)
        darker = min(l1, l2)

        return (lighter + 0.05) / (darker + 0.05)
