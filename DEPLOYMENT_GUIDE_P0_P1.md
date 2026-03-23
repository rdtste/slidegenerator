"""Deployment and Testing Guide for P0+P1 PPTX Skill Integration

## Overview

This guide covers deploying the P0 (Content Validation, Visual QA, Image Error Handling)
and P1 (Design Validation, Template Validation, Design QA) enhancements to the
slidegenerator pptx-service.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Generation Request                            │
│                         (Markdown)                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ P0: Content │
                    │ Validation  │  ← Markdown structure QA
                    └──────┬──────┘
                           │
                    ┌──────▼────────────┐
                    │ P1: Template      │
                    │ Pre-flight Check  │  ← Template compatibility
                    └──────┬────────────┘
                           │
                 ┌─────────▼─────────┐
                 │ Parse Markdown    │
                 │ Generate PPTX     │
                 └─────────┬─────────┘
                           │
                    ┌──────▼──────┐
                    │ P0: Visual  │
                    │ QA Pipeline │  ← PPTX→PDF→JPEG inspection
                    └──────┬──────┘
                           │
                    ┌──────▼──────────┐
                    │ P1: Design QA   │
                    │ & Scoring       │  ← Design rules + scores
                    └──────┬──────────┘
                           │
                    ┌──────▼──────┐
                    │  Response   │
                    │  + SSE Msgs │
                    └─────────────┘
```

## Prerequisites

- Docker & Docker Compose
- Python 3.12+
- LibreOffice (for soffice CLI)
- Poppler utilities (for pdftoppm CLI)
- 4+ GB RAM (for LibreOffice)

## Installation (Local Development)

### 1. Set up virtual environment

```bash
cd pptx-service
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing
```

### 2. Install system dependencies

**macOS:**
```bash
brew install libreoffice poppler
```

**Ubuntu/Debian:**
```bash
sudo apt-get install libreoffice poppler-utils
```

**CentOS/RHEL:**
```bash
sudo yum install libreoffice poppler-utils
```

## Testing

### Run P0+P1 Integration Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/test_p0_p1_pipeline.py -v

# Run with coverage
pytest tests/test_p0_p1_pipeline.py --cov=app --cov-report=html
```

### Expected Test Results

All tests should pass:
- ✅ Content validation tests
- ✅ Design validation tests
- ✅ Template validation tests
- ✅ Design QA service tests
- ✅ Pipeline integration tests

### Manual Testing (Development)

```bash
# Start pptx-service locally
cd pptx-service
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Test endpoint:
```bash
curl -X POST http://localhost:8000/api/generate-stream \
  -H "Content-Type: application/json" \
  -d '{
    "markdown": "# Slide 1\n## Content: Test",
    "template_id": "2023_REWEdigital_Master_DE_01"
  }'
```

Expected SSE response flow:
1. `validating` (1%) - Content validation
2. `parsing` (5%) - Markdown parsing
3. `template_check` (12%) - Template validation
4. `parsed` (10%) - Processing complete
5. `visual_qa` (85%) - Visual QA pipeline
6. `design_qa` (90%) - Design rule checking
7. `complete` (100%) - Generation done

## Docker Deployment

### Build Image

```bash
# From slidegenerator root
docker build -f pptx-service/Dockerfile -t slidegenerator/pptx-service:p0-p1-latest pptx-service/

# Verify build
docker run --rm slidegenerator/pptx-service:p0-p1-latest python3 -c "
import app.services.markdown_validator
import app.services.visual_qa_service
import app.services.design_validator
print('✅ All P0+P1 modules imported successfully')
"
```

### Run with Docker Compose

```bash
# From slidegenerator root
docker-compose -f docker-compose.yml up pptx-service

# Or production compose
docker-compose -f docker-compose.prod.yml up pptx-service
```

### Verify Container Health

```bash
# Health check
curl http://localhost:8000/api/health

# Check logs for P0+P1 initialization
docker logs slidegenerator-pptx-service-1 | grep -E "P0|P1|Validator|Design QA"
```

## Monitoring & Logs

### Key Log Messages to Look For

**P0 Content Validation:**
```
[Content Validator] Initialized
[Content Validator] Validation result: X issues
Content validation failed: X issues  # If validation fails
```

**P0 Visual QA:**
```
[Visual QA] Converting PPTX to PDF: ...
[Visual QA] Converting PDF to JPEG images (150 DPI)...
[Visual QA] Analyzing N slide images...
[Visual QA] Complete: N slides, X errors, Y warnings
```

**P1 Design Validation:**
```
[Design Validator] Initialized for template: ...
[Design Validator] Exception during validation: ...
```

**P1 Template Validation:**
```
[Template Validator] Initialized with templates_dir: ...
[Template Validation] Template validation for template_id...
```

**P1 Design QA:**
```
[Design QA] Template validation for ...
[Design QA] Design system validation...
[Design QA] Complete: N issues, design_score=XX, is_valid=...
```

### SSE Event Monitoring

Monitor real-time generation with event streaming:

```bash
# macOS/Linux
curl -N http://localhost:8000/api/generate-stream \
  -H "Content-Type: application/json" \
  -d '{"markdown": "...", "template_id": "..."}' | grep -oP 'event: \K[^ ]+'

# Or with jq for JSON parsing
curl -N http://localhost:8000/api/generate-stream \
  -H "Content-Type: application/json" \
  -d '{"markdown": "...", "template_id": "..."}' | \
  sed 's/^data: //' | jq '.step'
```

## Performance Benchmarks

Expected timings (on 4-core machine):

| Step | Time | Notes |
|------|------|-------|
| Content Validation | 50-100ms | Markdown parsing + rule checks |
| Template Validation | 100-200ms | File integrity + metadata load |
| PPTX Generation | 2-5s | Depends on slide count |
| Visual QA (5 slides) | 3-8s | PDF conversion + image analysis |
| Design QA | 500-1000ms | Design rule evaluation |
| **Total (5 slides)** | **6-15s** | End-to-end generation |

## Troubleshooting

### Issue: LibreOffice timeout in Visual QA

**Symptoms:**
```
[Visual QA] Pipeline failed: soffice conversion timed out
```

**Solution:**
1. Increase timeout in `app/utils/soffice_wrapper.py`: `TIMEOUT_SECS = 60`
2. Ensure `/tmp` has sufficient disk space
3. Check system RAM availability

### Issue: PDF to JPEG conversion fails

**Symptoms:**
```
[Visual QA] Pipeline failed: pdftoppm conversion error
```

**Solution:**
1. Verify Poppler installed: `which pdftoppm`
2. Test manually: `pdftoppm -jpeg -r 150 test.pdf output`
3. In Docker, ensure `poppler-utils` included in Dockerfile

### Issue: Design QA module missing

**Symptoms:**
```
ModuleNotFoundError: No module named 'app.services.design_qa'
```

**Solution:**
1. Verify all 3 P1 files exist:
   - `app/services/design_validator.py`
   - `app/services/template_validator.py`
   - `app/services/design_qa.py`
2. Verify `generate.py` imports look like:
   ```python
   from app.services.design_qa import DesignQAService
   ```

## Deployment Checklist

- [ ] All P0 modules created & syntax validated
- [ ] All P1 modules created & syntax validated
- [ ] `requirements.txt` includes markitdown, Pillow
- [ ] `requirements-dev.txt` created with pytest
- [ ] Dockerfile includes libreoffice, poppler-utils
- [ ] Integration tests pass: `pytest tests/test_p0_p1_pipeline.py -v`
- [ ] Docker image builds successfully
- [ ] Docker container starts without errors
- [ ] Health check passes: `curl http://localhost:8000/api/health`
- [ ] Manual test of /generate-stream endpoint works
- [ ] SSE events include all expected progress steps
- [ ] Log messages show P0/P1 initialization
- [ ] Performance meets benchmarks (< 20s for 10-slide presentation)

## Rollback Plan

If P0+P1 causes issues in production:

1. **Immediate:** Stop container
   ```bash
   docker-compose stop pptx-service
   ```

2. **Revert:** Deploy previous version
   ```bash
   docker pull prev-image-tag
   docker-compose up pptx-service
   ```

3. **Disable validation (emergency):** Comment out in `generate.py`:
   ```python
   # validation_result = _validator.validate(request.markdown)
   # if not validation_result.is_valid:
   #     return  # Skip validation
   ```

4. **Post-incident:** Review logs, fix issues, redeploy

## Next Steps (P2)

After P0+P1 is stable in production, implement P2:
- Job cleanup with TTL (30 min)
- Structured logging with context/metadata
- Comprehensive test coverage (unit + integration)
- Performance monitoring dashboards

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-23  
**Status:** Ready for staging deployment
"""
