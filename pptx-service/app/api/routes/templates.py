"""Template management endpoints."""

from __future__ import annotations

import logging
import shutil

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.config import settings
from app.models.schemas import TemplateInfo
from app.templates_mgmt.service import list_templates, get_template_path
from app.templates_mgmt.theme import extract_theme, extract_structure, theme_to_css, TemplateTheme
from app.templates_mgmt.profiler import extract_profile

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = (".pptx", ".potx")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.get("/templates", response_model=list[TemplateInfo])
async def get_templates():
    """List all available PowerPoint master templates."""
    return list_templates()


@router.get("/templates/{template_id}/theme")
async def get_template_theme(template_id: str):
    """Extract the visual theme from a template (colors, fonts, layouts)."""
    theme = extract_theme(template_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Template nicht gefunden")
    return {
        **theme.model_dump(),
        "css": theme_to_css(theme),
    }


@router.get("/templates/{template_id}/structure")
async def get_template_structure(template_id: str):
    """Extract raw layout structure for AI-based analysis."""
    structure = extract_structure(template_id)
    if not structure:
        raise HTTPException(status_code=404, detail="Template nicht gefunden")
    return structure.model_dump()


@router.post("/templates", response_model=TemplateInfo)
async def upload_template(file: UploadFile = File(...)):
    """Upload a new PowerPoint master template."""
    if not file.filename or not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Nur .pptx- oder .potx-Dateien erlaubt")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Datei zu groß (max 50 MB)")

    templates_dir = settings.templates_dir
    templates_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(
        c if c.isalnum() or c in "._- " else "_"
        for c in file.filename
    )
    dest = templates_dir / safe_name
    dest.write_bytes(content)

    logger.info(f"Template uploaded: {safe_name}")

    updated = list_templates()
    template_id = dest.stem
    match = next((t for t in updated if t.id == template_id), None)
    if not match:
        raise HTTPException(status_code=500, detail="Template konnte nicht gelesen werden")
    return match


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete a template by ID."""
    path = get_template_path(template_id)
    if not path:
        raise HTTPException(status_code=404, detail="Template nicht gefunden")

    path.unlink()
    logger.info(f"Template deleted: {template_id}")
    return {"deleted": True}


@router.post("/templates/{template_id}/learn")
async def learn_template(template_id: str):
    """Deep-learn a template: extract comprehensive visual profile for generation alignment.

    Returns a rich TemplateProfile with color DNA, typography DNA,
    full layout catalog, chart/image guidelines, and supported layout types.
    """
    profile = extract_profile(template_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Template nicht gefunden")
    return profile.model_dump()
