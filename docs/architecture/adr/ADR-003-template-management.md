# ADR-003: Template Management Architecture

## Status
Accepted

## Date
2026-04-01

## Context
Templates are currently managed across multiple disconnected components:
- `template_service.py` (CRUD, loading)
- `profile_service.py` (deep analysis)
- `theme_service.py` (CSS extraction)
- `templates.service.ts` (NestJS — upload, scope, sync)

The V2 renderer uses a hardcoded `_REWE_LAYOUT_MAP` instead of the analyzed profile.
There is no versioning — uploading a new template overwrites the old one.

## Decision
Consolidate template management into a cohesive module with:

### Template Registry
- Central registry tracking all templates with metadata
- `TemplateDescriptor`: id, name, version, scope, brand, analyzed profile reference
- JSON-based registry file alongside template files
- Version counter incremented on re-upload

### Template Analyzer
- Unified analysis combining current profile_service and theme_service
- Produces `TemplateProfile` with:
  - ColorDNA, TypographyDNA
  - Per-layout `PlaceholderMapping` (which placeholder serves which semantic role)
  - Layout constraints (max chars, max bullets, content area dimensions)
  - Supported slide types
- Analysis result stored as `.profile.json` alongside template file
- Analysis triggered on upload and on-demand

### Placeholder Mapping
- Structured mapping from semantic roles (title, body, bullets, image) to template placeholder indices
- Replaces heuristic keyword scoring with analyzed, stored mapping
- Fallback to keyword scoring when analysis is unavailable

### Template Versioning
- Version counter in `.meta.json`
- Old versions retained as `{id}.v{n}.{ext}`
- Latest version always at `{id}.{ext}`

### Storage Abstraction
- `TemplateStorage` protocol for filesystem operations
- Current: local filesystem / GCS FUSE
- Future: direct GCS API if needed

## Consequences
- Single source of truth for template metadata
- V2 renderer can use analyzed profile instead of hardcoded maps
- Template re-upload doesn't destroy previous versions
- Multi-brand support via template grouping
- Analysis data persisted and reusable across requests

## Migration Path
1. Introduce `TemplateDescriptor` and registry alongside existing .meta.json
2. Refactor profile_service into templates/analyzer.py
3. Update renderers to use analyzed PlaceholderMapping
4. Add versioning on upload
5. Deprecate hardcoded layout maps
