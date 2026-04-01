# Architecture Documentation

This directory contains the architectural documentation for the Slidegenerator project.

## Documents

- [Current State](current-state.md) — Analysis of the existing architecture
- [Target Architecture](target-architecture.md) — Recommended target architecture with dual-mode generation
- [Refactoring Roadmap](refactoring-roadmap.md) — Phased migration plan

## Architecture Decision Records (ADRs)

- [ADR-001: Presentation Generation Modes](adr/ADR-001-presentation-generation-modes.md)
- [ADR-002: Rendering Strategy](adr/ADR-002-rendering-strategy.md)
- [ADR-003: Template Management](adr/ADR-003-template-management.md)
- [ADR-004: API and Job Model](adr/ADR-004-api-and-job-model.md)
- [ADR-005: Technology Stack Decision](adr/ADR-005-technology-stack-decision.md)

## Key Principles

1. **Evolution over Big Bang** — Incremental migration, no breaking changes
2. **Two Modes** — Design Mode (visual excellence) + Template Mode (corporate reliability)
3. **Python for PPTX** — python-pptx is the best tool for PowerPoint manipulation
4. **NestJS as Gateway** — API orchestration, chat, job management
5. **Deterministic where possible** — AI assists, but layout and rendering are code-controlled
6. **Template safety** — Corporate templates must never be corrupted
