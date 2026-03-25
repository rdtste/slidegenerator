"""LLM client for the V2 pipeline — calls Gemini with structured JSON output."""

from __future__ import annotations

import json
import logging
from typing import Any, Type, TypeVar

import google.auth
import google.auth.transport.requests
import httpx

from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_MODEL = "gemini-2.5-flash"


def _get_access_token() -> str:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


def call_llm(prompt: str, temperature: float = 0.7, max_tokens: int = 8192) -> str:
    """Call Gemini and return raw text response."""
    token = _get_access_token()
    url = (
        f"https://{settings.gcp_region}-aiplatform.googleapis.com/v1/"
        f"projects/{settings.gcp_project_id}/locations/{settings.gcp_region}/"
        f"publishers/google/models/{_MODEL}:generateContent"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(url, json=payload, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        resp.raise_for_status()

    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text.strip()


def call_llm_structured(prompt: str, output_type: Type[T],
                        temperature: float = 0.7) -> T:
    """Call Gemini and parse response into a Pydantic model."""
    raw = call_llm(prompt, temperature=temperature)

    # Clean potential markdown fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error(f"LLM returned invalid JSON: {raw[:500]}")
        raise ValueError(f"LLM output is not valid JSON: {exc}") from exc

    return output_type.model_validate(parsed)


async def call_llm_async(prompt: str, temperature: float = 0.7,
                         max_tokens: int = 8192) -> str:
    """Async version of call_llm."""
    token = _get_access_token()
    url = (
        f"https://{settings.gcp_region}-aiplatform.googleapis.com/v1/"
        f"projects/{settings.gcp_project_id}/locations/{settings.gcp_region}/"
        f"publishers/google/models/{_MODEL}:generateContent"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        resp.raise_for_status()

    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text.strip()


async def call_llm_structured_async(prompt: str, output_type: Type[T],
                                     temperature: float = 0.7) -> T:
    """Async version of call_llm_structured."""
    raw = await call_llm_async(prompt, temperature=temperature)

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error(f"LLM returned invalid JSON: {raw[:500]}")
        raise ValueError(f"LLM output is not valid JSON: {exc}") from exc

    return output_type.model_validate(parsed)
