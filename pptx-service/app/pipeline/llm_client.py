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

_MODEL = "gemini-2.5-pro"

# ── Cached credentials & client ──────────────────────────────────────────
_credentials: google.auth.credentials.Credentials | None = None
_token_expiry: float = 0  # epoch seconds

_sync_client: httpx.Client | None = None
_async_client: httpx.AsyncClient | None = None


def _get_access_token(force_refresh: bool = False) -> str:
    global _credentials, _token_expiry
    now = time.time()
    if not force_refresh and _credentials is not None and now < _token_expiry:
        return _credentials.token
    if _credentials is None:
        _credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    _credentials.refresh(google.auth.transport.requests.Request())
    _token_expiry = now + 3000
    return _credentials.token


def _invalidate_token() -> None:
    """Force token refresh on next call (e.g. after 401)."""
    global _token_expiry
    _token_expiry = 0


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


def _repair_truncated_json(raw: str) -> str | None:
    """Try to repair truncated JSON by closing open structures.

    When the LLM output is cut off by max_tokens, the JSON is valid up to
    the truncation point. We strip the last incomplete value/key, then close
    all open brackets/braces.
    """
    # Strip trailing incomplete string or key-value
    cleaned = raw.rstrip()
    # Remove trailing comma or colon
    cleaned = cleaned.rstrip(",: ")
    # If we're mid-string (odd number of unescaped quotes after last complete value),
    # close the string first
    in_string = False
    i = 0
    while i < len(cleaned):
        c = cleaned[i]
        if c == '\\' and in_string:
            i += 2
            continue
        if c == '"':
            in_string = not in_string
        i += 1
    if in_string:
        cleaned += '"'

    # Count open brackets/braces that need closing
    stack: list[str] = []
    in_str = False
    i = 0
    while i < len(cleaned):
        c = cleaned[i]
        if c == '\\' and in_str:
            i += 2
            continue
        if c == '"':
            in_str = not in_str
        elif not in_str:
            if c in ('{', '['):
                stack.append('}' if c == '{' else ']')
            elif c in ('}', ']'):
                if stack:
                    stack.pop()
        i += 1

    # Close everything
    cleaned += ''.join(reversed(stack))
    return cleaned


def call_llm(prompt: str, temperature: float = 0.7, max_tokens: int = 8192) -> str:
    """Call Gemini and return raw text response."""
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }

    for attempt in range(2):
        token = _get_access_token(force_refresh=(attempt > 0))
        resp = _get_sync_client().post(_gemini_url(), json=payload, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        if resp.status_code == 401 and attempt == 0:
            logger.warning("Gemini returned 401 — refreshing token and retrying")
            _invalidate_token()
            continue
        resp.raise_for_status()
        break

    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text.strip()


def call_llm_structured(prompt: str, output_type: Type[T],
                        temperature: float = 0.7,
                        max_tokens: int = 16384) -> T:
    """Call Gemini and parse response into a Pydantic model."""
    raw = _clean_json(call_llm(prompt, temperature=temperature, max_tokens=max_tokens))

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        repaired = _repair_truncated_json(raw)
        if repaired:
            try:
                parsed = json.loads(repaired)
                logger.warning("LLM JSON was truncated — repaired by closing open structures")
            except json.JSONDecodeError as exc2:
                logger.error(f"LLM returned invalid JSON (repair failed): {raw[:500]}")
                raise ValueError(f"LLM output is not valid JSON: {exc2}") from exc2
        else:
            logger.error(f"LLM returned invalid JSON: {raw[:500]}")
            raise

    return output_type.model_validate(parsed)


async def call_llm_async(prompt: str, temperature: float = 0.7,
                         max_tokens: int = 8192) -> str:
    """Async version of call_llm."""
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }

    for attempt in range(2):
        token = _get_access_token(force_refresh=(attempt > 0))
        resp = await _get_async_client().post(_gemini_url(), json=payload, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        if resp.status_code == 401 and attempt == 0:
            logger.warning("Gemini returned 401 — refreshing token and retrying")
            _invalidate_token()
            continue
        resp.raise_for_status()
        break

    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text.strip()


async def call_llm_structured_async(prompt: str, output_type: Type[T],
                                     temperature: float = 0.7,
                                     max_tokens: int = 16384) -> T:
    """Async version of call_llm_structured."""
    raw = _clean_json(await call_llm_async(prompt, temperature=temperature, max_tokens=max_tokens))

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        repaired = _repair_truncated_json(raw)
        if repaired:
            try:
                parsed = json.loads(repaired)
                logger.warning("LLM JSON was truncated — repaired by closing open structures")
            except json.JSONDecodeError as exc2:
                logger.error(f"LLM returned invalid JSON (repair failed): {raw[:500]}")
                raise ValueError(f"LLM output is not valid JSON: {exc2}") from exc2
        else:
            logger.error(f"LLM returned invalid JSON: {raw[:500]}")
            raise

    return output_type.model_validate(parsed)
