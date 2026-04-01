# ADR-004: API and Job Model

## Status
Accepted

## Date
2026-04-01

## Context
The current API has multiple generation endpoints:
- `POST /generate` (V1, sync)
- `POST /generate-stream` (V1, SSE)
- `POST /generate-v2` (V2, SSE)
- `POST /export/start` (backend, V1 via pptx-service)
- `POST /export/start-v2` (backend, V2 via pptx-service)
- `POST /export/generate-deck` (external API, V2)

Jobs are stored in memory and lost on restart.

## Decision

### Unified Generation API (pptx-service)
Single endpoint with mode parameter:
```
POST /api/v1/generate
{
  "prompt": "...",
  "mode": "design" | "template",
  "template_id": "...",       // required for template mode
  "audience": "management",
  "image_style": "minimal",
  "accent_color": "#2563EB",
  "font_family": "Calibri",
  "document_text": ""
}
```

Response: SSE stream with progress events, final `complete` event with `fileId`.

### Backend API (NestJS)
- `POST /api/v1/export/start` — unified (replaces start + start-v2)
- `POST /api/v1/export/generate-deck` — external API (adds `mode` parameter)
- Existing SSE progress and download endpoints remain

### Job Model
- Keep in-memory for now (adequate for Cloud Run with minScale=1)
- Add job cleanup (existing job_cleanup_manager.py)
- Future: Redis or Firestore if multi-instance scaling needed

### Request Validation
- `mode=template` requires `template_id`
- `template_id` must exist in registry
- Content validated against template constraints in template mode

## Consequences
- Simpler API surface (fewer endpoints)
- External integrations use one endpoint with mode parameter
- Backwards compatibility: `mode` defaults to "design"
- V1 endpoints deprecated but kept until Template Mode is stable

## Migration
1. Add `mode` parameter to existing V2 endpoint
2. Route `mode=template` to Template Mode pipeline
3. Deprecate V1 endpoints
4. Update external API documentation
