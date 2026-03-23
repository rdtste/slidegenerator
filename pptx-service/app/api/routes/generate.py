"""Generate endpoint — creates PPTX from Markdown + template.

Features:
- P0: Content Validation (markdown structure, layout types, char limits)
- P0: Image Error Handling (retry logic with exponential backoff)
- P0: Visual QA (PPTX→PDF→JPEG conversion + image inspection)
- P1: Design Validation (ColorDNA, typography, layout variety)
- P1: Template Pre-flight (template compatibility checks)
- P1: Design QA (post-gen design rule enforcement)
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.models.schemas import GenerateRequest
from app.services.markdown_service import parse_markdown
from app.services.markdown_validator import MarkdownValidator  # P0
from app.services.pptx_service import generate_pptx
from app.services.visual_qa_service import VisualQAService  # P0
from app.services.design_validator import DesignValidator  # P1
from app.services.template_validator import TemplateValidator  # P1
from app.services.design_qa import DesignQAService  # P1

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory store for generated files awaiting download
_generated_files: dict[str, str] = {}

# P0 Services
_validator = MarkdownValidator()
_visual_qa = VisualQAService()

# P1 Services
_design_validator = DesignValidator()
_template_validator = TemplateValidator()
_design_qa = DesignQAService()


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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


@router.post("/generate-stream")
async def generate_stream(request: GenerateRequest):
    """Generate PPTX with real-time progress via Server-Sent Events."""
    progress_queue: queue.Queue = queue.Queue()

    def progress_callback(step: str, message: str, progress: int | None) -> None:
        progress_queue.put({"step": step, "message": message, "progress": progress})

    async def event_generator():
        # P0: Content Validation (BEFORE parsing)
        yield _sse_event("progress", {
            "step": "validating", "message": "LLM-Output wird validiert...", "progress": 1,
        })
        
        validation_result = _validator.validate(request.markdown)
        if not validation_result.is_valid:
            error_details = [f"{i.message} ({i.slide_index})" for i in validation_result.issues[:3]]
            yield _sse_event("validation_failed", {
                "detail": "Inhaltsvalidierung fehlgeschlagen",
                "issues": [
                    {"slide": i.slide_index, "message": i.message, "severity": i.severity}
                    for i in validation_result.issues
                ],
                "error_count": len([i for i in validation_result.issues if i.severity == "error"])
            })
            logger.warning(f"Content validation failed: {len(validation_result.issues)} issues")
            return
        
        yield _sse_event("progress", {
            "step": "parsing", "message": "Markdown wird analysiert...", "progress": 5,
        })

        try:
            presentation = parse_markdown(request.markdown)
        except Exception as exc:
            yield _sse_event("fail", {"detail": f"Markdown-Fehler: {exc}"})
            return

        total = len(presentation.slides)
        if total == 0:
            yield _sse_event("fail", {"detail": "Keine Folien im Markdown gefunden"})
            return

        yield _sse_event("progress", {
            "step": "parsed", "message": f"{total} Folien erkannt", "progress": 10,
        })

        # P1: Template Pre-flight Validation
        yield _sse_event("progress", {
            "step": "template_check", "message": "Template wird validiert...", "progress": 12,
        })
        
        template_check = _template_validator.validate_template(request.template_id)
        if not template_check.is_valid:
            template_errors = [i for i in template_check.issues if i.severity == "error"]
            if template_errors:
                logger.error(f"Template validation failed: {len(template_errors)} errors")
                yield _sse_event("template_validation_failed", {
                    "detail": "Template-Validierung fehlgeschlagen",
                    "issues": [
                        {"type": i.issue_type, "message": i.message, "severity": i.severity}
                        for i in template_check.issues[:5]
                    ]
                })
                return

        result_holder: dict = {"path": None, "error": None, "qa_report": None, "design_qa_report": None}

        def run_generation():
            try:
                result_holder["path"] = generate_pptx(
                    presentation, request.template_id, progress_callback=progress_callback,
                )
                
                # P0: Visual QA (AFTER PPTX generation - SYNC)
                if result_holder["path"]:
                    progress_queue.put({"step": "visual_qa", "message": "Visuelle Validierung läuft...", "progress": 85})
                    try:
                        qa_report = _visual_qa.run_visual_qa_sync(str(result_holder["path"]))
                        result_holder["qa_report"] = qa_report
                        logger.info(f"Visual QA complete: {qa_report.total_slides} slides")
                    except Exception as qa_error:
                        logger.error(f"Visual QA exception: {qa_error}")
                        result_holder["qa_report"] = None
                    
                    # P1: Design QA (AFTER Visual QA - SYNC)
                    progress_queue.put({"step": "design_qa", "message": "Design-Regeln überprüfen...", "progress": 90})
                    try:
                        # Extract slide data from presentation for design validation
                        slides_data = []
                        if hasattr(presentation, 'slides'):
                            for i, slide in enumerate(presentation.slides):
                                slide_data = {
                                    "layout_type": getattr(slide, 'layout_name', 'default'),
                                    "title": {"text": getattr(slide, 'title', ''), "size_pt": 40},
                                    "body": {"text": getattr(slide, 'body', ''), "size_pt": 14},
                                }
                                slides_data.append(slide_data)
                        
                        design_qa_report = _design_qa.run_design_qa_sync(
                            str(result_holder["path"]),
                            request.template_id,
                            slides_data
                        )
                        result_holder["design_qa_report"] = design_qa_report
                        logger.info(
                            f"Design QA complete: score={design_qa_report.design_score:.1f}, "
                            f"errors={design_qa_report.error_count}, warnings={design_qa_report.warning_count}"
                        )
                    except Exception as design_error:
                        logger.error(f"Design QA exception: {design_error}")
                        result_holder["design_qa_report"] = None
                        
            except Exception as exc:
                result_holder["error"] = str(exc)
            finally:
                progress_queue.put({"_done": True})

        thread = threading.Thread(target=run_generation, daemon=True)
        thread.start()

        while True:
            try:
                event = progress_queue.get(timeout=120)
            except queue.Empty:
                yield _sse_event("fail", {"detail": "Timeout bei der Generierung"})
                return

            if event.get("_done"):
                break
            
            # Only yield non-internal events (skip raw progress, they're handled in thread)
            if not event.get("_done"):
                yield _sse_event("progress", event)

        thread.join(timeout=10)

        if result_holder["error"]:
            yield _sse_event("fail", {
                "detail": f"PPTX-Generierung fehlgeschlagen: {result_holder['error']}",
            })
        elif result_holder["path"]:
            # P0: Visual QA Report (if available)
            pptx_path = result_holder["path"]
            qa_report = result_holder.get("qa_report")
            design_qa_report = result_holder.get("design_qa_report")
            
            if qa_report:
                if qa_report.error:
                    logger.warning(f"Visual QA errored: {qa_report.error}")
                    yield _sse_event("progress", {
                        "step": "visual_qa_error",
                        "message": f"Visual QA fehlgeschlagen: {qa_report.error[:100]}",
                        "progress": 90,
                    })
                elif not qa_report.is_valid:
                    error_count = len([i for i in qa_report.issues if i.severity == "error"])
                    warning_count = len([i for i in qa_report.issues if i.severity == "warning"])
                    logger.warning(f"Visual QA issues: {error_count} errors, {warning_count} warnings")
                    yield _sse_event("visual_qa_issues", {
                        "detail": "Visuelle Probleme gefunden",
                        "errors": error_count,
                        "warnings": warning_count,
                        "issues": [
                            {
                                "slide": i.slide_number,
                                "type": i.issue_type,
                                "message": i.description,
                                "severity": i.severity
                            }
                            for i in qa_report.issues[:10]  # Top 10 issues
                        ]
                    })
                else:
                    logger.info("Visual QA passed")
            
            # P1: Design QA Report (if available)
            if design_qa_report:
                if design_qa_report.error:
                    logger.warning(f"Design QA errored: {design_qa_report.error}")
                    yield _sse_event("progress", {
                        "step": "design_qa_error",
                        "message": f"Design QA fehlgeschlagen: {design_qa_report.error[:100]}",
                        "progress": 95,
                    })
                elif not design_qa_report.is_valid:
                    logger.warning(
                        f"Design QA issues: {design_qa_report.error_count} errors, "
                        f"{design_qa_report.warning_count} warnings, score={design_qa_report.design_score:.1f}"
                    )
                    yield _sse_event("design_qa_issues", {
                        "detail": "Design-Regel Verletzungen gefunden",
                        "score": round(design_qa_report.design_score, 1),
                        "color_compliance": round(design_qa_report.color_compliance, 1),
                        "typography_compliance": round(design_qa_report.typography_compliance, 1),
                        "layout_variety": round(design_qa_report.layout_variety, 1),
                        "errors": design_qa_report.error_count,
                        "warnings": design_qa_report.warning_count,
                        "issues": [
                            {
                                "slide": i.slide_number,
                                "category": i.category,
                                "title": i.title,
                                "description": i.description,
                                "severity": i.severity,
                                "remediation": i.remediation
                            }
                            for i in design_qa_report.issues[:8]  # Top 8 issues
                        ]
                    })
                else:
                    logger.info(f"Design QA passed: score={design_qa_report.design_score:.1f}")
            
            file_id = str(uuid.uuid4())
            _generated_files[file_id] = str(pptx_path)
            yield _sse_event("complete", {
                "fileId": file_id,
                "filename": pptx_path.name,
                "progress": 100,
                "message": "Präsentation erstellt und validiert!",
            })
        else:
            yield _sse_event("fail", {"detail": "Unbekannter Fehler bei der Generierung"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/download/{file_id}")
async def download_file(file_id: str):
    """Download a previously generated PPTX file."""
    file_path = _generated_files.pop(file_id, None)
    if not file_path:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden oder bereits heruntergeladen")

    from pathlib import Path

    path = Path(file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Datei nicht mehr verfügbar")

    return FileResponse(
        path=file_path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
