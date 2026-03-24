"""Image generation service — generates images via Vertex AI Imagen.

Features:
- Retry logic with exponential backoff
- Cache support
- Graceful fallback on failure (returns None instead of crashing)
- Structured error logging
"""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
import time
from pathlib import Path

import google.auth
import google.auth.transport.requests
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_IMAGE_CACHE: dict[str, Path] = {}

# P0 Configuration  
MAX_RETRIES = 3
TIMEOUT_SECS = 30
RETRY_BACKOFF_BASE = 1  # seconds (1s, 2s, 4s)


def _get_access_token() -> str:
    """Get a GCP access token via Application Default Credentials."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


def generate_image(description: str, width: int = 1024, height: int = 1024) -> Path | None:
    """Generate an image synchronously (backward compatible).
    
    Wraps generate_image_async for sync contexts.
    Returns None on failure (graceful fallback).
    """
    try:
        # Run async function in event loop or create new loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(generate_image_async(description, width, height))
    except Exception as e:
        logger.error(f"Sync image generation failed: {e}")
        return None


async def generate_image_async(
    description: str,
    width: int = 1024,
    height: int = 1024,
    max_retries: int = MAX_RETRIES,
    timeout_secs: int = TIMEOUT_SECS
) -> Path | None:
    """Generate an image with retry logic and exponential backoff (P0 Feature).
    
    Args:
        description: Text description of image to generate
        width: Image width (default 1024)
        height: Image height (default 1024)
        max_retries: Number of retry attempts (default 3)
        timeout_secs: Timeout per attempt in seconds (default 30)
        
    Returns:
        Path to generated PNG, or None if all retries exhausted
        
    Behavior:
    - Checks cache first (no retry needed)
    - Retries on timeout with exponential backoff: 1s → 2s → 4s
    - Returns None on final failure (allows slide to continue without image)
    - Logs all errors for debugging
    """
    
    # Check cache first
    cache_key = f"{description}:{width}x{height}"
    if cache_key in _IMAGE_CACHE:
        cached = _IMAGE_CACHE[cache_key]
        if cached.is_file():
            logger.debug(f"Image cache hit: {description[:60]}...")
            return cached
    
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"[Image Gen] Attempt {attempt}/{max_retries}: {description[:60]}...",
                extra={"attempt": attempt, "max_retries": max_retries}
            )
            
            result = await asyncio.wait_for(
                _generate_image_once(description, width, height),
                timeout=timeout_secs
            )
            
            if result:
                logger.info(f"[Image Gen] ✓ Success on attempt {attempt}")
                return result
            
        except asyncio.TimeoutError:
            last_error = f"Timeout ({timeout_secs}s)"
            logger.warning(
                f"[Image Gen] Timeout on attempt {attempt}/{max_retries}",
                extra={"attempt": attempt, "timeout": timeout_secs, "description": description[:60]}
            )
            
            if attempt < max_retries:
                wait_time = RETRY_BACKOFF_BASE ** (attempt - 1)
                logger.info(f"[Image Gen] Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            last_error = f"{type(e).__name__}: {str(e)[:100]}"
            logger.warning(
                f"[Image Gen] Error on attempt {attempt}/{max_retries}: {last_error}",
                extra={"attempt": attempt, "error_type": type(e).__name__, "description": description[:60]}
            )
            
            if attempt < max_retries:
                wait_time = RETRY_BACKOFF_BASE ** (attempt - 1)
                logger.info(f"[Image Gen] Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
    
    # All retries exhausted
    logger.error(
        f"[Image Gen] ✗ Failed after {max_retries} attempts: {last_error}",
        extra={"max_retries": max_retries, "description": description[:60], "error": last_error}
    )
    
    # Return None → caller will use placeholder or skip image
    return None


async def _generate_image_once(description: str, width: int, height: int) -> Path | None:
    """Generate image in single attempt (no retries)."""
    
    try:
        token = _get_access_token()
    except Exception as e:
        logger.error(f"Failed to get GCP access token: {e}")
        return None

    url = (
        f"https://{settings.gcp_region}-aiplatform.googleapis.com/v1/"
        f"projects/{settings.gcp_project_id}/locations/{settings.gcp_region}/"
        f"publishers/google/models/{settings.imagen_model}:predict"
    )

    # Enhance the prompt for better presentation-quality results
    enhanced_prompt = (
        f"Professional presentation graphic: {description}. "
        "Clean, modern, high-quality, corporate style. No text overlays."
    )

    aspect = _best_aspect_ratio(width, height)
    payload = {
        "instances": [{"prompt": enhanced_prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": aspect,
            "personGeneration": "allow_adult",
            "safetySetting": "block_some",
        },
    }

    try:
        # Use async httpx for non-blocking I/O
        async with httpx.AsyncClient(timeout=TIMEOUT_SECS) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code != 200:
            logger.error(f"[Image Gen] Imagen API error {response.status_code}: {response.text[:200]}")
            return None

        data = response.json()
        predictions = data.get("predictions", [])
        if not predictions:
            logger.warning(f"[Image Gen] No predictions returned. Response: {str(data)[:200]}")
            return None

        image_b64 = predictions[0].get("bytesBase64Encoded")
        if not image_b64:
            logger.warning("[Image Gen] Prediction has no image bytes")
            return None

        image_bytes = base64.b64decode(image_b64)
        tmp = tempfile.NamedTemporaryFile(suffix=".png", prefix="slidegen_img_", delete=False)
        tmp.write(image_bytes)
        tmp.close()

        result_path = Path(tmp.name)
        _IMAGE_CACHE[f"{description}:{width}x{height}"] = result_path
        logger.debug(f"[Image Gen] Image saved: {result_path} ({len(image_bytes)} bytes)")
        return result_path

    except Exception as e:
        logger.warning(f"[Image Gen] Generation failed: {type(e).__name__}: {str(e)[:100]}")
        return None


def _best_aspect_ratio(width: int, height: int) -> str:
    """Pick the closest Imagen-supported aspect ratio."""
    ratio = width / height if height > 0 else 1.0
    # Imagen 3 supports: 1:1, 3:4, 4:3, 9:16, 16:9
    options = [
        (1.0, "1:1"),
        (0.75, "3:4"),
        (1.333, "4:3"),
        (0.5625, "9:16"),
        (1.778, "16:9"),
    ]
    best = min(options, key=lambda o: abs(o[0] - ratio))
    return best[1]


def create_fallback_image(
    description: str,
    width: int = 1024,
    height: int = 1024,
    reason: str = "Bildgenerierung nicht verfuegbar",
) -> Path | None:
    """Create a simple local fallback PNG so picture placeholders are never left empty."""
    try:
        import matplotlib.pyplot as plt
        from textwrap import fill

        fig_w = max(4.0, width / 100.0)
        fig_h = max(3.0, height / 100.0)
        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=100)
        ax.set_facecolor("#F2F4F8")
        fig.patch.set_facecolor("#F2F4F8")
        ax.axis("off")

        ax.text(
            0.5,
            0.62,
            "Bildplatzhalter",
            ha="center",
            va="center",
            fontsize=24,
            color="#1F2A37",
            fontweight="bold",
            transform=ax.transAxes,
        )
        ax.text(
            0.5,
            0.48,
            fill(reason, width=42),
            ha="center",
            va="center",
            fontsize=13,
            color="#334155",
            transform=ax.transAxes,
        )
        ax.text(
            0.5,
            0.30,
            fill(description or "Ohne Beschreibung", width=52),
            ha="center",
            va="center",
            fontsize=11,
            color="#475569",
            transform=ax.transAxes,
        )

        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", prefix="slidegen_fallback_", delete=False,
        )
        # Keep exact canvas dimensions so placeholder fill/crop behaves predictably.
        fig.savefig(tmp.name, format="png")
        plt.close(fig)
        tmp.close()

        path = Path(tmp.name)
        logger.info(f"[Image Gen] Created fallback image: {path}")
        return path
    except Exception as exc:
        logger.warning(f"[Image Gen] Fallback image creation failed: {type(exc).__name__}: {exc}")
        return None
