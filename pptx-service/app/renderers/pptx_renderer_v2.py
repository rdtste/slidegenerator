"""V2 PPTX Renderer — converts RenderInstructions into a .pptx file.

This renderer takes deterministic RenderInstructions and produces slides.
No LLM, no decisions — pure execution.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Callable

from pptx import Presentation
from pptx.util import Cm, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE

from app.schemas.models import RenderInstruction, RenderElement, SlideType

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, int | None], None]


def _hex_to_rgb(hex_color: str) -> RGBColor:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return RGBColor(0x33, 0x33, 0x33)
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _set_alignment(tf_or_para, alignment: str) -> None:
    mapping = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
    tf_or_para.alignment = mapping.get(alignment, PP_ALIGN.LEFT)


class PptxRendererV2:
    """Renders a list of RenderInstructions into a .pptx file."""

    def __init__(self, accent_color: str = "#2563EB", font_family: str = "Calibri"):
        self.accent_color = accent_color
        self.font_family = font_family
        self._image_generator: Callable | None = None
        self._chart_generator: Callable | None = None

    def set_image_generator(self, fn: Callable) -> None:
        self._image_generator = fn

    def set_chart_generator(self, fn: Callable) -> None:
        self._chart_generator = fn

    def render(
        self,
        instructions: list[RenderInstruction],
        output_dir: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> Path:
        prs = Presentation()
        prs.slide_width = Cm(25.4)
        prs.slide_height = Cm(19.05)

        blank_layout = prs.slide_layouts[6]  # Blank layout

        total = len(instructions)
        for i, instr in enumerate(instructions):
            if progress_callback:
                pct = int(10 + (i / total) * 80)
                progress_callback("rendering", f"Folie {i+1}/{total} wird gerendert...", pct)

            slide = prs.slides.add_slide(blank_layout)

            # Set background
            self._set_background(slide, instr.background_color)

            # Render each element
            for element in instr.elements:
                try:
                    self._render_element(slide, element, instr)
                except Exception as exc:
                    logger.warning(f"Element render error on slide {i+1}: {exc}")

        # Save
        out_dir = Path(output_dir or tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "presentation_v2.pptx"
        prs.save(str(out_path))

        if progress_callback:
            progress_callback("saved", "Praesentation gespeichert", 95)

        return out_path

    def _set_background(self, slide, color: str) -> None:
        bg = slide.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = _hex_to_rgb(color)

    def _render_element(self, slide, element: RenderElement,
                        instr: RenderInstruction) -> None:
        if element.element_type == "shape":
            self._render_shape(slide, element)
        elif element.element_type == "image":
            self._render_image(slide, element)
        elif element.element_type == "chart":
            self._render_chart(slide, element)
        elif element.element_type == "bullets":
            self._render_bullets(slide, element)
        else:
            self._render_text(slide, element)

    def _render_text(self, slide, element: RenderElement) -> None:
        text = str(element.content) if element.content else ""
        if not text.strip():
            return

        pos = element.position
        style = element.style

        txBox = slide.shapes.add_textbox(
            Cm(pos.left_cm), Cm(pos.top_cm),
            Cm(pos.width_cm), Cm(pos.height_cm),
        )
        tf = txBox.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE

        # Vertical alignment
        va_map = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE,
                  "bottom": MSO_ANCHOR.BOTTOM}
        tf.paragraphs[0].alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER,
                                       "right": PP_ALIGN.RIGHT}.get(style.alignment, PP_ALIGN.LEFT)

        # Handle bold prefix format: **prefix** rest
        if "**" in text:
            parts = text.split("**")
            p = tf.paragraphs[0]
            p.space_after = Pt(0)
            _set_alignment(p, style.alignment)
            for i, part in enumerate(parts):
                if not part:
                    continue
                run = p.add_run()
                run.text = part
                run.font.name = style.font_family
                run.font.size = Pt(style.font_size_pt)
                run.font.color.rgb = _hex_to_rgb(style.font_color)
                run.font.bold = (i % 2 == 1)  # odd parts are bold
        else:
            p = tf.paragraphs[0]
            p.space_after = Pt(0)
            _set_alignment(p, style.alignment)
            run = p.add_run()
            run.text = text
            run.font.name = style.font_family
            run.font.size = Pt(style.font_size_pt)
            run.font.color.rgb = _hex_to_rgb(style.font_color)
            run.font.bold = style.bold

        # Line spacing
        if style.line_spacing != 1.0:
            for para in tf.paragraphs:
                para.line_spacing = Pt(int(style.font_size_pt * style.line_spacing))

    def _render_bullets(self, slide, element: RenderElement) -> None:
        items = element.content if isinstance(element.content, list) else []
        if not items:
            return

        pos = element.position
        style = element.style

        txBox = slide.shapes.add_textbox(
            Cm(pos.left_cm), Cm(pos.top_cm),
            Cm(pos.width_cm), Cm(pos.height_cm),
        )
        tf = txBox.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE

        for idx, item_text in enumerate(items):
            if idx == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()

            p.space_before = Pt(6) if idx > 0 else Pt(0)
            p.space_after = Pt(4)
            _set_alignment(p, style.alignment)

            if style.line_spacing != 1.0:
                p.line_spacing = Pt(int(style.font_size_pt * style.line_spacing))

            # Handle **bold** formatting within bullets
            if "**" in str(item_text):
                parts = str(item_text).split("**")
                for i, part in enumerate(parts):
                    if not part:
                        continue
                    run = p.add_run()
                    run.text = part
                    run.font.name = style.font_family
                    run.font.size = Pt(style.font_size_pt)
                    run.font.color.rgb = _hex_to_rgb(style.font_color)
                    run.font.bold = (i % 2 == 1)
            else:
                # Add bullet character
                run = p.add_run()
                run.text = f"\u2022  {item_text}"
                run.font.name = style.font_family
                run.font.size = Pt(style.font_size_pt)
                run.font.color.rgb = _hex_to_rgb(style.font_color)

    def _render_shape(self, slide, element: RenderElement) -> None:
        pos = element.position
        content = element.content if isinstance(element.content, dict) else {}
        fill_color = content.get("fill", "#e5e7eb")
        corner_r = content.get("corner_radius_cm", 0)

        if corner_r > 0:
            shape = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Cm(pos.left_cm), Cm(pos.top_cm),
                Cm(pos.width_cm), Cm(pos.height_cm),
            )
            # Set corner radius
            shape.adjustments[0] = min(corner_r / min(pos.width_cm, pos.height_cm), 0.5)
        else:
            shape = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Cm(pos.left_cm), Cm(pos.top_cm),
                Cm(pos.width_cm), Cm(pos.height_cm),
            )

        shape.fill.solid()
        shape.fill.fore_color.rgb = _hex_to_rgb(fill_color)
        shape.line.fill.background()  # No border

    def _render_image(self, slide, element: RenderElement) -> None:
        pos = element.position
        content = element.content if isinstance(element.content, dict) else {}
        description = content.get("description", "")

        if not description:
            return

        image_path = None
        if self._image_generator:
            try:
                image_path = self._image_generator(description)
            except Exception as exc:
                logger.warning(f"Image generation failed: {exc}")

        if image_path and Path(image_path).exists():
            slide.shapes.add_picture(
                str(image_path),
                Cm(pos.left_cm), Cm(pos.top_cm),
                Cm(pos.width_cm), Cm(pos.height_cm),
            )
        else:
            # Placeholder rectangle with description
            shape = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Cm(pos.left_cm), Cm(pos.top_cm),
                Cm(pos.width_cm), Cm(pos.height_cm),
            )
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(0x23, 0x27, 0x2f)
            shape.line.fill.background()

            tf = shape.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            run = p.add_run()
            run.text = f"[Bild: {description[:80]}]"
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(0x9c, 0xa3, 0xaf)

    def _render_chart(self, slide, element: RenderElement) -> None:
        pos = element.position
        content = element.content if isinstance(element.content, dict) else {}

        if not content or not self._chart_generator:
            # Placeholder
            shape = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Cm(pos.left_cm), Cm(pos.top_cm),
                Cm(pos.width_cm), Cm(pos.height_cm),
            )
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(0xf3, 0xf4, 0xf6)
            shape.line.fill.background()
            tf = shape.text_frame
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            run = p.add_run()
            run.text = "[Chart-Platzhalter]"
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(0x9c, 0xa3, 0xaf)
            return

        try:
            chart_path = self._chart_generator(content, self.accent_color)
            if chart_path and Path(chart_path).exists():
                slide.shapes.add_picture(
                    str(chart_path),
                    Cm(pos.left_cm), Cm(pos.top_cm),
                    Cm(pos.width_cm), Cm(pos.height_cm),
                )
        except Exception as exc:
            logger.warning(f"Chart generation failed: {exc}")
