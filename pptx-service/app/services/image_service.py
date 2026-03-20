"""Image generation service — generates images via Vertex AI Imagen."""

from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path

import google.auth
import google.auth.transport.requests
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_IMAGE_CACHE: dict[str, Path] = {}


def _get_access_token() -> str:
    """Get a GCP access token via Application Default Credentials."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


def generate_image(description: str, width: int = 1024, height: int = 1024) -> Path | None:
    """Generate an image from a text description using Vertex AI Imagen.

    Returns the path to the generated PNG file, or None on failure.
    """
    cache_key = f"{description}:{width}x{height}"
    if cache_key in _IMAGE_CACHE:
        cached = _IMAGE_CACHE[cache_key]
        if cached.is_file():
            logger.info(f"Image cache hit: {description[:60]}...")
            return cached

    logger.info(f"Generating image: {description[:80]}...")

    try:
        token = _get_access_token()
    except Exception:
        logger.exception("Failed to get GCP access token for Imagen")
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
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code != 200:
            logger.error(f"Imagen API error {response.status_code}: {response.text[:300]}")
            return None

        data = response.json()
        predictions = data.get("predictions", [])
        if not predictions:
            logger.warning(f"Imagen returned no predictions for: {description[:60]}...")
            # If filtered, the response may contain filteredReason
            if "filteredText" in str(data) or "blocked" in str(data).lower():
                logger.warning(f"Image likely filtered by safety. Response: {str(data)[:300]}")
            return None

        image_b64 = predictions[0].get("bytesBase64Encoded")
        if not image_b64:
            logger.warning("Imagen prediction has no image bytes")
            return None

        image_bytes = base64.b64decode(image_b64)
        tmp = tempfile.NamedTemporaryFile(suffix=".png", prefix="slidegen_img_", delete=False)
        tmp.write(image_bytes)
        tmp.close()

        result_path = Path(tmp.name)
        _IMAGE_CACHE[cache_key] = result_path
        logger.info(f"Image generated: {result_path} ({len(image_bytes)} bytes)")
        return result_path

    except Exception:
        logger.exception(f"Image generation failed for: {description[:60]}...")
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
