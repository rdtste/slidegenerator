# Generierungs-Pipeline: Alle Schritte im Detail

Dieses Dokument beschreibt jeden einzelnen Schritt beider Generierungs-Pipelines (V1 Template + V2 Design) — von der Nutzereingabe bis zur fertigen PPTX-Datei.

---

## V1 Pipeline (Template-basiert)

### Phase 0: Chat-Moderation (Backend)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 0.1 | `chat.service.ts` | **Moderator-Gespräch**: Nutzer beschreibt Thema → LLM (`MODERATOR_SYSTEM_PROMPT`) führt max. 3 Gesprächsrunden, sammelt: Thema, Fokus, Folienanzahl, Medien-Wünsche |
| 0.2 | `chat.service.ts` | **===READY=== Erkennung**: Wenn genug Kontext → LLM erzeugt `===READY===` Marker + vollständigen Generierungsauftrag (Briefing) |
| 0.3 | `chat.service.ts` | **Zielgruppen-Prompt**: Audience (team/management/customer/workshop) → spezifischer Prompt-Block mit Design-Regeln, Tonalität, bevorzugten Layoutmustern |
| 0.4 | `chat.service.ts` | **Bildstil-Prompt**: Image Style (photo/illustration/minimal/data_visual/none) → Prompt-Block mit visuellen Richtlinien |
| 0.5 | `chat.service.ts` | **Kombinations-Prompt**: Audience × ImageStyle Matrix → spezialisierter Design-Prompt (z.B. "Management + Data Visual" → KPI-Karten, Scorecards) |
| 0.6 | `chat.service.ts` | **Template-Profil-Prompt**: Falls Custom-Template → `profile.json` oder `analysis.json` → Layout-Katalog, Zeichenlimits, Design-DNA, Chart-Stil als Prompt-Kontext |

### Phase 1: Markdown-Generierung (Backend)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 1.1 | `chat.service.ts:generate()` | **System-Prompt Zusammenbau**: `BASE_SYSTEM_PROMPT` (155 Zeilen Design-Regeln) + Audience + ImageStyle + Kombination + Template-Profil |
| 1.2 | `chat.service.ts:generate()` | **LLM-Aufruf**: Gemini via OpenAI-SDK, `temperature=0.5`, `max_tokens=32768` → erzeugt strukturiertes Markdown |
| 1.3 | `chat.service.ts:generate()` | **Truncation-Check**: `finish_reason === 'length'` → Warnung loggen |
| 1.4 | `chat.service.ts:parseMarkdown()` | **Markdown → SlideDto[]**: Split an `---`, pro Slide: `<!-- layout: TYPE -->` extrahieren, `# Titel`, `## Untertitel`, `- Bullets`, `![img](placeholder)`, `<!-- notes: -->` |
| 1.5 | `chat.service.ts:validateStructure()` | **Strukturvalidierung**: Prüft Bild-Markdown auf falschen Slides, Image-Slides ohne Bild, Image-Slides ohne Bullets |
| 1.6 | `chat.service.ts:validateStructure()` | **LLM-Fix** (bei Fehlern): Zweiter Gemini-Aufruf mit `temperature=0.2` → korrigiertes Markdown. Ablehnung wenn Slides verloren (Truncation-Guard) |
| 1.7 | `chat.service.ts:validateAndFix()` | **Readability-Validierung**: Prüft Bullet-Anzahl, Bullet-Textlänge, Titel-Länge gegen Template-Constraints |
| 1.8 | `chat.service.ts:validateAndFix()` | **LLM-Fix** (bei Overflow): Dritter Gemini-Aufruf → kürzt Texte, splittet übervolle Slides. Truncation-Guard |

### Phase 2: Export starten (Backend → PPTX-Service)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 2.1 | `export.controller.ts:startExport()` | **Job erstellen**: `POST /api/v1/export/start` → UUID-basierter Job, `ReplaySubject` für SSE |
| 2.2 | `export.service.ts:processPptxJob()` | **HTTP-Request**: `POST http://localhost:8000/api/v1/generate-stream` mit `{markdown, template_id, custom_color, custom_font}` |
| 2.3 | `export.service.ts` | **SSE-Stream lesen**: Events parsen (`progress`, `complete`, `fail`, `qa_result`), an Frontend weiterleiten |
| 2.4 | `export.service.ts` | **Heartbeat**: 15s-Intervall Keep-Alive für Cloud Run (540s Max-Timeout) |

### Phase 3: PPTX-Service — Validierung (generate.py)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 3.1 | `generate.py:generate_stream()` | **Markdown-Validierung**: `MarkdownValidator.validate()` — prüft Layout-Typ, Titel-Länge, Bullet-Anzahl, Bullet-Länge, Placeholder-Texte, Visual-Pflicht |
| 3.2 | `generate.py` | **Bei Fehler**: SSE `validation_failed` Event → Abbruch |
| 3.3 | `markdown_service.py:parse_markdown()` | **Markdown → PresentationData**: Strip Frontmatter, Split an `---`, pro Slide: Layout-Regex, H1/H2-Regex, Bullet-Regex, Image-Regex, Chart-Block-Regex, Two-Column-Parser |
| 3.4 | `generate.py` | **Template-Validierung**: `TemplateValidator.validate_template()` — prüft ob Template existiert und nutzbar ist |

### Phase 4: PPTX-Service — Qualitäts-Pipeline (pptx_service.py)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 4.1 | `pptx_service.py:generate_pptx()` | **Template laden**: `template_service.load_presentation()` → `Presentation` Objekt, 16:9 (13.333" × 7.5") |
| 4.2 | `pptx_service.py` | **Analysis-Map laden**: `{template_id}.analysis.json` → Layout-Typ → Layout-Index Mapping (KI-generiert) |
| 4.3 | `pptx_service.py` | **Title-Limits laden**: Per-Layout max. Titelzeichen aus Profil/Analyse |
| 4.4 | `pptx_service.py` | **Alle Slides entfernen**: `_remove_all_slides()` — XML-Level, behält Layouts/Masters |
| 4.5 | `pptx_service.py` | **Metadata setzen**: Titel, Autor in `core_properties` |
| 4.6 | `pptx_service.py` | **Bilder parallel generieren**: `_collect_image_descriptions()` → `_prefetch_images()` → Vertex AI Imagen 3.0 async, Cache aufbauen |
| 4.7 | **`v1_content_leak_check.py`** | **Content-Leak-Sanitierung**: 15 Regex-Patterns (Icon-Deskriptoren, Placeholder, AI-Prompts, Stock-Photo-Text) + Known-Hints-Set → betroffene Felder leeren |
| 4.8 | **`v1_slide_rules.py`** | **Slide-Validierung** (12 Regeln): V1-S001 Headline required, V1-S002 Headline max 70 chars, V1-S003 Bullet max count, V1-S004 Bullet max 60 chars, V1-S005 No generic headlines, V1-S006 Total text density, V1-S007 Image needs description, V1-S008 Chart needs data, V1-S009 Two-column needs content, V1-S010 Visual-text ratio, V1-S011 Content density (chars/cm²), V1-S012 Headline should be statement |
| 4.9 | **`v1_auto_fixes.py`** | **Auto-Fix** (wenn auto_fixable findings): Titel truncate (Word-Boundary + …), Bullets trimmen, Bullet-Text truncate, Body truncate, Column truncate |
| 4.10 | **`v1_preflight.py`** | **Preflight-Scoring** (0-100): Readability (30%), Density (30%), Hierarchy (20%), Completeness (20%). Score < 70 → SSE-Warnung |

### Phase 5: PPTX-Service — Slide-Rendering (pptx_service.py)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 5.1 | `pptx_service.py:_resolve_layout()` | **Layout-Auflösung**: 1. AI-Analysis-Map → 2. Scored Keyword Matching (Pattern + Score + Negatives + Structure Bonus) → 3. Fallback-Index |
| 5.2 | `pptx_service.py:_add_slide()` | **Closing-Check**: Closing-Layout mit Bullets aber zu schmaler Content-Area (< 12cm) → Fallback auf Content-Layout |
| 5.3 | `pptx_service.py:_add_slide()` | **Slide erstellen**: `prs.slides.add_slide(layout)` |
| 5.4 | `pptx_service.py:_add_slide()` | **Title-Limit berechnen**: Konfiguriert (Profil) → Estimated (Placeholder-Breite × 8.5) → Default 50 |
| 5.5 | `pptx_service.py:_add_slide()` | **Speaker Notes**: `slide.notes_slide.notes_text_frame.text` setzen |
| 5.6 | `pptx_service.py` | **Layout-Handler aufrufen**: Pro Layout-Typ eigener Handler: |

#### Layout-Handler im Detail:

| Handler | Was passiert |
|---------|-------------|
| `_handle_title` | TITLE-Placeholder → Titel (truncated), BODY/SUBTITLE → Subtitle, PICTURE → Image generieren + `fit_image_to_placeholder()` |
| `_handle_section` | TITLE → Titel, BODY → Subtitle, OBJECT → Bullets (optional) |
| `_handle_content` | TITLE → Titel, OBJECT → Bullets oder Body-Text mit `**bold**` Rendering |
| `_handle_two_column` | TITLE → Titel, 2× OBJECT → Left/Right Column oder Bullets 50/50 split |
| `_handle_image` | TITLE → Titel, PICTURE → Image (Imagen 3.0 oder Fallback SVG), OBJECT → Bullets/Body |
| `_handle_chart` | TITLE → Titel, Chart-JSON parsen → `generate_chart()` (matplotlib) → PICTURE/OBJECT einfügen |
| `_handle_closing` | TITLE → Titel, BODY → Subtitle, OBJECT → Bullets oder Body |

#### Rendering-Details:

| Detail | Datei | Was passiert |
|--------|-------|-------------|
| 5.7 | `pptx_service.py:_truncate_title()` | **Titel-Truncation**: Word-Boundary, Ellipsis (…), Limit aus Profil/Schätzung |
| 5.8 | `pptx_service.py:_fill_bullet_list_leveled()` | **Bullet-Rendering**: lstStyle preservieren, `buNone` → explicit Bullet-Char (•), Level 0/1, `**bold**` → echtes Bold, dynamisches Spacing (3 Bullets→14pt, 5→10pt, 7→6pt, 8+→4pt) |
| 5.9 | `image_service.py:generate_image_async()` | **Bild-Generierung**: Vertex AI Imagen 3.0, Retry mit Backoff, Style-Keywords aus Template-Profil |
| 5.10 | `image_fitting.py:fit_image_to_placeholder()` | **Bild-Fitting**: Resize + Crop auf Placeholder-Dimensionen |
| 5.11 | `chart_service.py:generate_chart()` | **Chart-Generierung**: matplotlib, 6 Typen (bar, line, pie, donut, stacked_bar, horizontal_bar), Template-Farben, transparenter Hintergrund |
| 5.12 | `pptx_service.py:_apply_custom_design()` | **Custom Design** (nur Default-Template): Akzentfarbe auf Titel-Placeholders, Custom-Font auf alle Runs |

### Phase 6: PPTX-Service — Speichern + QA-Loop

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 6.1 | `pptx_service.py` | **PPTX speichern**: `prs.save()` → temp-Verzeichnis |
| 6.2 | `qa_loop_service.py` | **QA-Loop starten** (max 2 Iterationen): |
| 6.3 | `gemini_vision_qa.py` | **PPTX → Images**: LibreOffice → PDF → JPEG (pdfToPpm) |
| 6.4 | `gemini_vision_qa.py` | **Vision-Analyse**: Pro Slide-Image → Gemini Vision mit 9-Kriterien-Prompt: CONTENT_LEAK (Prio 0!), TEXT_OVERFLOW, IMAGE_OVERFLOW, IMAGE_MISSING, EMPTY_PLACEHOLDER, OVERLAP, LOW_CONTRAST, LAYOUT_BROKEN, SPACING |
| 6.5 | `gemini_vision_qa.py` | **Issue-Parsing**: JSON-Response → `SlideIssue[]` mit `fix_action` (clear_content_leak, resize_image, truncate_text, etc.) |
| 6.6 | `pptx_fixer.py:apply_fixes()` | **Programmatische Fixes**: Pro Issue → Fix-Dispatch: `clear_content_leak`, `truncate_text` (Schriftgröße-1pt pro Iteration), `resize_image` (90%), `reposition`, `crop_image`, `remove_placeholder`, `fill_content`, `adjust_spacing`, `change_font_color` |
| 6.7 | `qa_loop_service.py` | **Re-Check**: Nur geänderte Slides erneut prüfen |
| 6.8 | `qa_loop_service.py` | **Ergebnis**: `passed` wenn 0 Errors, SSE-Event `qa_result` mit Details |

### Phase 7: Download

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 7.1 | `generate.py` | **File-ID**: UUID generieren, PPTX-Path in `_generated_files` speichern |
| 7.2 | `generate.py` | **SSE `complete`**: `{fileId, filename, progress: 100, warning_count}` |
| 7.3 | `export.service.ts` | **Download**: Backend fetcht `GET /api/v1/download/{fileId}` → Buffer → an Frontend |

---

## V2 Pipeline (Design/AI-Pipeline)

### Phase 0: Identisch mit V1

Chat-Moderation → Briefing → `===READY===` → Briefing-Text.

### Phase 1: Export starten (Backend)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 1.1 | `export.controller.ts:startV2Export()` | **Job erstellen**: `POST /api/v1/export/start-v2` → UUID-basierter Job |
| 1.2 | `export.service.ts:processV2Job()` | **HTTP-Request**: `POST http://localhost:8000/api/v1/generate-v2` mit `{prompt, mode, document_text, audience, image_style, accent_color, font_family, template_id}` |

### Phase 2: Pipeline-Orchestrierung (8 Stages)

#### Stage 1: Input Interpretation (LLM)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 2.1.1 | `orchestrator.py:_stage_1_interpret()` | **Prompt bauen**: `interpreter_prompt.py` → Briefing-Text + Dokument-Text |
| 2.1.2 | `llm_client.py:call_llm_structured_async()` | **LLM-Aufruf**: Gemini, `temperature=0.3`, `max_tokens=2048`, `responseMimeType: application/json` |
| 2.1.3 | | **Output**: `InterpretedBriefing` (topic, goal, audience, image_style, requested_slide_count, content_themes[]) |
| 2.1.4 | | **Fallback**: Bei LLM-Fehler → Minimal-Briefing aus User-Input |

#### Stage 2: Storyline Planning (LLM)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 2.2.1 | `orchestrator.py:_stage_2_storyline()` | **Prompt bauen**: `storyline_prompt.py` → Briefing als JSON |
| 2.2.2 | `llm_client.py` | **LLM-Aufruf**: `temperature=0.5`, `max_tokens=4096` |
| 2.2.3 | | **Output**: `Storyline` (narrative_arc, beats[]: position, beat_type, core_message, content_theme, emotional_intent) |
| 2.2.4 | | **Fallback**: Bei LLM-Fehler → Linear-Storyline (Opening → Context × N → Closing) |

#### Stage 3: Slide Planning (LLM, 3 Retries)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 2.3.1 | `orchestrator.py:_stage_3_slide_plan()` | **Katalog bauen**: `SLIDE_TYPE_REGISTRY` (14 Slide-Types, erlaubte Blöcke, max Zeichen), `THEME_TO_SLIDE_TYPE` Transform-Regeln |
| 2.3.2 | | **Prompt bauen**: `slide_planner_prompt.py` → Storyline + Briefing + Katalog + Transforms + Audience-Profile + Image-Profile |
| 2.3.3 | `llm_client.py` | **LLM-Aufruf**: `temperature=0.4` (steigt +0.1 pro Retry), `max_tokens=32768`, 3 Versuche |
| 2.3.4 | `llm_client.py` | **JSON-Repair**: Bei Truncation → `repair_json()` (fehlende Klammern ergänzen) |
| 2.3.5 | `llm_client.py` | **401-Retry**: Token-Refresh bei Auth-Fehler |
| 2.3.6 | | **Output**: `PresentationPlan` (metadata, slides[]: position, slide_type, headline, subheadline, core_message, content_blocks[], visual, speaker_notes) |

#### Stage 4: Schema Validation (Code + optional LLM)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 2.4.1 | `validators/__init__.py:validate_plan()` | **Slide-Rules** (18 Regeln S001-S018): Headline required, max 70 chars, core_message, valid slide_type, bullet max count/length, no generic headlines, content blocks match type, visual role valid, total text density, KPI has value, timeline min entries, speaker notes, headline is statement, slide type fully populated, image has function, timeline entries complete, cards have body |
| 2.4.2 | `validators/composition_rules.py` | **Composition-Rules** (7 Regeln C001-C007): Visual-text ratio, content density (chars/cm²), card balance, comparison balance, process step consistency, visual asset required, timeline progression |
| 2.4.3 | `validators/content_leak_rules.py` | **Content-Leak-Rules** (3 Regeln L001-L003): Descriptor patterns, known icon hints, image_description in visible text |
| 2.4.4 | `validators/deck_rules.py` | **Deck-Rules**: Deck-Level Validierung (Gesamtstruktur) |
| 2.4.5 | | **Scoring**: Start 100, -15 pro Error, -5 pro Warning, `passed` wenn ≥ 70 |
| 2.4.6 | `validators/auto_fixes.py` | **Auto-Fix**: `truncate_headline()`, `trim_bullets()`, `truncate_bullet_text()`, `fix_decorative_image()`, `truncate_content_block_text()` |
| 2.4.7 | | **LLM-Regenerierung**: Wenn Auto-Fix nicht reicht (`needs_llm_regeneration()`) → `_regenerate_slide()` via LLM mit Context-Slides |
| 2.4.8 | | **Loop**: Max 2 Regen-Attempts, re-validate nach jedem Fix |

#### Stage 4b: Preflight Quality Gate (Code)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 2.4b.1 | `validators/preflight.py:run_preflight()` | **Scoring pro Slide** (0-100): Readability (30%), Balance (15%), Density (25%), Hierarchy (15%), Visual Fit (15%) |
| 2.4b.2 | | **Readability**: Text/Limit Ratio (≤0.7 → 100, ≤1.0 → 75, >1.2 → <30) |
| 2.4b.3 | | **Balance**: Content-Block-Konsistenz (Card-Bodies, KPI-Labels, Column-Items, Step-Descriptions, Timeline-Descriptions) |
| 2.4b.4 | | **Density**: Fill-Level Sweet-Spot 30-75% → 100, <20% oder >90% → Abzug |
| 2.4b.5 | | **Hierarchy**: Headline-Qualität (Länge, Einzigartigkeit vs. Core-Message) |
| 2.4b.6 | | **Visual Fit**: Visual-Asset Passung (Chart bei chart_insight, Image bei image_text_split) |
| 2.4b.7 | | **Threshold**: Score < 70 → Warning (kein Hard-Block) |

#### Stage 5: Content Filling (LLM, parallel)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 2.5.1 | `orchestrator.py:_stage_5_fill_content()` | **Prompt bauen**: `content_filler_prompt.py` → SlidePlan + Audience-Profile + Image-Profile |
| 2.5.2 | | **Parallel-Ausführung**: `asyncio.gather()` — alle Slides gleichzeitig füllen |
| 2.5.3 | `llm_client.py` | **LLM-Aufruf** (pro Slide): `temperature=0.5` |
| 2.5.4 | | **Output**: `FilledSlide` (headline, subheadline, content_blocks[], visual, speaker_notes, text_metrics) |
| 2.5.5 | | **Metrics**: `total_chars`, `bullet_count`, `max_bullet_length`, `headline_length` berechnen |
| 2.5.6 | | **Fallback**: Bei LLM-Fehler → SlidePlan direkt als FilledSlide übernehmen |

#### Stage 6: Layout Engine (Code)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 2.6.1 | `layouts/engine.py:LayoutEngine.calculate()` | **Blueprint laden**: `blueprints.py` → 14 vordefinierte Layouts mit Element-Positionen in cm für 33.867 × 19.05 cm Canvas |
| 2.6.2 | | **Element-Positionen**: Pro Slide-Type → fixe Positionen (x, y, w, h in cm) für jeden Element-Typ (headline, subheadline, body, bullets, image, chart, cards, kpis, timeline, process_steps) |
| 2.6.3 | | **Output**: `RenderInstruction` (slide_type, elements[]: type, x, y, w, h, content, style) |

#### Stage 7: PPTX Rendering (Code)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 2.7.1 | `renderers/pptx_renderer_v2.py:render()` | **Blank Presentation**: `Presentation()`, `slide_width = Cm(33.867)`, `slide_height = Cm(19.05)` (16:9) |
| 2.7.2 | | **Pro RenderInstruction**: Blank Slide hinzufügen |
| 2.7.3 | | **Pro RenderElement**: Shape erstellen (TextBox, Picture, Chart) mit exakten cm-Positionen aus Blueprint |
| 2.7.4 | | **Text-Rendering**: Font, Größe, Farbe, Bold, Alignment aus Design Tokens |
| 2.7.5 | | **Bild-Rendering**: Imagen 3.0 → `fit_image_to_placeholder()` → `slide.shapes.add_picture()` |
| 2.7.6 | | **Chart-Rendering**: `generate_chart()` → matplotlib PNG → `slide.shapes.add_picture()` |
| 2.7.7 | | **Farben/Fonts**: `accent_color`, `font_family` aus Request, Design-Token-Defaults |

#### Stage 8: Visual Design Review (Code + LLM Vision)

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 2.8.1 | `design_review_agent.py:review_and_fix()` | **PPTX → Images**: LibreOffice → PDF → JPEG |
| 2.8.2 | `design_review_agent.py` | **Gemini Vision Review**: Pro Slide-Image → spezialisierter Design-Review-Prompt → strukturierte Analyse |
| 2.8.3 | | **Output pro Slide**: `SlideReview` (design_score 0-10, verdict, strengths[], fixes[]) |
| 2.8.4 | | **Fix-Kategorien**: FONT_SIZE, SPACING, POSITION, SIZE, PADDING, FONT_WEIGHT, COLOR, REMOVE — mit konkreten Parametern (delta_pt, delta_x_cm, etc.) |
| 2.8.5 | | **Fix anwenden**: `RenderInstruction` Adjustments → Re-Render |
| 2.8.6 | | **Loop**: Max 2 Iterationen, Re-Check nach Fixes |
| 2.8.7 | | **Ergebnis**: `DesignReviewResult` (avg_score, total_fixes_applied) |

### Phase 3: Quality Report + Download

| Schritt | Datei | Was passiert |
|---------|-------|-------------|
| 3.1 | `orchestrator.py:_stage_8_quality_report()` | **Quality zusammenführen**: Validation Score + Design Review Score → finaler `QualityReport` |
| 3.2 | `generate_v2.py` | **SSE `complete`**: `{fileId, filename, quality: {passed, score, slide_count, design_score, design_fixes}}` |
| 3.3 | `export.service.ts` | **Download**: Backend fetcht `GET /api/v1/download-v2/{fileId}` → Buffer → an Frontend |

---

## Vergleich: Quality Gates V1 vs V2

| Quality Gate | V1 (Template) | V2 (Design) |
|-------------|---------------|-------------|
| **Markdown-Validierung** | `MarkdownValidator` (Layout, Titel, Bullets, Placeholder) | - (kein Markdown) |
| **Strukturvalidierung** | `validateStructure()` (Images auf falschen Slides) + LLM-Fix | - (Slide-Typen sind Schema-gebunden) |
| **Readability-Validierung** | `validateAndFix()` + LLM-Fix | - (in Stage 4) |
| **Content-Leak-Erkennung** | `v1_content_leak_check.py` (pre-render) | `content_leak_rules.py` (Stage 4) |
| **Slide-Level-Validierung** | `v1_slide_rules.py` (12 Regeln) | `slide_rules.py` (18 Regeln) |
| **Composition-Validierung** | In `v1_slide_rules.py` (S010, S011) | `composition_rules.py` (7 Regeln) |
| **Auto-Fixes** | `v1_auto_fixes.py` (truncate, trim) | `auto_fixes.py` + LLM-Regenerierung |
| **Preflight-Scoring** | `v1_preflight.py` (4 Dimensionen) | `preflight.py` (5 Dimensionen) |
| **Vision QA** | `gemini_vision_qa.py` (9 Kriterien) | `design_review_agent.py` (strukturierte Fixes) |
| **Post-Render Fix** | `pptx_fixer.py` (10 Fix-Actions) | Design Review Re-Render |
| **QA-Loop** | `qa_loop_service.py` (max 2 Iterationen) | Design Review Agent (max 2 Iterationen) |

---

## Datenfluss-Übersicht

### V1

```
User-Input
  → Chat-Moderation (LLM) → Briefing
  → Markdown-Generierung (LLM) → Markdown
  → Strukturvalidierung (Code + LLM) → fixes Markdown
  → Readability-Validierung (Code + LLM) → gekürztes Markdown
  → Markdown-Parser (Code) → PresentationData (SlideContent[])
  → Content-Leak-Sanitierung (Code) → gesäubertes PresentationData
  → Slide-Validierung (Code) → Findings
  → Auto-Fix (Code) → gekürztes PresentationData
  → Preflight-Scoring (Code) → Warnungen
  → Template laden + Layout-Auflösung (Code)
  → Per-Slide Rendering (Code) → Placeholders füllen, Images/Charts
  → PPTX speichern
  → Vision QA (LLM Vision) → Issues
  → Programmatische Fixes (Code) → korrigierte PPTX
  → Re-Check (LLM Vision)
  → Download
```

### V2

```
User-Input
  → Chat-Moderation (LLM) → Briefing
  → Stage 1: Input Interpretation (LLM) → InterpretedBriefing
  → Stage 2: Storyline Planning (LLM) → Storyline (Beats)
  → Stage 3: Slide Planning (LLM, 3 Retries) → PresentationPlan (SlidePlan[])
  → Stage 4: Validation (Code) → QualityReport
    → Auto-Fixes (Code)
    → LLM-Regenerierung (für komplexe Fehler)
  → Stage 4b: Preflight Scoring (Code) → SlideScores
  → Stage 5: Content Filling (LLM, parallel) → FilledSlide[]
  → Stage 6: Layout Engine (Code) → RenderInstruction[]
  → Stage 7: PPTX Rendering (Code) → PPTX-Datei
  → Stage 8: Design Review (LLM Vision) → Fixes
    → Re-Render (Code)
    → Re-Check (LLM Vision)
  → Download
```
