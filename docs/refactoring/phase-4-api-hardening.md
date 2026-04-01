# Phase 4: API Hardening

## Goal
Stabilize the API for external consumers with proper validation, error handling, and documentation.

## Work Packages

### A-01: Unified Generation Endpoint
Merge V1 and V2 endpoints into single `POST /api/v1/generate`:
```python
class GenerateRequest(BaseModel):
    prompt: str
    mode: Literal["design", "template"] = "design"
    template_id: str | None = None
    audience: str = "management"
    image_style: str = "minimal"
    accent_color: str = "#2563EB"
    font_family: str = "Calibri"
    document_text: str = ""
```

### A-02: Request Validation
- `mode=template` requires `template_id`
- `template_id` must exist in registry
- `prompt` must not be empty
- Return 400 with structured error if invalid

### A-03: External API Mode Support
Add `mode` parameter to `generate-deck` endpoint:
- Default: "design" (backwards compatible)
- "template" requires `template_id`

### A-04: Structured Error Codes
Replace string error messages with structured errors:
```json
{
  "error_code": "TEMPLATE_NOT_FOUND",
  "message": "Template 'xyz' not found in registry",
  "details": {"template_id": "xyz"}
}
```

### O-01: Correlation IDs
- Generate request ID on entry
- Pass through all log messages
- Include in SSE events
- Return in response headers

### O-02: OpenAPI Documentation
- Add proper OpenAPI descriptions to all endpoints
- Document request/response models
- Include example values

## Acceptance Criteria
- [ ] Single generation endpoint handles both modes
- [ ] Invalid requests return 400 with clear error
- [ ] External API supports mode parameter
- [ ] Error responses have machine-readable codes
- [ ] All requests have correlation IDs in logs

## Risk: Low
API changes are additive. Old endpoints kept until clients migrate.
