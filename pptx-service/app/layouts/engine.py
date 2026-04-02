"""Layout Engine — transforms FilledSlide + Blueprint into RenderInstructions.

This is the bridge between semantic slide content and pixel-precise rendering.
No LLM involved — purely deterministic.
"""

from __future__ import annotations

import logging
from typing import Any

from app.schemas.models import (
    Audience, ImageStyleType, FilledSlide, SlideType,
    RenderInstruction, RenderElement, ElementPosition, ElementStyle,
    BulletsBlock, KpiBlock, QuoteBlock, ComparisonColumnBlock,
    TimelineEntryBlock, ProcessStepBlock, CardBlock, TextBlock,
    LabelValueBlock,
)
from app.layouts.blueprints import get_blueprint, ElementBlueprint, SlideBlueprint

logger = logging.getLogger(__name__)

# Audience style modifiers — tuned for readability
_AUDIENCE_MODS: dict[Audience, dict[str, float]] = {
    Audience.MANAGEMENT: {
        "headline_size": 1.1, "body_size": 0.85, "whitespace": 1.25,
        "kpi_value_size": 1.25, "line_spacing": 1.2,
    },
    Audience.TEAM: {
        "headline_size": 1.0, "body_size": 0.95, "whitespace": 1.1,
        "kpi_value_size": 1.0, "line_spacing": 1.1,
    },
    Audience.CUSTOMER: {
        "headline_size": 1.1, "body_size": 0.9, "whitespace": 1.3,
        "kpi_value_size": 1.15, "line_spacing": 1.15,
    },
    Audience.WORKSHOP: {
        "headline_size": 1.0, "body_size": 1.0, "whitespace": 1.0,
        "kpi_value_size": 1.0, "line_spacing": 1.0,
    },
}


class LayoutEngine:
    """Calculates RenderInstructions from FilledSlides and Blueprints."""

    def __init__(self, accent_color: str = "#2563EB", font_family: str = "Calibri"):
        self.accent_color = accent_color
        self.font_family = font_family

    def calculate(
        self,
        slide: FilledSlide,
        audience: Audience = Audience.MANAGEMENT,
        image_style: ImageStyleType = ImageStyleType.MINIMAL,
        slide_index: int = 0,
    ) -> RenderInstruction:
        bp = get_blueprint(slide.slide_type)
        mods = _AUDIENCE_MODS.get(audience, _AUDIENCE_MODS[Audience.TEAM])

        instruction = RenderInstruction(
            slide_index=slide_index,
            slide_type=slide.slide_type,
            layout_id=f"v2_{slide.slide_type.value}",
            accent_color=self.accent_color,
            background_color=self._resolve_bg(bp.background),
        )

        # Add elements based on slide type
        handler = getattr(self, f"_layout_{slide.slide_type.value}", None)
        if handler:
            handler(slide, bp, mods, instruction)
        else:
            self._layout_generic(slide, bp, mods, instruction)

        return instruction

    # ── Per-type layout handlers ──

    def _layout_title_hero(self, slide: FilledSlide, bp: SlideBlueprint,
                           mods: dict, instr: RenderInstruction) -> None:
        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.key == "subheadline" and slide.subheadline:
                instr.elements.append(self._text_element(el, slide.subheadline, mods))
            elif el.is_shape:
                instr.elements.append(self._shape_element(el))

    def _layout_section_divider(self, slide: FilledSlide, bp: SlideBlueprint,
                                mods: dict, instr: RenderInstruction) -> None:
        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.is_shape:
                instr.elements.append(self._shape_element(el))

    def _layout_key_statement(self, slide: FilledSlide, bp: SlideBlueprint,
                              mods: dict, instr: RenderInstruction) -> None:
        quote_text = ""
        attribution = ""
        for cb in slide.content_blocks:
            if isinstance(cb, QuoteBlock):
                quote_text = cb.text
                attribution = cb.attribution
                break
        if not quote_text:
            quote_text = slide.core_message or slide.headline

        for el in bp.elements:
            if el.key == "statement":
                instr.elements.append(self._text_element(el, quote_text, mods))
            elif el.key == "attribution" and attribution:
                instr.elements.append(self._text_element(el, f"— {attribution}", mods))
            elif el.is_shape:
                instr.elements.append(self._shape_element(el))

    def _layout_bullets_focused(self, slide: FilledSlide, bp: SlideBlueprint,
                                mods: dict, instr: RenderInstruction) -> None:
        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.key == "bullet_area":
                bullets = self._extract_bullets(slide)
                instr.elements.append(self._bullet_element(el, bullets, mods))

    def _layout_three_cards(self, slide: FilledSlide, bp: SlideBlueprint,
                            mods: dict, instr: RenderInstruction) -> None:
        cards = [cb for cb in slide.content_blocks if isinstance(cb, CardBlock)]

        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.key.startswith("card_") and el.is_shape:
                instr.elements.append(self._shape_element(el))
            elif el.key.startswith("card_icon_"):
                idx = int(el.key.split("_")[-1])
                if idx < len(cards) and cards[idx].icon_hint:
                    from app.utils.icon_resolver import resolve_icon_hint
                    emoji = resolve_icon_hint(cards[idx].icon_hint)
                    if emoji:
                        instr.elements.append(self._text_element(el, emoji, mods))
            elif el.key.startswith("card_title_"):
                idx = int(el.key.split("_")[-1])
                if idx < len(cards):
                    instr.elements.append(self._text_element(el, cards[idx].title, mods))
            elif el.key.startswith("card_body_"):
                idx = int(el.key.split("_")[-1])
                if idx < len(cards):
                    instr.elements.append(self._text_element(el, cards[idx].body, mods))

    def _layout_kpi_dashboard(self, slide: FilledSlide, bp: SlideBlueprint,
                              mods: dict, instr: RenderInstruction) -> None:
        kpis = [cb for cb in slide.content_blocks if isinstance(cb, KpiBlock)]
        kpi_count = len(kpis)

        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
                continue

            # Only render elements matching KPI count
            for prefix in ("kpi_card_", "kpi_value_", "kpi_label_", "kpi_delta_"):
                if el.key.startswith(prefix):
                    idx = int(el.key.split("_")[-1])
                    if idx >= kpi_count:
                        break
                    if prefix == "kpi_card_":
                        # Recalculate card positions for actual count
                        adjusted = self._redistribute_element(el, idx, kpi_count)
                        instr.elements.append(self._shape_element(adjusted))
                    elif prefix == "kpi_value_":
                        adjusted = self._redistribute_element(el, idx, kpi_count)
                        size = int(el.font_size_pt * mods.get("kpi_value_size", 1.0))
                        adj_el = ElementBlueprint(**{**adjusted.__dict__, "font_size_pt": size})
                        instr.elements.append(self._text_element(adj_el, kpis[idx].value, mods))
                    elif prefix == "kpi_label_":
                        adjusted = self._redistribute_element(el, idx, kpi_count)
                        instr.elements.append(self._text_element(adjusted, kpis[idx].label, mods))
                    elif prefix == "kpi_delta_":
                        adjusted = self._redistribute_element(el, idx, kpi_count)
                        delta_text = kpis[idx].delta
                        if delta_text:
                            color = "#22c55e" if kpis[idx].trend.value == "up" else (
                                "#ef4444" if kpis[idx].trend.value == "down" else "#6b7280")
                            adj_el = ElementBlueprint(**{**adjusted.__dict__, "font_color": color})
                            instr.elements.append(self._text_element(adj_el, delta_text, mods))
                    break

    def _layout_image_text_split(self, slide: FilledSlide, bp: SlideBlueprint,
                                 mods: dict, instr: RenderInstruction) -> None:
        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.key == "body_area":
                bullets = self._extract_bullets(slide)
                if bullets:
                    instr.elements.append(self._bullet_element(el, bullets, mods))
                else:
                    text = self._extract_text(slide)
                    instr.elements.append(self._text_element(el, text, mods))
            elif el.key == "image_area":
                instr.elements.append(RenderElement(
                    element_type="image",
                    content={"description": slide.visual.image_description,
                             "role": slide.visual.image_role.value},
                    position=ElementPosition(left_cm=el.x_cm, top_cm=el.y_cm,
                                             width_cm=el.w_cm, height_cm=el.h_cm),
                ))

    def _layout_comparison(self, slide: FilledSlide, bp: SlideBlueprint,
                           mods: dict, instr: RenderInstruction) -> None:
        cols = [cb for cb in slide.content_blocks if isinstance(cb, ComparisonColumnBlock)]

        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.key == "col_left_label" and len(cols) > 0:
                instr.elements.append(self._text_element(el, cols[0].column_label, mods))
            elif el.key == "col_left_body" and len(cols) > 0:
                instr.elements.append(self._bullet_element(el, cols[0].items, mods))
            elif el.key == "col_right_label" and len(cols) > 1:
                instr.elements.append(self._text_element(el, cols[1].column_label, mods))
            elif el.key == "col_right_body" and len(cols) > 1:
                instr.elements.append(self._bullet_element(el, cols[1].items, mods))
            elif el.is_shape:
                instr.elements.append(self._shape_element(el))

    def _layout_timeline(self, slide: FilledSlide, bp: SlideBlueprint,
                         mods: dict, instr: RenderInstruction) -> None:
        entries = [cb for cb in slide.content_blocks if isinstance(cb, TimelineEntryBlock)]
        count = len(entries)

        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.key == "track_line":
                instr.elements.append(self._shape_element(el))
            elif el.key.startswith("node_"):
                idx = int(el.key.split("_")[-1])
                if idx < count:
                    adjusted = self._redistribute_timeline(el, idx, count)
                    instr.elements.append(self._shape_element(adjusted))
            elif el.key.startswith("date_"):
                idx = int(el.key.split("_")[-1])
                if idx < count:
                    adjusted = self._redistribute_timeline(el, idx, count)
                    instr.elements.append(self._text_element(adjusted, entries[idx].date, mods))
            elif el.key.startswith("entry_title_"):
                idx = int(el.key.split("_")[-1])
                if idx < count:
                    adjusted = self._redistribute_timeline(el, idx, count)
                    instr.elements.append(self._text_element(adjusted, entries[idx].title, mods))
            elif el.key.startswith("entry_desc_"):
                idx = int(el.key.split("_")[-1])
                if idx < count:
                    adjusted = self._redistribute_timeline(el, idx, count)
                    instr.elements.append(self._text_element(adjusted, entries[idx].description, mods))

    def _layout_process_flow(self, slide: FilledSlide, bp: SlideBlueprint,
                             mods: dict, instr: RenderInstruction) -> None:
        steps = [cb for cb in slide.content_blocks if isinstance(cb, ProcessStepBlock)]
        count = len(steps)

        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.key.startswith("step_box_"):
                idx = int(el.key.split("_")[-1])
                if idx < count:
                    instr.elements.append(self._shape_element(el))
            elif el.key.startswith("step_num_"):
                idx = int(el.key.split("_")[-1])
                if idx < count:
                    instr.elements.append(self._text_element(el, str(steps[idx].step_number), mods))
            elif el.key.startswith("step_title_"):
                idx = int(el.key.split("_")[-1])
                if idx < count:
                    instr.elements.append(self._text_element(el, steps[idx].title, mods))
            elif el.key.startswith("step_desc_"):
                idx = int(el.key.split("_")[-1])
                if idx < count:
                    instr.elements.append(self._text_element(el, steps[idx].description, mods))
            elif el.key.startswith("arrow_"):
                idx = int(el.key.split("_")[-1])
                if idx < count - 1:
                    instr.elements.append(self._shape_element(el))

    def _layout_chart_insight(self, slide: FilledSlide, bp: SlideBlueprint,
                              mods: dict, instr: RenderInstruction) -> None:
        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.key == "chart_area":
                chart_spec = slide.visual.chart_spec
                instr.elements.append(RenderElement(
                    element_type="chart",
                    content=chart_spec.model_dump() if chart_spec else {},
                    position=ElementPosition(left_cm=el.x_cm, top_cm=el.y_cm,
                                             width_cm=el.w_cm, height_cm=el.h_cm),
                ))
            elif el.key == "takeaway_area":
                bullets = self._extract_bullets(slide)
                if bullets:
                    instr.elements.append(self._bullet_element(el, bullets, mods))

    def _layout_image_fullbleed(self, slide: FilledSlide, bp: SlideBlueprint,
                                mods: dict, instr: RenderInstruction) -> None:
        for el in bp.elements:
            if el.key == "background_image":
                instr.elements.append(RenderElement(
                    element_type="image",
                    content={"description": slide.visual.image_description,
                             "role": "hero", "fullbleed": True},
                    position=ElementPosition(left_cm=el.x_cm, top_cm=el.y_cm,
                                             width_cm=el.w_cm, height_cm=el.h_cm),
                ))
            elif el.key == "headline" and slide.headline:
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.is_shape:
                instr.elements.append(self._shape_element(el))

    def _layout_agenda(self, slide: FilledSlide, bp: SlideBlueprint,
                       mods: dict, instr: RenderInstruction) -> None:
        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.key == "agenda_list":
                items = self._extract_bullets(slide)
                # Format as numbered list
                numbered = [f"{i+1}.  {item}" for i, item in enumerate(items)]
                instr.elements.append(self._bullet_element(el, numbered, mods))

    def _layout_closing(self, slide: FilledSlide, bp: SlideBlueprint,
                        mods: dict, instr: RenderInstruction) -> None:
        bullets = self._extract_bullets(slide)
        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.key == "takeaways" and bullets:
                instr.elements.append(self._bullet_element(el, bullets, mods))
            elif el.key == "contact":
                # Could be extended with contact info
                pass

    def _layout_generic(self, slide: FilledSlide, bp: SlideBlueprint,
                        mods: dict, instr: RenderInstruction) -> None:
        """Fallback layout for any unhandled type."""
        for el in bp.elements:
            if el.key == "headline":
                instr.elements.append(self._text_element(el, slide.headline, mods, "headline"))
            elif el.is_shape:
                instr.elements.append(self._shape_element(el))

    # ── Helpers ──

    def _text_element(self, el: ElementBlueprint, text: str, mods: dict,
                      role: str = "") -> RenderElement:
        size = el.font_size_pt
        if role == "headline":
            size = int(size * mods.get("headline_size", 1.0))
        elif role == "":
            size = int(size * mods.get("body_size", 1.0))

        # Apply line spacing modifier for more breathing room
        spacing = el.line_spacing * mods.get("line_spacing", 1.0)

        # Use blueprint key as semantic role so the renderer can apply
        # the correct typography level (card_title_0 → "card_title", etc.)
        semantic_role = role if role else el.key

        return RenderElement(
            element_type=semantic_role,
            content=text,
            position=ElementPosition(
                left_cm=el.x_cm, top_cm=el.y_cm,
                width_cm=el.w_cm, height_cm=el.h_cm,
            ),
            style=ElementStyle(
                font_family=self.font_family,
                font_size_pt=size,
                font_color=self._resolve_color(el.font_color),
                bold=el.bold,
                alignment=el.alignment,
                vertical_alignment=el.v_alignment,
                line_spacing=spacing,
            ),
        )

    def _bullet_element(self, el: ElementBlueprint, items: list[str],
                        mods: dict) -> RenderElement:
        size = int(el.font_size_pt * mods.get("body_size", 1.0))
        spacing = el.line_spacing * mods.get("line_spacing", 1.0)
        return RenderElement(
            element_type="bullets",
            content=items,
            position=ElementPosition(
                left_cm=el.x_cm, top_cm=el.y_cm,
                width_cm=el.w_cm, height_cm=el.h_cm,
            ),
            style=ElementStyle(
                font_family=self.font_family,
                font_size_pt=size,
                font_color=self._resolve_color(el.font_color),
                line_spacing=spacing,
            ),
        )

    def _shape_element(self, el: ElementBlueprint) -> RenderElement:
        return RenderElement(
            element_type="shape",
            content={"fill": self._resolve_color(el.shape_fill),
                     "corner_radius_cm": el.corner_radius_cm},
            position=ElementPosition(
                left_cm=el.x_cm, top_cm=el.y_cm,
                width_cm=el.w_cm, height_cm=el.h_cm,
            ),
        )

    def _resolve_color(self, color: str) -> str:
        if color == "accent":
            return self.accent_color
        if color == "accent_light":
            # Lighten accent by mixing with white
            return self._lighten(self.accent_color, 0.85)
        if color == "accent_dark":
            return self._darken(self.accent_color, 0.3)
        return color

    def _resolve_bg(self, bg: str) -> str:
        if bg == "accent_dark":
            return self._darken(self.accent_color, 0.15)
        return bg

    def _extract_bullets(self, slide: FilledSlide) -> list[str]:
        for cb in slide.content_blocks:
            if isinstance(cb, BulletsBlock):
                result = []
                for item in cb.items:
                    if item.bold_prefix:
                        result.append(f"**{item.bold_prefix}** {item.text}")
                    else:
                        result.append(item.text)
                return result
        return []

    def _extract_text(self, slide: FilledSlide) -> str:
        for cb in slide.content_blocks:
            if isinstance(cb, TextBlock):
                return cb.text
        return ""

    def _redistribute_element(self, el: ElementBlueprint, idx: int,
                              total: int) -> ElementBlueprint:
        """Recalculate horizontal position for dynamic element count (KPIs, etc.)."""
        pad = 1.8
        available = 25.4 - 2 * pad
        gap = 0.6
        item_w = (available - (total - 1) * gap) / total
        new_x = pad + idx * (item_w + gap)
        return ElementBlueprint(**{**el.__dict__, "x_cm": new_x, "w_cm": item_w})

    def _redistribute_timeline(self, el: ElementBlueprint, idx: int,
                               total: int) -> ElementBlueprint:
        """Redistribute timeline elements evenly."""
        pad = 2.5
        available = 25.4 - 2 * pad
        spacing = available / max(total - 1, 1) if total > 1 else 0
        new_x = pad + idx * spacing - el.w_cm / 2
        return ElementBlueprint(**{**el.__dict__, "x_cm": new_x})

    @staticmethod
    def _lighten(hex_color: str, factor: float) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _darken(hex_color: str, factor: float) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))
        return f"#{r:02x}{g:02x}{b:02x}"
