"""FastAPI application entry point — PPTX Generation Microservice."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import templates, generate
from app.config import settings

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Slidegenerator PPTX Service",
    description="Microservice für Folienmaster-basierte PPTX-Generierung.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(templates.router, prefix="/api/v1", tags=["Templates"])
app.include_router(generate.router, prefix="/api/v1", tags=["Generate"])


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
