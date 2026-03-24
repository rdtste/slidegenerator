"""Generate endpoint — creates PPTX from Markdown + template.

Features:
- Content Validation (markdown structure, layout types, char limits)
- Image Error Handling (retry logic with exponential backoff)
- QA Loop: Gemini Vision analysis + programmatic fixes (max 2 iterations)
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
from app.services.markdown_validator import MarkdownValidator
from app.services.pptx_service import generate_pptx
from app.services.template_validator import TemplateValidator
from app.services.qa_loop_service import run_qa_loop

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory store for generated files awaiting download
_generated_files: dict[str, str] = {}

_validator = MarkdownValidator()
_template_validator = TemplateValidator()


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
        # --- Phase 1: Validation ---
        yield _sse_event("progress", {
            "step": "validating", "message": "Inhalte werden validiert...", "progress": 1,
        })

        validation_result = _validator.validate(request.markdown)
        if not validation_result.is_valid:
            yield _sse_event("validation_failed", {
                "detail": "Inhaltsvalidierung fehlgeschlagen",
                "issues": [
                    {"slide": i.slide_index, "message": i.message, "severity": i.severity}
                    for i in validation_result.issues
                ],
                "error_count": len([i for i in validation_result.issues if i.severity == "error"])
            })
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
            "step": "parsed", "message": f"{total} Folien erkannt", "progress": 8,
        })

        # Template pre-flight
        template_check = _template_validator.validate_template(request.template_id)
        if not template_check.is_valid:
            template_errors = [i for i in template_check.issues if i.severity == "error"]
            if template_errors:
                yield _sse_event("template_validation_failed", {
                    "detail": "Template-Validierung fehlgeschlagen",
                    "issues": [
                        {"type": i.issue_type, "message": i.message, "severity": i.severity}
                        for i in template_check.issues[:5]
                    ]
                })
                return

        # --- Phase 2: PPTX Generation (in thread) ---
        result_holder: dict = {
            "path": None,
            "error": None,
            "generation_warnings": [],
        }

        def run_generation():
            try:
                generation_warnings: list[dict] = []
                result_holder["path"] = generate_pptx(
                    presentation,
                    request.template_id,
                    progress_callback=progress_callback,
                    warnings_collector=generation_warnings,
                )
                result_holder["generation_warnings"] = generation_warnings
            except Exception as exc:
                result_holder["error"] = str(exc)
            finally:
                progress_queue.put({"_gen_done": True})

        thread = threading.Thread(target=run_generation, daemon=True)
        thread.start()

        # Stream generation progress
        while True:
            try:
                event = progress_queue.get(timeout=120)
            except queue.Empty:
                yield _sse_event("fail", {"detail": "Timeout bei der Generierung"})
                return

            if event.get("_gen_done"):
                break

            yield _sse_event("progress", event)

        thread.join(timeout=10)

        if result_holder["error"]:
            yield _sse_event("fail", {
                "detail": f"PPTX-Generierung fehlgeschlagen: {result_holder['error']}",
            })
            return

        if not result_holder["path"]:
            yield _sse_event("fail", {"detail": "Unbekannter Fehler bei der Generierung"})
            return

        pptx_path = result_holder["path"]
        generation_warnings = result_holder.get("generation_warnings") or []

        # Report generation warnings (images that failed)
        if generation_warnings:
            yield _sse_event("generation_warnings", {
                "detail": "Einige Bilder konnten nicht KI-generiert werden.",
                "count": len(generation_warnings),
                "warnings": generation_warnings[:12],
            })

        # --- Phase 3: QA Loop (async) ---
        yield _sse_event("progress", {
            "step": "qa_start",
            "message": "Qualitaetspruefung wird gestartet...",
            "progress": 82,
        })

        qa_events: list[dict] = []

        def qa_progress(step: str, message: str, progress: int | None) -> None:
            qa_events.append({"step": step, "message": message, "progress": progress})

        try:
            qa_result = await run_qa_loop(
                str(pptx_path),
                progress_callback=qa_progress,
            )

            # Flush QA progress events to SSE
            for ev in qa_events:
                yield _sse_event("progress", ev)

            # Report QA result
            if qa_result.passed:
                yield _sse_event("qa_result", {
                    "status": "passed",
                    "message": f"Qualitaetspruefung bestanden"
                        + (f" ({qa_result.total_fixes_applied} Korrektur(en))" if qa_result.total_fixes_applied > 0 else ""),
                    "iterations": qa_result.iterations_run,
                    "fixes_applied": qa_result.total_fixes_applied,
                })
            else:
                remaining = qa_result.remaining_issues
                yield _sse_event("qa_result", {
                    "status": "issues_remaining",
                    "message": f"{len([i for i in remaining if i.severity == 'error'])} Problem(e) verbleibend",
                    "iterations": qa_result.iterations_run,
                    "fixes_applied": qa_result.total_fixes_applied,
                    "issues": [i.to_dict() for i in remaining[:8]],
                })

        except Exception as qa_error:
            logger.error(f"QA Loop exception: {qa_error}")
            yield _sse_event("progress", {
                "step": "qa_skipped",
                "message": f"Qualitaetspruefung uebersprungen: {str(qa_error)[:80]}",
                "progress": 95,
            })

        # --- Phase 4: Ready for download ---
        file_id = str(uuid.uuid4())
        _generated_files[file_id] = str(pptx_path)
        yield _sse_event("complete", {
            "fileId": file_id,
            "filename": pptx_path.name,
            "progress": 100,
            "message": "Praesentation erstellt und geprueft!",
            "warning_count": len(generation_warnings),
            "warnings": generation_warnings[:12],
        })

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
        raise HTTPException(status_code=404, detail="Datei nicht mehr verfuegbar")

    return FileResponse(
        path=file_path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
