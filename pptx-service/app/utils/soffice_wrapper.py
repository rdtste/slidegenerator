"""LibreOffice and Poppler CLI wrappers for PPTX→PDF→JPEG conversion (PPTX Skill)."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class LibreOfficeConverter:
    """Wrapper for LibreOffice CLI for PPTX→PDF conversion.
    
    PPTX Skill requirement:
    python scripts/office/soffice.py --headless --convert-to pdf output.pptx
    """

    def __init__(self, soffice_path: str = "soffice"):
        self.soffice_path = soffice_path

    async def pptx_to_pdf(self, pptx_path: str, output_dir: str | None = None) -> str:
        """Convert PPTX to PDF using LibreOffice headless mode.
        
        Args:
            pptx_path: Path to .pptx file
            output_dir: Directory for PDF output (defaults to pptx directory)
            
        Returns:
            Path to generated PDF file
            
        Raises:
            RuntimeError: If conversion fails
        """
        
        if output_dir is None:
            output_dir = os.path.dirname(pptx_path) or "."

        cmd = [
            self.soffice_path,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", output_dir,
            pptx_path
        ]

        try:
            logger.info(f"Converting PPTX to PDF: {pptx_path}")
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                logger.error(f"LibreOffice error: {result.stderr}")
                raise RuntimeError(f"PDF conversion failed: {result.stderr}")

            # Output is {filename}.pdf in output_dir
            base_name = Path(pptx_path).stem
            pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

            if not os.path.exists(pdf_path):
                raise RuntimeError(f"PDF not created at expected path: {pdf_path}")

            logger.info(f"✓ PDF generated: {pdf_path}")
            return pdf_path

        except subprocess.TimeoutExpired:
            logger.error("LibreOffice conversion timeout (120s)")
            raise RuntimeError("PDF conversion timeout after 120 seconds")
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            raise RuntimeError(f"PDF conversion failed: {str(e)}")


class PdftoPpmConverter:
    """Wrapper for pdftoppm (Poppler) for PDF→JPEG conversion.
    
    PPTX Skill requirement:
    pdftoppm -jpeg -r 150 output.pdf slide
    """

    def __init__(self, pdftoppm_path: str = "pdftoppm"):
        self.pdftoppm_path = pdftoppm_path

    async def pdf_to_jpeg(
        self,
        pdf_path: str,
        output_prefix: str | None = None,
        dpi: int = 150
    ) -> list[str]:
        """Convert PDF to JPEG images using pdftoppm.
        
        Args:
            pdf_path: Path to PDF file
            output_prefix: Prefix for output files (defaults to pdf name in same dir)
            dpi: DPI for JPEG conversion (default 150)
            
        Returns:
            List of paths to generated JPEG files (slide-01.jpg, slide-02.jpg, etc)
            
        Raises:
            RuntimeError: If conversion fails
        """

        if output_prefix is None:
            base_dir = os.path.dirname(pdf_path) or "."
            base_name = Path(pdf_path).stem
            output_prefix = os.path.join(base_dir, base_name)

        cmd = [
            self.pdftoppm_path,
            "-jpeg",
            "-r", str(dpi),
            pdf_path,
            output_prefix
        ]

        try:
            logger.info(f"Converting PDF to JPEG images: {pdf_path} ({dpi} DPI)")
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes for large PDFs
            )

            if result.returncode != 0:
                logger.error(f"pdftoppm error: {result.stderr}")
                raise RuntimeError(f"JPEG conversion failed: {result.stderr}")

            # Find generated JPEGs (slide-01.jpg, slide-02.jpg, etc)
            base_dir = os.path.dirname(output_prefix) or "."
            base_name = Path(output_prefix).name

            jpeg_files = sorted([
                os.path.join(base_dir, f)
                for f in os.listdir(base_dir)
                if f.startswith(base_name) and f.endswith('.jpg')
            ])

            if not jpeg_files:
                raise RuntimeError(f"No JPEG files created from {pdf_path}")

            logger.info(f"✓ Generated {len(jpeg_files)} JPEG images")
            return jpeg_files

        except subprocess.TimeoutExpired:
            logger.error("PDF to JPEG conversion timeout (300s)")
            raise RuntimeError("JPEG conversion timeout after 300 seconds")
        except FileNotFoundError:
            logger.error(f"pdftoppm not found at {self.pdftoppm_path}")
            raise RuntimeError(
                f"pdftoppm not installed or not found at {self.pdftoppm_path}. "
                "Install with: apt-get install poppler-utils"
            )
        except Exception as e:
            logger.error(f"JPEG conversion failed: {e}")
            raise RuntimeError(f"JPEG conversion failed: {str(e)}")
