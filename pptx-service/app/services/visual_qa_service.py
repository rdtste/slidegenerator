"""Visual QA service — converts PPTX to images and inspects for issues (PPTX Skill)."""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.utils.image_analysis import ImageAnalyzer, VisualIssue
from app.utils.soffice_wrapper import LibreOfficeConverter, PdftoPpmConverter

logger = logging.getLogger(__name__)


class VisualQAReport(BaseModel):
    """Report of visual QA results"""
    total_slides: int = 0
    issues: list[VisualIssue] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    is_valid: bool = True
    error: Optional[str] = None


class VisualQAService:
    """Runs visual QA pipeline: PPTX → PDF → JPEG → Analyze.
    
    PPTX Skill requirement:
    1. Convert PPTX to PDF via LibreOffice
    2. Convert PDF to JPEG images (150 DPI) via pdftoppm
    3. Inspect each image for visual issues
    """

    def __init__(
        self,
        soffice_path: str = "soffice",
        pdftoppm_path: str = "pdftoppm"
    ):
        self.converter = LibreOfficeConverter(soffice_path)
        self.pdf_to_jpeg = PdftoPpmConverter(pdftoppm_path)
        self.analyzer = ImageAnalyzer()

    def run_visual_qa_sync(self, pptx_path: str) -> VisualQAReport:
        """Synchronous wrapper for run_visual_qa (for use in threads).
        
        Args:
            pptx_path: Path to generated PPTX file
            
        Returns:
            VisualQAReport with issues, image paths, and validity status
        """
        import asyncio
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.run_visual_qa(pptx_path))
        except RuntimeError:
            # Event loop already exists in thread
            return asyncio.run(self.run_visual_qa(pptx_path))

    async def run_visual_qa(self, pptx_path: str) -> VisualQAReport:
        """Run full visual QA pipeline.
        
        Args:
            pptx_path: Path to generated PPTX file
            
        Returns:
            VisualQAReport with issues, image paths, and validity status
        """

        issues = []
        image_paths = []

        try:
            # Step 1: PPTX → PDF
            logger.info(f"[Visual QA] Converting PPTX to PDF: {pptx_path}")
            pdf_path = await self.converter.pptx_to_pdf(pptx_path)

            # Step 2: PDF → JPEG (150 DPI per PPTX Skill spec)
            logger.info(f"[Visual QA] Converting PDF to JPEG images (150 DPI)...")
            image_paths = await self.pdf_to_jpeg.pdf_to_jpeg(pdf_path, dpi=150)

            # Step 3: Analyze each JPEG
            logger.info(f"[Visual QA] Analyzing {len(image_paths)} slide images...")
            for slide_num, image_path in enumerate(image_paths, start=1):
                slide_issues = await self.analyzer.analyze_image(image_path, slide_num)
                issues.extend(slide_issues)

            # Summary
            is_valid = all(i.severity != "error" for i in issues)
            error_count = len([i for i in issues if i.severity == "error"])
            warning_count = len([i for i in issues if i.severity == "warning"])

            logger.info(
                f"[Visual QA] Complete: {len(image_paths)} slides, "
                f"{error_count} errors, {warning_count} warnings"
            )

            return VisualQAReport(
                total_slides=len(image_paths),
                issues=issues,
                image_paths=image_paths,
                is_valid=is_valid
            )

        except Exception as e:
            logger.error(f"[Visual QA] Pipeline failed: {e}")
            return VisualQAReport(
                total_slides=0,
                issues=issues,
                image_paths=image_paths,
                is_valid=False,
                error=str(e)
            )
