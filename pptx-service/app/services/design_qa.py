"""Design QA service — orchestrates design validation pipeline (P1).

PPTX Skill requirement (Post-Generation Design Inspection):
1. Extract slide metadata from generated PPTX
2. Run design system validation against each slide
3. Correlate with visual QA findings
4. Generate comprehensive design report
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.services.design_validator import DesignValidator, DesignValidationResult
from app.services.template_validator import TemplateValidator

logger = logging.getLogger(__name__)


class DesignQAIssue(BaseModel):
    """Design QA issue from automation + visual inspection"""
    slide_number: int
    category: str  # "color", "typography", "layout", "contrast", "visual", "structure"
    severity: str  # "error", "warning", "info"
    title: str
    description: str
    remediation: Optional[str] = None
    linked_visual_qa: bool = False  # Issue also detected by visual QA


class DesignQAReport(BaseModel):
    """Comprehensive design QA report"""
    pptx_path: Path
    template_id: str
    total_slides: int
    issues: list[DesignQAIssue] = Field(default_factory=list)
    design_score: float = 0.0  # 0-100, 100 = perfect
    color_compliance: float = 0.0
    typography_compliance: float = 0.0
    layout_variety: float = 0.0
    is_valid: bool = True
    error: Optional[str] = None
    
    @property
    def error_count(self) -> int:
        return len([i for i in self.issues if i.severity == "error"])
    
    @property
    def warning_count(self) -> int:
        return len([i for i in self.issues if i.severity == "warning"])


class DesignQAService:
    """Orchestrates comprehensive design QA after PPTX generation.
    
    P1 Enhancement: Post-generation design inspection combining:
    - Design system rule validation
    - Template compliance checking
    - Visual element analysis
    - Color & typography verification
    """

    def __init__(self, templates_dir: str = "/app/templates"):
        self.design_validator = DesignValidator()
        self.template_validator = TemplateValidator(templates_dir)
        logger.info("[Design QA] Service initialized")

    async def run_design_qa(
        self,
        pptx_path: str,
        template_id: str,
        slides_data: Optional[list[dict]] = None
    ) -> DesignQAReport:
        """Run comprehensive design QA pipeline.
        
        Args:
            pptx_path: Path to generated PPTX file
            template_id: Template used for generation
            slides_data: Optional slide metadata for correlation
            
        Returns:
            DesignQAReport with issues, compliance scores, and recommendations
        """
        pptx_path_obj = Path(pptx_path)
        all_issues = []
        
        try:
            # Step 1: Template Pre-flight Validation
            logger.info(f"[Design QA] Template validation for {template_id}...")
            template_result = self.template_validator.validate_template(template_id)
            
            if not template_result.is_valid:
                logger.warning(f"[Design QA] Template validation failed: {len(template_result.issues)} issues")
                # Convert template validation issues to design QA format
                for issue in template_result.issues:
                    if issue.severity == "error":
                        all_issues.append(DesignQAIssue(
                            slide_number=0,  # Template-level
                            category="structure",
                            severity="error",
                            title="Template Error",
                            description=issue.message,
                            remediation=issue.details
                        ))

            # Step 2: Design System Validation
            logger.info(f"[Design QA] Design system validation...")
            if slides_data:
                for slide_num, slide in enumerate(slides_data, start=1):
                    validation_result = self.design_validator.validate(slide, slide_num)
                    
                    # Convert design validation issues to QA format
                    for issue in validation_result.issues:
                        all_issues.append(DesignQAIssue(
                            slide_number=issue.slide_number,
                            category=issue.issue_type,
                            severity=issue.severity,
                            title=f"{issue.issue_type.title()} Issue",
                            description=issue.description,
                            remediation=issue.suggested_fix
                        ))
            
            # Step 3: Calculate compliance scores
            color_compliance = self._calculate_color_compliance(all_issues)
            typography_compliance = self._calculate_typography_compliance(all_issues)
            layout_variety = self._calculate_layout_variety(slides_data or [])
            
            # Step 4: Overall design score
            design_score = (color_compliance + typography_compliance + layout_variety) / 3.0
            
            is_valid = all(i.severity != "error" for i in all_issues)
            
            logger.info(
                f"[Design QA] Complete: {len(all_issues)} issues, "
                f"design_score={design_score:.1f}, is_valid={is_valid}"
            )
            
            return DesignQAReport(
                pptx_path=pptx_path_obj,
                template_id=template_id,
                total_slides=len(slides_data) if slides_data else 0,
                issues=all_issues,
                design_score=design_score,
                color_compliance=color_compliance,
                typography_compliance=typography_compliance,
                layout_variety=layout_variety,
                is_valid=is_valid
            )
            
        except Exception as e:
            logger.error(f"[Design QA] Pipeline failed: {e}")
            return DesignQAReport(
                pptx_path=pptx_path_obj,
                template_id=template_id,
                total_slides=0,
                issues=all_issues,
                is_valid=False,
                error=str(e)
            )

    def _calculate_color_compliance(self, issues: list[DesignQAIssue]) -> float:
        """Calculate color compliance score (0-100)."""
        color_issues = [i for i in issues if i.category == "color"]
        if not color_issues:
            return 100.0
        
        error_count = len([i for i in color_issues if i.severity == "error"])
        warning_count = len([i for i in color_issues if i.severity == "warning"])
        
        # Score: 100 - (errors * 10) - (warnings * 2)
        score = max(0, 100 - (error_count * 10) - (warning_count * 2))
        return min(100, score)

    def _calculate_typography_compliance(self, issues: list[DesignQAIssue]) -> float:
        """Calculate typography compliance score (0-100)."""
        typography_issues = [i for i in issues if i.category == "typography"]
        if not typography_issues:
            return 100.0
        
        error_count = len([i for i in typography_issues if i.severity == "error"])
        warning_count = len([i for i in typography_issues if i.severity == "warning"])
        
        score = max(0, 100 - (error_count * 10) - (warning_count * 3))
        return min(100, score)

    def _calculate_layout_variety(self, slides_data: list[dict]) -> float:
        """Calculate layout variety score (0-100)."""
        if not slides_data:
            return 0.0
        
        unique_layouts = len(set(slide.get("layout_type") for slide in slides_data if "layout_type" in slide))
        ideal_layouts = max(3, len(slides_data) // 2)  # At least 3, or 1 per 2 slides
        
        # Score: min(100, (unique_layouts / ideal_layouts) * 100)
        score = min(100, (unique_layouts / ideal_layouts) * 100) if ideal_layouts > 0 else 50.0
        return score

    def run_design_qa_sync(
        self,
        pptx_path: str,
        template_id: str,
        slides_data: Optional[list[dict]] = None
    ) -> DesignQAReport:
        """Synchronous wrapper for run_design_qa (for use in threads).
        
        Args:
            pptx_path: Path to generated PPTX
            template_id: Template ID
            slides_data: Optional slide metadata
            
        Returns:
            DesignQAReport
        """
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.run_design_qa(pptx_path, template_id, slides_data))
        except RuntimeError:
            return asyncio.run(self.run_design_qa(pptx_path, template_id, slides_data))
