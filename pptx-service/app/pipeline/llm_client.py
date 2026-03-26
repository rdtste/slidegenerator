"""LLM client for the V2 pipeline — calls Gemini with structured JSON output.

Performance: credentials and httpx client are cached at module level to avoid
repeated OAuth token refreshes and TCP connection setup on every LLM call.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Type, TypeVar

import google.auth
import google.auth.transport.requests
import httpx

from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_MODEL = "gemini-2.5-flash"

# ── Cached credentials & client ──────────────────────────────────────────
_credentials: google.auth.credentials.Credentials | None = None
_token_expiry: float = 0  # epoch seconds

_sync_client: httpx.Client | None = None
_async_client: httpx.AsyncClient | None = None


def _get_access_token() -> str:
    global _credentials, _token_expiry
    now = time.time()
    if _credentials is not None and now < _token_expiry:
        return _credentials.token
    if _credentials is None:
        _credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    _credentials.refresh(google.auth.transport.requests.Request())
    # Cache token for 50 minutes (tokens typically valid for 60 min)
    _token_expiry = now + 3000
    return _credentials.token


def _get_sync_client() -> httpx.Client:
    global _sync_client
    if _sync_client is None or _sync_client.is_closed:
        _sync_client = httpx.Client(timeout=120, http2=False)
    return _sync_client


def _get_async_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None or _async_client.is_closed:
        _async_client = httpx.AsyncClient(timeout=120, http2=False)
    return _async_client


def _gemini_url() -> str:
    return (
        f"https://{settings.gcp_region}-aiplatform.googleapis.com/v1/"
        f"projects/{settings.gcp_project_id}/locations/{settings.gcp_region}/"
        f"publishers/google/models/{_MODEL}:generateContent"
    )


def _clean_json(raw: str) -> str:
    """Strip markdown fences from LLM output."""
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


def call_llm(prompt: str, temperature: float = 0.7, max_tokens: int = 8192) -> str:
    """Call Gemini and return raw text response."""
    token = _get_access_token()

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }

    resp = _get_sync_client().post(_gemini_url(), json=payload, headers={
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
    raw = _clean_json(call_llm(prompt, temperature=temperature))

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

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }

    resp = await _get_async_client().post(_gemini_url(), json=payload, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    resp.raise_for_status()

    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text.strip()


async def call_llm_structured_async(prompt: str, output_type: Type[T],
                                     temperature: float = 0.7,
                                     max_tokens: int = 8192) -> T:
    """Async version of call_llm_structured."""
    raw = _clean_json(await call_llm_async(prompt, temperature=temperature, max_tokens=max_tokens))

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error(f"LLM returned invalid JSON: {raw[:500]}")
        raise ValueError(f"LLM output is not valid JSON: {exc}") from exc

    return output_type.model_validate(parsed)
