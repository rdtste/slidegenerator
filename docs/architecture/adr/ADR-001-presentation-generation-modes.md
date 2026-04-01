# ADR-001: Two Presentation Generation Modes

## Status
Accepted

## Date
2026-04-01

## Context
The application currently has two separate generation pipelines (V1 Markdown-based, V2 AI-pipeline) that evolved independently. Users need two distinct capabilities:

1. **Visually excellent presentations** — modern, well-designed, AI-driven content
2. **Robust corporate template filling** — deterministic, placeholder-based, enterprise-safe

These are fundamentally different use cases with different quality criteria and risk profiles.

## Decision
Introduce two explicit generation modes:

### Design Mode
- AI-driven 8-stage pipeline (evolved from V2)
- Focus on visual quality, storyline, typography
- Template optional (provides theme colors/fonts)
- Blueprint-based layout with theme-awareness
- LLM assists with content and slide planning

### Template Mode
- Deterministic pipeline (evolved from V1)
- Focus on corporate compliance and reliability
- Template required (defines all layouts and constraints)
- Placeholder-based filling using analyzed template profile
- No LLM for layout or positioning decisions
- Content mapped to template slots via analyzed PlaceholderMapping

### Shared Foundation
- Unified content model (`SlideSpec`, `ContentBlock`)
- Shared request model (`PresentationRequest` with `mode` field)
- Single orchestrator with mode-based dispatch
- Common template registry and analysis infrastructure

## Consequences
- Clear separation of concerns between visual quality and template compliance
- Users choose the appropriate mode for their use case
- Template Mode can guarantee deterministic output
- Design Mode can be improved independently without risking template stability
- API gains a `mode` parameter (default: "design" for backwards compatibility)

## Alternatives Considered
1. **Single unified pipeline** — Too complex, conflicting quality criteria
2. **Completely separate services** — Code duplication, no shared models
3. **Template-only with "design template"** — Limits visual freedom
