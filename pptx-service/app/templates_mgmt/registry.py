"""Template Registry — central management for template metadata and lookup.

Reads from existing .meta.json and .profile.json files, providing a
unified view of all registered templates with their analysis state.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import settings
from app.templates_mgmt.models import (
    TemplateDescriptor,
    TemplatePlaceholderMap,
    LayoutMapping,
    PlaceholderSlot,
)

logger = logging.getLogger(__name__)


class FileTemplateRegistry:
    """File-based template registry reading from the templates directory.

    This is the initial implementation that reads from existing
    .meta.json and .profile.json files alongside template files.
    """

    def __init__(self, templates_dir: Path | None = None):
        self._dir = templates_dir or settings.templates_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def get(self, template_id: str) -> TemplateDescriptor | None:
        """Get a template descriptor by ID."""
        path = self._find_template_file(template_id)
        if not path:
            return None
        return self._build_descriptor(template_id, path)

    def list_all(self) -> list[TemplateDescriptor]:
        """List all registered templates."""
        descriptors: list[TemplateDescriptor] = []
        seen: set[str] = set()

        for pattern in ("*.pptx", "*.potx"):
            for path in sorted(self._dir.glob(pattern)):
                # Skip versioned files (e.g., template.v1.pptx)
                if ".v" in path.stem and path.stem.split(".v")[-1].isdigit():
                    continue
                tid = path.stem
                if tid in seen:
                    continue
                seen.add(tid)
                desc = self._build_descriptor(tid, path)
                if desc:
                    descriptors.append(desc)

        return descriptors

    def register(self, template_id: str, metadata: dict) -> None:
        """Register or update template metadata."""
        meta_path = self._dir / f"{template_id}.meta.json"
        existing = self._load_meta(template_id)
        existing.update(metadata)
        meta_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        logger.info(f"Registry updated: {template_id}")

    def get_placeholder_map(self, template_id: str) -> TemplatePlaceholderMap | None:
        """Get the analyzed placeholder mapping for a template.

        Reads from .profile.json and converts layout_catalog entries
        into structured LayoutMapping objects.
        """
        profile = self._load_profile(template_id)
        if not profile:
            return None

        layouts: list[LayoutMapping] = []
        for ld in profile.get("layout_catalog", []):
            # Determine semantic type from layout analysis
            semantic_type = ld.get("mapped_type", "")
            if not semantic_type:
                semantic_type = self._infer_semantic_type(ld)

            # Profile uses both "index" (from TemplateProfile) and "layout_index" (from AI analysis)
            layout_idx = ld.get("layout_index", ld.get("index", 0))
            layout_name = ld.get("layout_name", ld.get("name", ""))

            slots: list[PlaceholderSlot] = []
            for ph in ld.get("placeholder_details", []):
                ph_type_name = ph.get("type", "")
                role = self._ph_type_to_role(ph_type_name)
                if role:
                    slots.append(PlaceholderSlot(
                        role=role,
                        ph_index=ph.get("index", 0),
                        ph_type=self._ph_type_name_to_int(ph_type_name),
                        max_chars=ld.get("title_max_chars", 0) if role == "title" else ld.get("max_chars_per_bullet", 0),
                        width_cm=ph.get("width_cm", 0),
                        height_cm=ph.get("height_cm", 0),
                        position=ph.get("position", ""),
                    ))

            if semantic_type and semantic_type != "unused":
                layouts.append(LayoutMapping(
                    layout_index=layout_idx,
                    layout_name=layout_name,
                    semantic_type=semantic_type,
                    slots=slots,
                    max_bullets=ld.get("max_bullets", 0),
                    max_chars_per_bullet=ld.get("max_chars_per_bullet", 0),
                    title_max_chars=ld.get("title_max_chars", 0),
                ))

        if not layouts:
            return None

        desc = self.get(template_id)
        return TemplatePlaceholderMap(
            template_id=template_id,
            template_version=desc.version if desc else 1,
            layouts=layouts,
        )

    # ── Internal helpers ──

    def _find_template_file(self, template_id: str) -> Path | None:
        for ext in (".pptx", ".potx"):
            path = self._dir / f"{template_id}{ext}"
            if path.is_file():
                return path
        return None

    def _build_descriptor(self, template_id: str, path: Path) -> TemplateDescriptor | None:
        meta = self._load_meta(template_id)
        profile = self._load_profile(template_id)

        return TemplateDescriptor(
            id=template_id,
            name=meta.get("name", template_id.replace("_", " ").replace("-", " ").title()),
            filename=path.name,
            version=meta.get("version", 1),
            scope=meta.get("scope", "global"),
            session_id=meta.get("sessionId"),
            uploaded_at=meta.get("uploadedAt", ""),
            profile_available=profile is not None,
            layout_count=len(profile.get("layout_catalog", [])) if profile else 0,
            supported_types=profile.get("supported_layout_types", []) if profile else [],
        )

    def _load_meta(self, template_id: str) -> dict:
        meta_path = self._dir / f"{template_id}.meta.json"
        if meta_path.is_file():
            try:
                return json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning(f"Corrupt meta for {template_id}")
        return {"scope": "global"}

    def _load_profile(self, template_id: str) -> dict | None:
        profile_path = self._dir / f"{template_id}.profile.json"
        if not profile_path.is_file():
            return None
        try:
            return json.loads(profile_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning(f"Corrupt profile for {template_id}")
            return None

    @staticmethod
    def _infer_semantic_type(layout_detail: dict) -> str:
        """Infer semantic type from placeholder types when not explicitly mapped."""
        ph_types = set(layout_detail.get("placeholder_types", []))
        has_picture = layout_detail.get("has_picture", False)
        has_chart = layout_detail.get("has_chart", False)

        if has_picture:
            return "image"
        if has_chart:
            return "chart"
        if ph_types == {"TITLE"} or ph_types == {"TITLE", "SUBTITLE"}:
            return "title"
        if "OBJECT" in ph_types and ph_types - {"TITLE", "OBJECT", "TITLE_OR_CENTER"} == set():
            obj_count = layout_detail.get("placeholder_types", []).count("OBJECT")
            if obj_count >= 2:
                return "two_column"
            return "content"
        if "TITLE" in ph_types:
            return "section"
        return ""

    @staticmethod
    def _ph_type_to_role(ph_type_name: str) -> str:
        """Convert placeholder type name to semantic role."""
        mapping = {
            "TITLE": "title",
            "TITLE_OR_CENTER": "title",
            "SUBTITLE": "subtitle",
            "BODY": "body",
            "OBJECT": "content",
            "PICTURE": "image",
            "CHART": "chart",
            "TABLE": "table",
        }
        return mapping.get(ph_type_name, "")

    @staticmethod
    def _ph_type_name_to_int(ph_type_name: str) -> int:
        """Convert placeholder type name to OOXML integer constant."""
        mapping = {
            "TITLE_OR_CENTER": 0,
            "TITLE": 1,
            "BODY": 2,
            "SUBTITLE": 3,
            "OBJECT": 7,
            "TABLE": 10,
            "CHART": 12,
            "PICTURE": 18,
        }
        return mapping.get(ph_type_name, 0)
