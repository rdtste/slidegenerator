"""Generate endpoint — creates PPTX from Markdown + template."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.schemas import GenerateRequest
from app.services.markdown_service import parse_markdown
from app.services.pptx_service import generate_pptx

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate")
async def generate(request: GenerateRequest):
    """Generate a PPTX file from Markdown and a selected template."""
    try:
        presentation = parse_markdown(request.markdown)
    except Exception as exc:
        logger.exception("Markdown parsing failed")
        raise HTTPException(status_code=400, detail=f"Markdown-Fehler: {exc}") from exc

    if not presentation.slides:
        raise HTTPException(status_code=400, detail="Keine Folien im Markdown gefunden")

    try:
        output_path = generate_pptx(presentation, request.template_id)
    except Exception as exc:
        logger.exception("PPTX generation failed")
        raise HTTPException(status_code=500, detail=f"PPTX-Generierung fehlgeschlagen: {exc}") from exc

    return FileResponse(
        path=str(output_path),
        filename=output_path.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
