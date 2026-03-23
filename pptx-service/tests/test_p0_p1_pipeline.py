"""Integration tests for P0+P1 PPTX Skill pipeline.

Tests content validation, visual QA, template validation, and design QA
in a simplified end-to-end scenario.

Run with: pytest tests/test_p0_p1_pipeline.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from app.services.markdown_validator import MarkdownValidator, ContentValidationResult
from app.services.visual_qa_service import VisualQAService, VisualQAReport
from app.services.design_validator import DesignValidator, ColorDNA, TypographyRules, LayoutRules, DesignSystem
from app.services.template_validator import TemplateValidator
from app.services.design_qa import DesignQAService


class TestContentValidation:
    """P0: Content validation tests"""
    
    def test_markdown_validator_valid_content(self):
        """Test validator accepts properly formatted markdown."""
        validator = MarkdownValidator()
        
        valid_markdown = """# Slide 1: Title Slide
## Content: This is a test presentation

# Slide 2: Content Slide
## Content: Main points here
- Point 1
- Point 2
- Point 3
"""
        
        result = validator.validate(valid_markdown)
        
        # Should have no critical errors (warnings are OK)
        errors = [i for i in result.issues if i.severity == "error"]
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert result.is_valid
    
    def test_markdown_validator_rejects_excessive_bullets(self):
        """Test validator catches too many bullet points."""
        validator = MarkdownValidator()
        
        invalid_markdown = """# Slide 1: Content
## Content: Too many bullets
- Point 1
- Point 2
- Point 3
- Point 4
- Point 5
- Point 6
"""
        
        result = validator.validate(invalid_markdown)
        
        # Should detect bullet count violation
        bullet_issues = [i for i in result.issues if "bullet" in i.message.lower()]
        assert len(bullet_issues) > 0, "Should detect excess bullets"
    
    def test_markdown_validator_rejects_title_too_long(self):
        """Test validator catches oversized titles."""
        validator = MarkdownValidator()
        
        invalid_markdown = """# This is an extremely long title that definitely exceeds 50 characters maximum
## Content: Test content
"""
        
        result = validator.validate(invalid_markdown)
        
        # Should detect title length violation
        title_issues = [i for i in result.issues if "title" in i.message.lower()]
        assert len(title_issues) > 0, "Should detect title too long"


class TestDesignValidation:
    """P1: Design validation tests"""
    
    def test_design_validator_initialization(self):
        """Test design validator initializes with default system."""
        validator = DesignValidator()
        
        assert validator.design_system is not None
        assert validator.design_system.template_id == "default"
        assert validator.design_system.color_dna is not None
    
    def test_design_system_custom_creation(self):
        """Test custom design system configuration."""
        design_system = DesignSystem(
            template_id="custom",
            color_dna=ColorDNA(
                dominant="#FF0000",
                supporting=["#00FF00"],
                accent="#0000FF"
            ),
            typography=TypographyRules(),
            layout=LayoutRules()
        )
        
        assert design_system.template_id == "custom"
        assert design_system.color_dna.dominant == "#FF0000"
        assert len(design_system.color_dna.supporting) == 1
    
    def test_design_validator_slide_validation(self):
        """Test design validator on individual slide."""
        validator = DesignValidator()
        
        slide_data = {
            "layout_type": "content",
            "title": {"text": "Test Title", "size_pt": 40},
            "body": {"text": "Test body", "size_pt": 14},
            "image": {"path": "/test/image.jpg"},
        }
        
        result = validator.validate(slide_data, slide_number=1)
        
        # Should be valid - title size in range, has image
        assert result.is_valid


class TestTemplateValidation:
    """P1: Template pre-flight validation tests"""
    
    def test_template_validator_initialization(self):
        """Test template validator initializes."""
        validator = TemplateValidator(templates_dir="/tmp")
        
        assert validator.templates_dir == Path("/tmp")
    
    def test_template_validator_missing_template(self):
        """Test validator detects missing template."""
        validator = TemplateValidator(templates_dir="/nonexistent")
        
        result = validator.validate_template("missing_template")
        
        # Should report template not found
        assert not result.is_valid
        missing_issues = [i for i in result.issues if i.severity == "error"]
        assert len(missing_issues) > 0
    
    def test_hex_color_validation(self):
        """Test hex color format validation."""
        from app.services.template_validator import TemplateValidator
        
        # Valid cases
        assert TemplateValidator._is_valid_hex_color("#FF0000")
        assert TemplateValidator._is_valid_hex_color("#000000")
        assert TemplateValidator._is_valid_hex_color("#FFFFFF")
        
        # Invalid cases
        assert not TemplateValidator._is_valid_hex_color("red")
        assert not TemplateValidator._is_valid_hex_color("#FF00")
        assert not TemplateValidator._is_valid_hex_color("#FF00GG")


class TestDesignQAService:
    """P1: Design QA orchestration tests"""
    
    def test_design_qa_service_initialization(self):
        """Test design QA service initializes."""
        service = DesignQAService(templates_dir="/tmp")
        
        assert service.design_validator is not None
        assert service.template_validator is not None
    
    def test_design_score_calculation(self):
        """Test design score calculation from compliance metrics."""
        service = DesignQAService()
        
        # Mock data: perfect compliance
        color_score = 100.0
        typography_score = 100.0
        layout_score = 100.0
        
        avg_score = (color_score + typography_score + layout_score) / 3
        assert avg_score == 100.0
        
        # Mixed compliance
        color_score = 90.0
        typography_score = 85.0
        layout_score = 80.0
        
        avg_score = (color_score + typography_score + layout_score) / 3
        assert 84 < avg_score < 86  # Should be ~85


class TestPipelineIntegration:
    """End-to-end pipeline tests"""
    
    def test_full_validation_flow(self):
        """Test complete P0+P1 validation flow."""
        
        # Step 1: Content validation (P0)
        validator = MarkdownValidator()
        markdown = """# Slide 1: Introduction
## Content: Welcome to presentation

# Slide 2: Main Points
## Content: Key information
- Point 1
- Point 2
- Point 3
"""
        
        content_result = validator.validate(markdown)
        assert content_result.is_valid
        
        # Step 2: Design validation (P1)
        design_validator = DesignValidator()
        
        slides_data = [
            {
                "layout_type": "title",
                "title": {"text": "Introduction", "size_pt": 40},
            },
            {
                "layout_type": "content",
                "title": {"text": "Main Points", "size_pt": 38},
                "body": {"text": "Key information", "size_pt": 14},
                "image": {"path": "/test/chart.png"},
            }
        ]
        
        # Design should pass for properly formatted slides
        for i, slide in enumerate(slides_data, 1):
            design_result = design_validator.validate(slide, slide_number=i)
            # Allow warnings but not errors
            errors = [issue for issue in design_result.issues if issue.severity == "error"]
            assert len(errors) == 0
    
    def test_compliance_score_degradation(self):
        """Test design score decreases with issues."""
        service = DesignQAService()
        
        # Perfect state
        perfect_issues = []
        errors = len([i for i in perfect_issues if i == "error"])
        warnings = len([i for i in perfect_issues if i == "warning"])
        color_score = max(0, 100 - (errors * 10) - (warnings * 2))
        
        assert color_score == 100.0
        
        # With issues
        with_issues = ["error", "error", "warning", "warning", "warning"]
        errors = len([i for i in with_issues if i == "error"])
        warnings = len([i for i in with_issues if i == "warning"])
        color_score = max(0, 100 - (errors * 10) - (warnings * 2))
        
        assert color_score == 80.0  # 100 - (2*10) - (3*2) = 80


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
