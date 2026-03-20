"""Generate endpoint — creates PPTX from Markdown + template."""

from __future__ import annotations

import json
import logging
import queue
import threading
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.models.schemas import GenerateRequest
from app.services.markdown_service import parse_markdown
from app.services.pptx_service import generate_pptx

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory store for generated files awaiting download
_generated_files: dict[str, str] = {}


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
        yield _sse_event("progress", {
            "step": "parsing", "message": "Markdown wird analysiert...", "progress": 2,
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
            "step": "parsed", "message": f"{total} Folien erkannt", "progress": 5,
        })

        result_holder: dict = {"path": None, "error": None}

        def run_generation():
            try:
                result_holder["path"] = generate_pptx(
                    presentation, request.template_id, progress_callback=progress_callback,
                )
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
            yield _sse_event("progress", event)

        thread.join(timeout=10)

        if result_holder["error"]:
            yield _sse_event("fail", {
                "detail": f"PPTX-Generierung fehlgeschlagen: {result_holder['error']}",
            })
        elif result_holder["path"]:
            file_id = str(uuid.uuid4())
            _generated_files[file_id] = str(result_holder["path"])
            yield _sse_event("complete", {
                "fileId": file_id,
                "filename": result_holder["path"].name,
                "progress": 100,
                "message": "Fertig!",
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
