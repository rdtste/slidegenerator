"""Image fitting — crops/resizes images to match placeholder dimensions exactly."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def fit_image_to_placeholder(
    image_path: str | Path,
    ph_width_emu: int,
    ph_height_emu: int,
) -> Path:
    """Crop and resize an image to exactly fill a placeholder (center crop).

    Ensures the image matches the placeholder's aspect ratio so
    insert_picture() fills without distortion or letterboxing.

    Args:
        image_path: Path to the source image (PNG/JPEG).
        ph_width_emu: Placeholder width in EMUs.
        ph_height_emu: Placeholder height in EMUs.

    Returns:
        Path to the fitted image (may be same as input if no change needed).
    """
    image_path = Path(image_path)

    try:
        img = Image.open(image_path)
        img_w, img_h = img.size

        if img_w == 0 or img_h == 0 or ph_width_emu == 0 or ph_height_emu == 0:
            return image_path

        img_aspect = img_w / img_h
        ph_aspect = ph_width_emu / ph_height_emu

        # If aspect ratios are close enough (within 5%), no crop needed
        if abs(img_aspect - ph_aspect) / max(img_aspect, ph_aspect) < 0.05:
            return image_path

        # Center crop to match placeholder aspect ratio
        if img_aspect > ph_aspect:
            # Image is wider — crop left/right
            new_w = int(img_h * ph_aspect)
            new_h = img_h
            left = (img_w - new_w) // 2
            box = (left, 0, left + new_w, new_h)
        else:
            # Image is taller — crop top/bottom
            new_w = img_w
            new_h = int(img_w / ph_aspect)
            top = (img_h - new_h) // 2
            box = (0, top, new_w, top + new_h)

        cropped = img.crop(box)

        # Target pixel size: scale to reasonable resolution for the placeholder
        # 96 DPI is standard screen; use placeholder EMU size for reference
        target_w = max(512, min(1920, int(ph_width_emu / 914400 * 96)))
        target_h = max(384, min(1440, int(ph_height_emu / 914400 * 96)))

        if cropped.size[0] > target_w * 1.5 or cropped.size[1] > target_h * 1.5:
            cropped = cropped.resize((target_w, target_h), Image.LANCZOS)

        # Save to same path (overwrite)
        output_path = image_path.with_stem(image_path.stem + "_fitted")
        fmt = "PNG" if image_path.suffix.lower() == ".png" else "JPEG"
        cropped.save(str(output_path), format=fmt, quality=92)

        logger.debug(
            f"[Image Fit] Cropped {img_w}x{img_h} -> {cropped.size[0]}x{cropped.size[1]} "
            f"(placeholder aspect {ph_aspect:.2f})"
        )
        return output_path

    except Exception as e:
        logger.warning(f"[Image Fit] Failed to fit image: {e}")
        return image_path
