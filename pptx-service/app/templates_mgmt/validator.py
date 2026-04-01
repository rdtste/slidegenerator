"""Template validator — pre-flight checks before generation.

Consolidated from app.services.template_validator into the templates_mgmt module.
"""

from __future__ import annotations

import json
import logging
import re
import zipfile
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.config import settings
from app.templates_mgmt.service import get_template_path

logger = logging.getLogger(__name__)


class TemplateLayout(BaseModel):
    """Definition of a layout in the template"""
    name: str
    placeholder_count: int
    has_image_placeholder: bool
    primary_text_color: Optional[str] = None
    background_color: Optional[str] = None


class TemplateMetadata(BaseModel):
    """Template metadata and specifications"""
    id: str
    name: str
    version: str
    layouts: list[TemplateLayout] = Field(default_factory=list)
    color_palette: dict[str, str] = Field(default_factory=dict)
    fonts: list[str] = Field(default_factory=list)


class TemplateValidationIssue(BaseModel):
    """Issue found during template pre-flight validation"""
    issue_type: str  # "missing_layout", "color_mismatch", "metadata_missing", "invalid_format"
    severity: str  # "error", "warning"
    message: str
    details: Optional[str] = None


class TemplateValidationResult(BaseModel):
    """Result of template pre-flight validation"""
    template_id: str
    is_valid: bool
    issues: list[TemplateValidationIssue] = Field(default_factory=list)
    metadata: Optional[TemplateMetadata] = None

    @property
    def error_count(self) -> int:
        return len([i for i in self.issues if i.severity == "error"])

    @property
    def warning_count(self) -> int:
        return len([i for i in self.issues if i.severity == "warning"])


class TemplateValidator:
    """Pre-flight validation for templates before PPTX generation."""

    def __init__(self, templates_dir: str | None = None):
        resolved_dir = Path(templates_dir) if templates_dir else settings.templates_dir
        self.templates_dir = resolved_dir
        logger.info(f"[Template Validator] Initialized with templates_dir: {self.templates_dir}")

    def validate_template(self, template_id: str) -> TemplateValidationResult:
        """Pre-flight check of a template before generation."""
        issues = []
        metadata = None

        # Check 1: Template file exists (.potx or .pptx)
        template_path = self._find_template_file(template_id)
        if template_path is None:
            issues.append(TemplateValidationIssue(
                issue_type="missing_layout",
                severity="warning",
                message=(
                    f"Template '{template_id}' not found in {self.templates_dir}. "
                    "Using default template fallback."
                ),
                details="Expected .potx or .pptx file"
            ))
            return TemplateValidationResult(
                template_id=template_id,
                is_valid=True,
                issues=issues
            )

        # Check 2: Metadata file exists
        metadata_path = template_path.parent / f"{template_id}.meta.json"
        if metadata_path.exists():
            try:
                metadata = self._load_metadata(metadata_path)
            except Exception as e:
                issues.append(TemplateValidationIssue(
                    issue_type="metadata_missing",
                    severity="warning",
                    message="Could not load template metadata",
                    details=str(e)
                ))
        else:
            issues.append(TemplateValidationIssue(
                issue_type="metadata_missing",
                severity="warning",
                message=f"Metadata file not found: {metadata_path}",
                details="Proceeding without metadata (may affect design validation)"
            ))
            metadata = TemplateMetadata(id=template_id, name=template_id, version="unknown")

        # Check 3: Required layouts
        if metadata:
            required_layouts = ["title", "content"]
            available_layouts = {l.name for l in metadata.layouts}
            for required in required_layouts:
                if required not in available_layouts:
                    issues.append(TemplateValidationIssue(
                        issue_type="missing_layout",
                        severity="warning",
                        message=f"Template missing recommended layout: {required}",
                        details=f"Available layouts: {', '.join(available_layouts)}"
                    ))

        # Check 4: Color palette viability
        if metadata and metadata.color_palette:
            color_issues = self._validate_color_palette(metadata)
            issues.extend(color_issues)

        # Check 5: File integrity (try to read as ZIP)
        file_issues = self._validate_file_integrity(template_path)
        issues.extend(file_issues)

        is_valid = all(i.severity != "error" for i in issues)

        return TemplateValidationResult(
            template_id=template_id,
            is_valid=is_valid,
            issues=issues,
            metadata=metadata
        )

    def _load_metadata(self, metadata_path: Path) -> TemplateMetadata:
        """Load template metadata from JSON file."""
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        layouts = []
        for layout_def in data.get("layouts", []):
            layouts.append(TemplateLayout(**layout_def))

        return TemplateMetadata(
            id=data.get("id", "unknown"),
            name=data.get("name", "unknown"),
            version=data.get("version", "1.0"),
            layouts=layouts,
            color_palette=data.get("color_palette", {}),
            fonts=data.get("fonts", [])
        )

    def _validate_color_palette(self, metadata: TemplateMetadata) -> list[TemplateValidationIssue]:
        """Check color palette for viability."""
        issues = []
        colors = metadata.color_palette

        required_colors = ["primary", "accent"]
        for required in required_colors:
            if required not in colors:
                issues.append(TemplateValidationIssue(
                    issue_type="color_mismatch",
                    severity="warning",
                    message=f"Color palette missing: {required}",
                    details=f"Available: {', '.join(colors.keys())}"
                ))

        for color_name, color_value in colors.items():
            if not self._is_valid_hex_color(color_value):
                issues.append(TemplateValidationIssue(
                    issue_type="color_mismatch",
                    severity="error",
                    message=f"Invalid color format for {color_name}: {color_value}",
                    details="Color values must be hex format (e.g., #FF0000)"
                ))

        return issues

    def _validate_file_integrity(self, template_path: Path) -> list[TemplateValidationIssue]:
        """Check PPTX file integrity."""
        issues = []

        try:
            with zipfile.ZipFile(template_path, "r") as z:
                required_files = ["[Content_Types].xml", "ppt/presentation.xml"]
                missing = [f for f in required_files if f not in z.namelist()]
                if missing:
                    issues.append(TemplateValidationIssue(
                        issue_type="invalid_format",
                        severity="error",
                        message="PPTX file structure invalid",
                        details=f"Missing: {', '.join(missing)}"
                    ))
        except Exception as e:
            issues.append(TemplateValidationIssue(
                issue_type="invalid_format",
                severity="error",
                message="Could not read template file as PPTX",
                details=str(e)
            ))

        return issues

    def _find_template_file(self, template_id: str) -> Path | None:
        """Find template by ID using the same search behavior as generation."""
        return get_template_path(template_id)

    @staticmethod
    def _is_valid_hex_color(color: str) -> bool:
        """Check if color string is valid hex format."""
        return bool(re.match(r"^#[0-9A-Fa-f]{6}$", color))
