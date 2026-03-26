"""V2 Generate endpoint — AI-driven 8-stage pipeline for presentation generation.

Uses the V2 pipeline orchestrator with structured LLM output,
14 slide types, layout engine, and deterministic rendering.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.schemas.models import Audience, ImageStyleType

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory store for generated files awaiting download
_generated_files: dict[str, str] = {}


class GenerateV2Request(BaseModel):
    """Request body for V2 pipeline generation."""
    prompt: str = Field(..., description="User prompt / briefing text")
    document_text: str = Field("", description="Extracted document text (optional)")
    audience: str = Field("management", description="Target audience")
    image_style: str = Field("minimal", description="Image style preference")
    accent_color: str = Field("#2563EB", description="Accent color hex")
    font_family: str = Field("Calibri", description="Font family")
    template_id: str | None = Field(None, description="Template ID (optional)")


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _parse_audience(value: str) -> Audience:
    try:
        return Audience(value)
    except ValueError:
        return Audience.MANAGEMENT


def _parse_image_style(value: str) -> ImageStyleType:
    try:
        return ImageStyleType(value)
    except ValueError:
        return ImageStyleType.MINIMAL


@router.post("/generate-v2")
async def generate_v2(request: GenerateV2Request):
    """Generate a presentation using the V2 AI pipeline with SSE progress."""

    async def event_generator():
        from app.pipeline.orchestrator import PipelineOrchestrator

        audience = _parse_audience(request.audience)
        image_style = _parse_image_style(request.image_style)

        orchestrator = PipelineOrchestrator(
            audience=audience,
            image_style=image_style,
            accent_color=request.accent_color,
            font_family=request.font_family,
            template_id=request.template_id,
        )

        # Wire up image generator — uses shared thread pool + dedicated event loop
        try:
            from app.services.image_service import generate_image_async
            from app.services._image_thread import run_image_gen_sync

            orchestrator.set_image_generator(
                lambda desc: run_image_gen_sync(desc, generate_image_async)
            )
        except Exception as exc:
            logger.warning(f"Image generator not available: {exc}")

        # Wire up chart generator
        try:
            from app.services.chart_service import generate_chart
            orchestrator.set_chart_generator(
                lambda data, color: generate_chart(data, colors=[color])
            )
        except Exception as exc:
            logger.warning(f"Chart generator not available: {exc}")

        # Use asyncio.Queue for real-time progress streaming
        progress_queue: asyncio.Queue = asyncio.Queue()

        def on_progress(step: str, message: str, pct: int | None) -> None:
            progress_queue.put_nowait({"step": step, "message": message, "progress": pct})

        orchestrator.set_progress_callback(on_progress)

        # Run pipeline in background task so we can yield SSE events in real-time
        pipeline_result: dict = {"result": None, "error": None}

        async def run_pipeline():
            try:
                pipeline_result["result"] = await orchestrator.run(
                    user_input=request.prompt,
                    document_text=request.document_text,
                )
            except Exception as exc:
                pipeline_result["error"] = exc
            finally:
                # Signal completion
                await progress_queue.put(None)

        task = asyncio.create_task(run_pipeline())

        # Stream progress events as they arrive
        while True:
            event = await progress_queue.get()
            if event is None:
                break
            yield _sse_event("progress", event)

        await task  # Ensure task is fully done

        if pipeline_result["error"]:
            logger.exception("V2 pipeline failed", exc_info=pipeline_result["error"])
            yield _sse_event("fail", {
                "detail": f"Pipeline-Fehler: {str(pipeline_result['error'])[:500]}",
            })
            return

        result = pipeline_result["result"]

        design_score = result.quality.design_score
        design_info = f", Design: {design_score:.1f}/10" if design_score else ""
        design_fixes = result.quality.design_fixes_applied

        yield _sse_event("progress", {
            "step": "quality",
            "message": f"Qualitaet: {result.score:.0f}/100 ({result.slide_count} Folien{design_info})",
            "progress": 95,
        })

        # Store file for download
        file_id = str(uuid.uuid4())
        _generated_files[file_id] = str(result.pptx_path)

        yield _sse_event("complete", {
            "fileId": file_id,
            "filename": result.pptx_path.name,
            "progress": 100,
            "message": "Praesentation erstellt!",
            "quality": {
                "passed": result.passed,
                "score": result.score,
                "slide_count": result.slide_count,
                "design_score": design_score,
                "design_fixes": design_fixes,
            },
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/download-v2/{file_id}")
async def download_v2_file(file_id: str):
    """Download a V2-generated PPTX file."""
    file_path = _generated_files.pop(file_id, None)
    if not file_path:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    from pathlib import Path
    path = Path(file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Datei nicht mehr verfuegbar")

    return FileResponse(
        path=file_path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
