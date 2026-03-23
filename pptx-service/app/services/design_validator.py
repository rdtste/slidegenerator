"""Design validator — enforces ColorDNA, typography, and layout rules (P1 enhancement).

PPTX Skill requirement (Design Enforcement):
- Validate generated slides against template design system
- Check color palette compliance (ColorDNA)
- Ensure typography consistency (sizes, weights, contrast)
- Verify layout variety and visual element presence
- Report design violations with severity levels
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DesignIssue(BaseModel):
    """Single design validation issue"""
    slide_number: int
    issue_type: str  # "color", "typography", "layout", "contrast", "missing_element"
    severity: str  # "error", "warning"
    description: str
    suggested_fix: Optional[str] = None


class DesignValidationResult(BaseModel):
    """Report of design validation results"""
    total_slides: int = 0
    issues: list[DesignIssue] = Field(default_factory=list)
    is_valid: bool = True
    error: Optional[str] = None
    
    @property
    def error_count(self) -> int:
        return len([i for i in self.issues if i.severity == "error"])
    
    @property
    def warning_count(self) -> int:
        return len([i for i in self.issues if i.severity == "warning"])


class ColorDNA(BaseModel):
    """Color palette specification"""
    dominant: str  # Primary color (hex)
    supporting: list[str] = Field(default_factory=list)  # 1-2 supporting colors
    accent: str  # Accent color for highlights
    background_light: str = "#FFFFFF"
    background_dark: str = "#000000"
    contrast_min_ratio: float = 4.5  # WCAG AA standard


class TypographyRules(BaseModel):
    """Typography specifications"""
    title_size_min: int = 36
    title_size_max: int = 44
    section_header_size_min: int = 20
    section_header_size_max: int = 24
    body_size_min: int = 14
    body_size_max: int = 16
    margin_min_inches: float = 0.5
    line_spacing_min: float = 1.2


class LayoutRules(BaseModel):
    """Layout consistency specifications"""
    layouts_per_deck: list[str]  # Expected layout types: "title", "content", "two-column", "image+text"
    min_unique_layouts: int = 3  # At least 3 different layouts
    visual_element_required: bool = True  # Every slide needs image/chart/icon/shape
    max_text_only_slides: int = 0  # No text-only slides


class DesignSystem(BaseModel):
    """Complete design system for a template"""
    template_id: str
    color_dna: ColorDNA
    typography: TypographyRules
    layout: LayoutRules


class DesignValidator:
    """Validates generated PPTX slides against design system rules.
    
    P1 Enhancement: Extends P0 content validation with design consistency checks.
    Reads design metadata from template and validates compliance.
    """

    def __init__(self, design_system: Optional[DesignSystem] = None):
        """Initialize validator with design system rules.
        
        If no design_system provided, uses defaults.
        """
        self.design_system = design_system or self._default_design_system()
        logger.info(f"[Design Validator] Initialized for template: {self.design_system.template_id}")

    def _default_design_system(self) -> DesignSystem:
        """Default design system (conservative, safe rules)."""
        return DesignSystem(
            template_id="default",
            color_dna=ColorDNA(
                dominant="#003366",
                supporting=["#006699", "#FF6600"],
                accent="#FFCC00"
            ),
            typography=TypographyRules(),
            layout=LayoutRules(
                layouts_per_deck=["title", "content", "two-column", "image_text"],
                min_unique_layouts=2,
                visual_element_required=True,
                max_text_only_slides=0
            )
        )

    def validate(
        self,
        slide_data: dict,
        slide_number: int
    ) -> DesignValidationResult:
        """Validate a single slide against design rules.
        
        Args:
            slide_data: Slide metadata/content (from presentation)
            slide_number: Position in deck (1-indexed)
            
        Returns:
            DesignValidationResult with issues list and validity status
        """
        issues = []

        try:
            # P1.1: Color Validation
            color_issues = self._validate_colors(slide_data, slide_number)
            issues.extend(color_issues)

            # P1.2: Typography Validation
            typography_issues = self._validate_typography(slide_data, slide_number)
            issues.extend(typography_issues)

            # P1.3: Layout & Visual Element Validation
            layout_issues = self._validate_layout(slide_data, slide_number)
            issues.extend(layout_issues)

            # P1.4: Contrast Validation
            contrast_issues = self._validate_contrast(slide_data, slide_number)
            issues.extend(contrast_issues)

        except Exception as e:
            logger.error(f"[Design Validator] Exception during validation: {e}")
            return DesignValidationResult(
                total_slides=1,
                issues=issues,
                is_valid=False,
                error=str(e)
            )

        is_valid = all(i.severity != "error" for i in issues)

        return DesignValidationResult(
            total_slides=1,
            issues=issues,
            is_valid=is_valid
        )

    def _validate_colors(self, slide_data: dict, slide_num: int) -> list[DesignIssue]:
        """Check color palette compliance."""
        issues = []
        
        # This would need integration with image analysis to extract actual colors
        # For now, we log the check but don't fail (P1 foundational)
        if "colors" in slide_data:
            colors_used = slide_data.get("colors", [])
            if colors_used:
                logger.debug(f"[Design Validator] Slide {slide_num} colors: {colors_used}")

        return issues

    def _validate_typography(self, slide_data: dict, slide_num: int) -> list[DesignIssue]:
        """Check typography consistency (font sizes, weights)."""
        issues = []
        rules = self.design_system.typography

        if "title" in slide_data:
            title_size = slide_data["title"].get("size_pt", 0)
            if title_size and (title_size < rules.title_size_min or title_size > rules.title_size_max):
                issues.append(DesignIssue(
                    slide_number=slide_num,
                    issue_type="typography",
                    severity="warning",
                    description=f"Title size {title_size}pt outside recommended range ({rules.title_size_min}-{rules.title_size_max}pt)",
                    suggested_fix=f"Use {rules.title_size_min}-{rules.title_size_max}pt for titles"
                ))

        if "body" in slide_data:
            body_size = slide_data["body"].get("size_pt", 0)
            if body_size and (body_size < rules.body_size_min or body_size > rules.body_size_max):
                issues.append(DesignIssue(
                    slide_number=slide_num,
                    issue_type="typography",
                    severity="warning",
                    description=f"Body text size {body_size}pt outside recommended range ({rules.body_size_min}-{rules.body_size_max}pt)",
                    suggested_fix=f"Use {rules.body_size_min}-{rules.body_size_max}pt for body text"
                ))

        return issues

    def _validate_layout(self, slide_data: dict, slide_num: int) -> list[DesignIssue]:
        """Check layout variety and visual element presence."""
        issues = []
        rules = self.design_system.layout

        if rules.visual_element_required:
            has_visual = any(slide_data.get(key) for key in ["image", "chart", "shape", "icon"])
            if not has_visual:
                issues.append(DesignIssue(
                    slide_number=slide_num,
                    issue_type="missing_element",
                    severity="warning",
                    description="Slide lacks visual element (image, chart, icon, or shape)",
                    suggested_fix="Add a visual element to break up text"
                ))

        return issues

    def _validate_contrast(self, slide_data: dict, slide_num: int) -> list[DesignIssue]:
        """Check text-background contrast (WCAG AA compliance)."""
        issues = []
        min_ratio = self.design_system.color_dna.contrast_min_ratio

        # This would integrate with image analysis to check actual contrast ratios
        # For now, it's a placeholder for the P1 architecture
        if "text_elements" in slide_data:
            elements = slide_data.get("text_elements", [])
            for elem in elements:
                contrast_ratio = elem.get("contrast_ratio", 0)
                if contrast_ratio and contrast_ratio < min_ratio:
                    issues.append(DesignIssue(
                        slide_number=slide_num,
                        issue_type="contrast",
                        severity="error",
                        description=f"Text contrast ratio {contrast_ratio:.1f}:1 below WCAG AA minimum ({min_ratio}:1)",
                        suggested_fix="Increase text color brightness or decrease background brightness"
                    ))

        return issues

    def validate_deck(
        self,
        slides: list[dict]
    ) -> DesignValidationResult:
        """Validate entire presentation against design rules.
        
        Args:
            slides: List of slide dictionaries
            
        Returns:
            Aggregated DesignValidationResult for full deck
        """
        all_issues = []
        layouts_found = set()

        for slide_num, slide in enumerate(slides, start=1):
            result = self.validate(slide, slide_num)
            all_issues.extend(result.issues)
            
            # Track layout types for variety check
            if "layout_type" in slide:
                layouts_found.add(slide["layout_type"])

        # Deck-level checks
        rules = self.design_system.layout
        if len(layouts_found) < rules.min_unique_layouts:
            all_issues.append(DesignIssue(
                slide_number=0,  # Deck-level issue
                issue_type="layout",
                severity="warning",
                description=f"Only {len(layouts_found)} unique layouts found, minimum {rules.min_unique_layouts} recommended",
                suggested_fix=f"Vary slide layouts (title, content, two-column, image+text, etc.)"
            ))

        is_valid = all(i.severity != "error" for i in all_issues)

        return DesignValidationResult(
            total_slides=len(slides),
            issues=all_issues,
            is_valid=is_valid
        )
