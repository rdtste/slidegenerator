# Slidegenerator V2 -- Produktionsarchitektur

## Kernproblem

Das aktuelle System delegiert die gesamte Praesentation an einen einzigen LLM-Aufruf. Das LLM entscheidet gleichzeitig ueber Inhalt, Struktur, Folientyp, Textmenge, Layout und visuelle Logik. Das Ergebnis ist vorhersehbar: generische Bullet-Folien, inkonsistentes Design, keine visuelle Hierarchie, keine Qualitaetskontrolle. Das Problem ist nicht der Prompt -- das Problem ist die Architektur. Ein einzelner Prompt kann nicht gleichzeitig Storyteller, Designer, Layout-Engine und Quality Gate sein.

Die Loesung: Das LLM plant Inhalt und Struktur. Das System erzwingt Design, validiert Qualitaet und rendert deterministisch.

---

## 1. Zielarchitektur: Der Production Pipeline

Die neue Architektur ist eine 8-stufige Pipeline. Jede Stufe hat eine klar definierte Verantwortung, Eingabe und Ausgabe. Keine Stufe darf die Verantwortung einer anderen uebernehmen.

```
User Input
    |
    v
[Stage 1] Input Interpreter (LLM)
    |
    v
[Stage 2] Storyline Planner (LLM)
    |
    v
[Stage 3] Slide Planner (LLM, constrained)
    |
    v
[Stage 4] Schema Validator (Code, deterministic)
    |
    v
[Stage 5] Content Filler (LLM, per-slide)
    |
    v
[Stage 6] Template Mapper + Layout Engine (Code, deterministic)
    |
    v
[Stage 7] PPTX Renderer (Code, deterministic)
    |
    v
[Stage 8] Post-Generation Review (LLM + Code)
    |
    v
Output / Regeneration Loop
```

### Stage 1: Input Interpreter

- **Zweck**: User-Eingabe in ein strukturiertes Briefing uebersetzen.
- **Eingabe**: Freitext-Prompt, optional angehaengte Dokumente (PDF, DOCX, TXT).
- **Ausgabe**: `InterpretedBriefing` -- strukturiertes JSON.
- **Verantwortung**: LLM (mit Schema-Constraint via structured output).
- **Fehlerlogik**: Wenn Briefing unvollstaendig (z.B. kein Thema erkennbar), Rueckfrage an User.

```json
{
  "topic": "Q1 2026 Geschaeftsergebnisse",
  "goal": "Vorstand ueber Quartalsergebnisse informieren und Massnahmen vorschlagen",
  "audience": "management",
  "tone": "formal_analytical",
  "image_style": "data_visual",
  "requested_slide_count": 12,
  "key_facts": [
    "Umsatz +8% YoY",
    "EBIT-Marge 14.2%",
    "3 neue Maerkte erschlossen"
  ],
  "source_documents": ["q1_report.pdf"],
  "content_themes": ["financials", "market_expansion", "outlook", "actions"],
  "constraints": {
    "must_include": ["KPI-Uebersicht", "Marktvergleich"],
    "must_avoid": ["technische Details"],
    "language": "de"
  }
}
```

### Stage 2: Storyline Planner

- **Zweck**: Narrativen Bogen der Praesentation definieren. Keine Folien -- nur die Story.
- **Eingabe**: `InterpretedBriefing`.
- **Ausgabe**: `Storyline` -- geordnete Liste von Story Beats mit Kernaussagen.
- **Verantwortung**: LLM (Kreativitaet), aber Output muss Schema-konform sein.
- **Fehlerlogik**: Wenn weniger als 3 oder mehr als 25 Beats, regenerieren. Wenn kein klarer Bogen (Intro/Body/Conclusion), regenerieren.

```json
{
  "narrative_arc": "situation_complication_resolution",
  "beats": [
    {
      "position": 1,
      "beat_type": "opening",
      "core_message": "Q1 2026 war unser staerkstes Quartal seit 3 Jahren",
      "content_theme": "financials",
      "emotional_intent": "confidence",
      "evidence_needed": true
    },
    {
      "position": 2,
      "beat_type": "context",
      "core_message": "Der Markt waechst, aber der Wettbewerb verschaerft sich",
      "content_theme": "market_expansion",
      "emotional_intent": "urgency",
      "evidence_needed": true
    }
  ]
}
```

### Stage 3: Slide Planner

- **Zweck**: Jeden Story Beat in genau einen erlaubten Slide-Typ uebersetzen. Das LLM waehlt den Slide-Typ aus einer festen Liste. Es definiert Headline, Subheadline, Content-Struktur und Visual-Typ. Es schreibt KEINEN Fliesstext -- nur strukturierte Platzhalter.
- **Eingabe**: `Storyline` + `InterpretedBriefing` + Liste erlaubter `SlideTypes`.
- **Ausgabe**: `PresentationPlan` mit `SlidePlan[]`.
- **Verantwortung**: LLM (Auswahl), aber strikt durch erlaubte Typen eingeschraenkt.
- **Fehlerlogik**: Wenn unerlaubter Typ gewaehlt, Fallback auf naechstbesten erlaubten Typ. Wenn Content-Felder fehlen, Slide wird markiert und regeneriert.

```json
{
  "slide_type": "kpi_dashboard",
  "headline": "Q1 auf Rekordkurs",
  "subheadline": "Alle Kernindikatoren ueber Plan",
  "core_message": "Q1 2026 war unser staerkstes Quartal seit 3 Jahren",
  "content_blocks": [
    { "type": "kpi", "label": "Umsatz", "value": "142M EUR", "trend": "up", "delta": "+8%" },
    { "type": "kpi", "label": "EBIT-Marge", "value": "14.2%", "trend": "up", "delta": "+1.1pp" },
    { "type": "kpi", "label": "Neue Maerkte", "value": "3", "trend": "neutral", "delta": "" }
  ],
  "visual": {
    "type": "none",
    "image_role": "none"
  },
  "speaker_notes": "Betonen: Bestes Quartal seit 2023. Vergleich mit Wettbewerb erwaehnen."
}
```

### Stage 4: Schema Validator

- **Zweck**: Harte Pruefung des PresentationPlan gegen Regeln. Kein LLM -- rein deterministisch.
- **Eingabe**: `PresentationPlan`.
- **Ausgabe**: `ValidationResult` mit PASS / FAIL pro Slide + Deck-Level-Checks.
- **Verantwortung**: Code (Python-Validatoren).
- **Fehlerlogik**: FAIL-Slides werden mit Fehlerbeschreibung zurueck an Stage 3 zur Regeneration gegeben. Max 2 Regenerationsversuche pro Slide, dann Fallback-Typ.

### Stage 5: Content Filler

- **Zweck**: Fuer jeden validierten SlidePlan den finalen Text erzeugen. Das LLM schreibt jetzt die eigentlichen Bullet-Texte, Beschreibungen und Labels -- aber nur innerhalb der Constraints des Slide-Typs.
- **Eingabe**: Ein einzelner `SlidePlan` + Zielgruppen-Profil + Bildstil-Profil.
- **Ausgabe**: `FilledSlide` mit finalen Texten, aber immer noch kein Layout.
- **Verantwortung**: LLM (Textqualitaet), eingeschraenkt durch Zeichenlimits und Content-Regeln des Slide-Typs.
- **Fehlerlogik**: Wenn Text zu lang, automatisch kuerzen und Warnung. Wenn Bullet-Count ueberschritten, letzte Bullets streichen.

### Stage 6: Template Mapper + Layout Engine

- **Zweck**: Deterministische Zuordnung von Slide-Typ + Zielgruppe + Bildstil zu einem konkreten PPTX-Layout. Berechnung von Positionen, Groessen, Schriftgroessen. Kein LLM.
- **Eingabe**: `FilledSlide[]` + Template-Profil + Zielgruppe + Bildstil.
- **Ausgabe**: `RenderInstruction[]` -- exakte Anweisungen fuer den Renderer.
- **Verantwortung**: Code (deterministische Layout-Regeln).
- **Fehlerlogik**: Wenn kein passendes Layout existiert, Fallback auf generisches Layout des Slide-Typs.

### Stage 7: PPTX Renderer

- **Zweck**: python-pptx-Code, der RenderInstructions 1:1 umsetzt. Keine Entscheidungen, keine Interpretation. Reine Ausfuehrung.
- **Eingabe**: `RenderInstruction[]`.
- **Ausgabe**: `.pptx`-Datei.
- **Verantwortung**: Code (python-pptx).
- **Fehlerlogik**: Bei Rendering-Fehler (z.B. Bild nicht verfuegbar), Platzhalter einsetzen und Warnung loggen.

### Stage 8: Post-Generation Review

- **Zweck**: Automatische Qualitaetspruefung des fertigen Decks. Kombination aus Code-Checks und optionalem LLM-Review.
- **Eingabe**: Generiertes `.pptx` + `PresentationPlan`.
- **Ausgabe**: `QualityReport` mit Score und Findings.
- **Verantwortung**: Code (deterministische Checks) + LLM (subjektive Bewertung).
- **Fehlerlogik**: Wenn Score unter Schwellenwert, spezifische Slides zur Regeneration markieren. Max 1 Regenerationszyklus fuer das gesamte Deck.

---

## 2. Konkretes Datenmodell

### InterpretedBriefing

```json
{
  "$schema": "briefing_v1",
  "topic": "string, required",
  "goal": "string, required",
  "audience": "enum: team | management | customer | workshop",
  "tone": "enum: formal_analytical | persuasive | collaborative | educational",
  "image_style": "enum: photo | illustration | minimal | data_visual | none",
  "requested_slide_count": "integer, 5-25, default 10",
  "key_facts": ["string[]"],
  "content_themes": ["string[]"],
  "source_documents": ["string[] (file references)"],
  "constraints": {
    "must_include": ["string[]"],
    "must_avoid": ["string[]"],
    "language": "string, default 'de'"
  }
}
```

### Storyline

```json
{
  "$schema": "storyline_v1",
  "narrative_arc": "enum: situation_complication_resolution | problem_solution | chronological | thematic_cluster | compare_decide",
  "total_beats": "integer",
  "beats": [
    {
      "position": "integer, 1-based",
      "beat_type": "enum: opening | context | evidence | insight | action | transition | closing",
      "core_message": "string, max 120 chars",
      "content_theme": "string",
      "emotional_intent": "enum: confidence | urgency | curiosity | resolution | inspiration",
      "evidence_needed": "boolean",
      "suggested_slide_types": ["string[], aus erlaubter Liste, max 2 Vorschlaege"]
    }
  ]
}
```

### PresentationPlan

```json
{
  "$schema": "presentation_plan_v1",
  "briefing_ref": "InterpretedBriefing",
  "storyline_ref": "Storyline",
  "audience": "enum",
  "image_style": "enum",
  "slides": ["SlidePlan[]"],
  "metadata": {
    "total_slides": "integer",
    "estimated_duration_minutes": "integer",
    "content_density": "enum: light | medium | dense"
  }
}
```

### SlidePlan

```json
{
  "$schema": "slide_plan_v1",
  "position": "integer, 1-based",
  "slide_type": "enum: aus erlaubter Liste (siehe Abschnitt 3)",
  "beat_ref": "integer, referenziert Storyline-Beat",
  "headline": "string, max 60 chars",
  "subheadline": "string, max 100 chars, optional",
  "core_message": "string, max 120 chars",
  "content_blocks": ["ContentBlock[]"],
  "visual": {
    "type": "enum: photo | illustration | icon | chart | diagram | none",
    "image_role": "enum: hero | supporting | decorative | evidence | none",
    "image_description": "string, max 200 chars, nur wenn type != none",
    "chart_spec": "ChartSpec, nur wenn type == chart"
  },
  "speaker_notes": "string, max 500 chars",
  "transition_hint": "string, optional, max 80 chars",
  "validation": {
    "passed": "boolean",
    "issues": ["string[]"],
    "regeneration_count": "integer"
  }
}
```

### ContentBlock

```json
{
  "type": "enum: text | bullets | kpi | quote | label_value | comparison_column | process_step | timeline_entry | card",
  "content": "string | object, abhaengig vom type",
  "max_chars": "integer, vom Slide-Typ bestimmt",
  "max_items": "integer, vom Slide-Typ bestimmt"
}
```

Typ-spezifische Content-Strukturen:

```json
// type: "bullets"
{
  "type": "bullets",
  "items": [
    { "text": "string, max 60 chars", "bold_prefix": "string, optional, max 20 chars" }
  ],
  "max_items": 3
}

// type: "kpi"
{
  "type": "kpi",
  "label": "string, max 30 chars",
  "value": "string, max 15 chars",
  "trend": "enum: up | down | neutral",
  "delta": "string, max 15 chars"
}

// type: "comparison_column"
{
  "type": "comparison_column",
  "column_label": "string, max 25 chars",
  "items": ["string[], max 4 items, max 50 chars each"]
}

// type: "timeline_entry"
{
  "type": "timeline_entry",
  "date": "string, max 20 chars",
  "title": "string, max 40 chars",
  "description": "string, max 80 chars"
}

// type: "process_step"
{
  "type": "process_step",
  "step_number": "integer",
  "title": "string, max 30 chars",
  "description": "string, max 80 chars"
}

// type: "card"
{
  "type": "card",
  "title": "string, max 30 chars",
  "body": "string, max 100 chars",
  "icon_hint": "string, optional"
}

// type: "quote"
{
  "type": "quote",
  "text": "string, max 150 chars",
  "attribution": "string, max 50 chars"
}

// type: "label_value"
{
  "type": "label_value",
  "pairs": [
    { "label": "string, max 25 chars", "value": "string, max 40 chars" }
  ],
  "max_items": 6
}
```

### ChartSpec

```json
{
  "chart_type": "enum: bar | horizontal_bar | stacked_bar | line | pie | donut",
  "title": "string, max 50 chars",
  "data": {
    "labels": ["string[]"],
    "series": [
      { "name": "string", "values": ["number[]"] }
    ]
  },
  "unit": "string, optional (%, EUR, Stk)",
  "highlight_index": "integer, optional"
}
```

### FilledSlide

Identisch mit SlidePlan, aber alle `content` Felder sind final befuellt (keine Platzhalter). Zusaetzliches Feld:

```json
{
  "text_metrics": {
    "total_chars": "integer",
    "bullet_count": "integer",
    "max_bullet_length": "integer",
    "headline_length": "integer"
  }
}
```

### RenderInstruction

```json
{
  "slide_index": "integer",
  "layout_id": "string, referenziert Template-Layout",
  "elements": [
    {
      "placeholder_type": "enum: title | subtitle | body | image | chart | shape | label | kpi_value | kpi_label | kpi_trend",
      "content": "string | ImageRef | ChartSpec",
      "position": { "left_cm": "float", "top_cm": "float", "width_cm": "float", "height_cm": "float" },
      "style": {
        "font_family": "string",
        "font_size_pt": "integer",
        "font_color": "string, hex",
        "bold": "boolean",
        "alignment": "enum: left | center | right",
        "vertical_alignment": "enum: top | middle | bottom"
      }
    }
  ],
  "background": {
    "type": "enum: solid | gradient | image",
    "value": "string"
  }
}
```

### QualityReport

```json
{
  "overall_score": "float, 0-100",
  "pass": "boolean (score >= 70)",
  "deck_findings": [
    { "rule": "string", "severity": "enum: error | warning", "message": "string" }
  ],
  "slide_findings": [
    {
      "slide_index": "integer",
      "findings": [
        { "rule": "string", "severity": "enum: error | warning", "message": "string", "auto_fixable": "boolean" }
      ],
      "regenerate": "boolean"
    }
  ]
}
```

---

## 3. Erlaubte Slide-Typen

### Vollstaendiger Katalog: 14 Typen

#### 1. `title_hero`
- **Zweck**: Eroeffnungsfolie, Sectiontrenner.
- **Wann**: Position 1 oder bei Themenuebergang.
- **Erlaubte Inhalte**: Headline (max 50 chars), Subheadline (max 80 chars), optional ein Hero-Bild oder Farbflaeche.
- **Verboten**: Bullets, KPIs, Charts. Kein Text unterhalb der Subheadline.
- **Layout**: Headline zentriert oder links, grosser Weissraum, optional Vollbild-Hintergrund.
- **Zielgruppen**: Alle, aber besonders `management` und `customer`.

#### 2. `section_divider`
- **Zweck**: Visueller Trenner zwischen Deck-Abschnitten.
- **Wann**: Zwischen thematischen Bloecken (z.B. vor "Ausblick").
- **Erlaubte Inhalte**: Section-Titel (max 40 chars), optional Untertitel (max 60 chars).
- **Verboten**: Jeglicher Body-Content. Keine Bullets, keine Bilder.
- **Layout**: Zentrierter grosser Titel, Akzentfarbe oder -form.
- **Zielgruppen**: Alle.

#### 3. `key_statement`
- **Zweck**: Eine zentrale Aussage visuell hervorheben.
- **Wann**: Wenn ein Beat-Typ `insight` oder `core_message` besonders stark ist.
- **Erlaubte Inhalte**: Eine Aussage (max 100 chars), optional Attribution/Quelle (max 50 chars).
- **Verboten**: Bullets, mehrere Textbloecke, Charts.
- **Layout**: Grosser zentrierter Text, optional Akzentfarbe links oder grosses Anfuehrungszeichen.
- **Zielgruppen**: `management`, `customer`.

#### 4. `bullets_focused`
- **Zweck**: Knappe Aufzaehlung mit klarer Hierarchie.
- **Wann**: Wenn 2-3 gleichwertige Punkte kommuniziert werden muessen.
- **Erlaubte Inhalte**: Headline, max 3 Bullets (je max 60 chars), optionaler Bold-Prefix pro Bullet (max 20 chars).
- **Verboten**: Mehr als 3 Bullets. Bullets ohne Bold-Prefix bei `management`-Zielgruppe. Generische Formulierungen.
- **Layout**: Headline oben, Bullets mit ausreichend Abstand, grosser Weissraum rechts oder unten.
- **Zielgruppen**: `team`, `management`.

#### 5. `three_cards`
- **Zweck**: 3 parallele Konzepte/Optionen/Saeulen nebeneinander.
- **Wann**: Strategische Saeulen, Optionen, Vorteile, Vergleichsdimensionen.
- **Erlaubte Inhalte**: Headline, 3 Cards (je: Titel max 30 chars, Body max 100 chars, optional Icon-Hint).
- **Verboten**: Mehr als 3 Cards. Cards ohne Titel. Cards mit mehr als 100 chars Body.
- **Layout**: 3 gleichgrosse Container nebeneinander, optional mit Icon/Emoji oben.
- **Zielgruppen**: `management`, `customer`, `workshop`.

#### 6. `kpi_dashboard`
- **Zweck**: Kennzahlen auf einen Blick.
- **Wann**: Wenn 2-5 numerische Kernindikatoren praesentiert werden.
- **Erlaubte Inhalte**: Headline, 2-5 KPI-Bloecke (je: Label max 30 chars, Value max 15 chars, Trend, Delta).
- **Verboten**: Mehr als 5 KPIs. KPIs ohne numerischen Value. Fliesstext.
- **Layout**: KPI-Karten in einer Reihe oder 2x2/2x3-Grid, grosse Zahlen, kleine Labels.
- **Zielgruppen**: `management` (primaer), `team`.

#### 7. `image_text_split`
- **Zweck**: Bild und Text gleichberechtigt nebeneinander.
- **Wann**: Wenn ein Bild funktional zum Inhalt beitraegt (nicht dekorativ).
- **Erlaubte Inhalte**: Headline, Text-Block (max 200 chars oder max 3 Bullets), Bild mit image_role `supporting` oder `evidence`.
- **Verboten**: Bild als reine Dekoration. Text ohne Bezug zum Bild. Mehr als 3 Bullets.
- **Layout**: 50/50 oder 60/40 Split, Bild links oder rechts (alternierend im Deck).
- **Zielgruppen**: `customer`, `team`.

#### 8. `comparison`
- **Zweck**: Zwei Optionen/Zustaende/Szenarien gegenuebergestellt.
- **Wann**: Vorher/Nachher, Option A/B, Ist/Soll.
- **Erlaubte Inhalte**: Headline, 2 Comparison-Columns (je: Label max 25 chars, max 4 Items je max 50 chars).
- **Verboten**: Mehr als 2 Spalten. Mehr als 4 Items pro Spalte.
- **Layout**: 2 Spalten mit klarer visueller Trennung, optional Farb-Coding (rot/gruen, grau/akzent).
- **Zielgruppen**: `management`, `team`, `workshop`.

#### 9. `timeline`
- **Zweck**: Chronologische Abfolge darstellen.
- **Wann**: Wenn ein Beat content_theme `history`, `milestones`, `roadmap` hat.
- **Erlaubte Inhalte**: Headline, 3-6 Timeline-Entries (je: Date max 20 chars, Title max 40 chars, Description max 80 chars).
- **Verboten**: Mehr als 6 Eintraege. Eintraege ohne Datum.
- **Layout**: Horizontale Zeitleiste mit Punkten und Labels, oder vertikale Schrittfolge.
- **Zielgruppen**: Alle.

#### 10. `process_flow`
- **Zweck**: Sequentielle Schritte eines Prozesses.
- **Wann**: Ablauf, Methodik, Vorgehensmodell.
- **Erlaubte Inhalte**: Headline, 3-5 Process-Steps (je: Step-Number, Title max 30 chars, Description max 80 chars).
- **Verboten**: Mehr als 5 Schritte. Schritte ohne Nummer.
- **Layout**: Horizontale Pfeile oder nummerierte vertikale Schritte.
- **Zielgruppen**: `team`, `workshop`.

#### 11. `chart_insight`
- **Zweck**: Eine Daten-Visualisierung mit Kernaussage.
- **Wann**: Wenn ein Beat Evidence durch Zahlen braucht.
- **Erlaubte Inhalte**: Headline, ChartSpec, optional 1-2 Takeaway-Bullets (max 60 chars).
- **Verboten**: Mehr als 1 Chart. Mehr als 2 Bullets neben dem Chart. Chart ohne Headline.
- **Layout**: Chart nimmt 60-70% der Flaeche ein, Headline oben, Takeaways unten oder rechts.
- **Zielgruppen**: `management` (primaer), `team`.

#### 12. `image_fullbleed`
- **Zweck**: Emotionales Vollbild mit minimalem Text-Overlay.
- **Wann**: Stimmungswechsel, Eroeffnung eines neuen Abschnitts, emotionaler Akzent.
- **Erlaubte Inhalte**: Bild (hero-Rolle), optional kurzer Text-Overlay (max 60 chars).
- **Verboten**: Bullets, KPIs, Charts, langer Text.
- **Layout**: Bild vollflaeching, Text-Overlay mit halbtransparentem Hintergrund.
- **Zielgruppen**: `customer` (primaer), `workshop`.

#### 13. `agenda`
- **Zweck**: Ueberblick ueber die Praesentationsstruktur.
- **Wann**: Position 2 (nach Title) oder bei langen Praesentationen (>10 Folien).
- **Erlaubte Inhalte**: Headline ("Agenda"/"Ueberblick"), 3-6 Agenda-Punkte (je max 40 chars).
- **Verboten**: Mehr als 6 Punkte. Punkte mit Unterpunkten. Detailbeschreibungen.
- **Layout**: Nummerierte vertikale Liste, aktueller Punkt optional hervorgehoben.
- **Zielgruppen**: `management`, `customer`.

#### 14. `closing`
- **Zweck**: Abschlussfolie mit Call-to-Action oder Zusammenfassung.
- **Wann**: Letzte Folie.
- **Erlaubte Inhalte**: Headline (max 50 chars), optional 1-3 Takeaway-Bullets (max 60 chars), optional Kontaktinfo.
- **Verboten**: Neue Inhalte. Charts. Detaillierte Beschreibungen.
- **Layout**: Aehnlich wie `key_statement`, optional mit Kontaktblock unten.
- **Zielgruppen**: Alle.

---

## 4. Transformationslogik

Die Transformationslogik mappt Content-Themes und Beat-Typen auf bevorzugte Slide-Typen. Sie wird im Slide Planner als Constraint mitgegeben.

### Primaere Themen-zu-Typ-Mappings

```
THEME/PATTERN             -> BEVORZUGTE SLIDE-TYPEN         -> VERBOTENE TYPEN
--------------------------------------------------------------------------------
history / milestones      -> timeline                       -> bullets_focused
roadmap / plan            -> timeline, process_flow         -> key_statement
financials / kpis         -> kpi_dashboard, chart_insight   -> image_fullbleed
strategy / vision         -> key_statement, three_cards     -> bullets_focused
comparison / alternatives -> comparison                     -> kpi_dashboard
process / method          -> process_flow                   -> image_fullbleed
team / people / culture   -> image_text_split, three_cards  -> kpi_dashboard
market / competition      -> chart_insight, comparison      -> key_statement
actions / next_steps      -> three_cards, process_flow      -> image_fullbleed
summary / conclusion      -> closing, key_statement         -> timeline
workshop / ideation       -> three_cards, comparison        -> kpi_dashboard
quote / testimonial       -> key_statement                  -> chart_insight, kpi_dashboard
```

### Beat-Type-zu-Slide-Type-Mappings

```
BEAT TYPE    -> BEVORZUGTE SLIDE-TYPEN
----------------------------------------
opening      -> title_hero, image_fullbleed
context      -> bullets_focused, image_text_split, chart_insight
evidence     -> kpi_dashboard, chart_insight, comparison
insight      -> key_statement, three_cards
action       -> three_cards, process_flow
transition   -> section_divider
closing      -> closing, key_statement
```

### Zielgruppen-Modifikatoren

Die Zielgruppe modifiziert die Typ-Auswahl:

```
management:
  - Bevorzuge: kpi_dashboard, key_statement, chart_insight
  - Vermeide: image_fullbleed (ausser Eroeffnung), process_flow (zu detailliert)
  - Erzwinge: Mindestens 1 kpi_dashboard wenn content_theme "financials" vorkommt
  - Content-Dichte: niedrig (wenig Text, grosse Zahlen)

team:
  - Bevorzuge: bullets_focused, process_flow, comparison
  - Vermeide: image_fullbleed, key_statement (zu abstrakt)
  - Content-Dichte: mittel

customer:
  - Bevorzuge: image_text_split, image_fullbleed, key_statement, three_cards
  - Vermeide: process_flow (zu intern), kpi_dashboard (nur wenn extern relevant)
  - Erzwinge: Mindestens 1 image_fullbleed oder image_text_split
  - Content-Dichte: niedrig (emotional, visuell)

workshop:
  - Bevorzuge: three_cards, comparison, process_flow
  - Vermeide: kpi_dashboard, chart_insight (zu passiv)
  - Erzwinge: Mindestens 1 comparison oder three_cards
  - Content-Dichte: mittel (interaktiv, offen)
```

### Bildstil-Modifikatoren

```
photo:
  - image_text_split: Bild muss Photo sein
  - image_fullbleed: erlaubt und empfohlen
  - Mindestens 20% der Folien sollten ein Bild haben

illustration:
  - image_text_split: Bild muss Illustration sein
  - image_fullbleed: erlaubt
  - Icons in three_cards und process_flow empfohlen

minimal:
  - image_fullbleed: verboten
  - image_text_split: nur mit geometrischen/abstrakten Formen
  - Keine Photos. Icons statt Bilder.
  - Viel Weissraum

data_visual:
  - chart_insight: bevorzugt, mindestens 2 pro Deck
  - kpi_dashboard: bevorzugt
  - image_fullbleed: verboten
  - Bilder nur als Diagramme oder Data-Visualisierungen

none:
  - Alle image-Varianten verboten
  - Kein image_fullbleed, kein image_text_split
  - Nur typografische Slide-Typen
```

### Automatische Sequenz-Regeln

```
1. Folie 1 MUSS title_hero sein
2. Letzte Folie MUSS closing sein
3. Wenn total_slides >= 10: Folie 2 SOLLTE agenda sein
4. Maximal 2 bullets_focused hintereinander
5. Maximal 1 kpi_dashboard pro 5 Folien
6. section_divider nur vor Themenwechsel, nie am Ende
7. chart_insight nie direkt nach kpi_dashboard
8. image_fullbleed nie direkt nach image_fullbleed
9. Mindestens 3 verschiedene Slide-Typen im Deck
10. key_statement maximal 2x pro Deck
```

---

## 5. Validator- und Quality-Gate-Logik

### Slide-Level Checks (deterministisch, Code)

```python
SLIDE_RULES = {
    # Universelle Regeln
    "S001": {
        "rule": "headline_required",
        "check": "slide.headline is not None and len(slide.headline.strip()) > 0",
        "severity": "error",
        "message": "Jede Folie braucht eine Headline"
    },
    "S002": {
        "rule": "headline_max_length",
        "check": "len(slide.headline) <= 60",
        "severity": "error",
        "message": "Headline darf max 60 Zeichen haben",
        "auto_fix": "truncate_at_word_boundary(slide.headline, 60)"
    },
    "S003": {
        "rule": "core_message_required",
        "check": "slide.core_message is not None and len(slide.core_message.strip()) > 0",
        "severity": "error",
        "message": "Jede Folie braucht eine Kernaussage"
    },
    "S004": {
        "rule": "valid_slide_type",
        "check": "slide.slide_type in ALLOWED_SLIDE_TYPES",
        "severity": "error",
        "message": "Slide-Typ ist nicht erlaubt"
    },
    "S005": {
        "rule": "bullets_max_count",
        "check": "count_bullets(slide) <= 3",
        "severity": "error",
        "message": "Max 3 Bullets pro Folie",
        "auto_fix": "slide.content_blocks.bullets.items = items[:3]"
    },
    "S006": {
        "rule": "bullet_max_length",
        "check": "all(len(b.text) <= 60 for b in bullets)",
        "severity": "error",
        "message": "Jeder Bullet darf max 60 Zeichen haben",
        "auto_fix": "truncate_at_word_boundary(bullet.text, 60)"
    },
    "S007": {
        "rule": "no_generic_headline",
        "check": "slide.headline.lower() not in GENERIC_HEADLINES",
        "severity": "warning",
        "message": "Headline ist zu generisch (z.B. 'Ueberblick', 'Zusammenfassung')"
    },
    "S008": {
        "rule": "content_blocks_match_type",
        "check": "validate_content_blocks_for_type(slide)",
        "severity": "error",
        "message": "Content-Bloecke passen nicht zum Slide-Typ"
    },
    "S009": {
        "rule": "visual_role_valid",
        "check": "slide.visual.image_role != 'decorative' or slide.slide_type == 'image_fullbleed'",
        "severity": "warning",
        "message": "Dekorative Bilder nur bei image_fullbleed erlaubt"
    },
    "S010": {
        "rule": "total_text_density",
        "check": "slide.text_metrics.total_chars <= MAX_CHARS_FOR_TYPE[slide.slide_type]",
        "severity": "error",
        "message": "Folie hat zu viel Text fuer diesen Slide-Typ"
    },
    "S011": {
        "rule": "kpi_has_numeric_value",
        "check": "all KPI content_blocks have numeric value",
        "severity": "error",
        "message": "KPI-Werte muessen numerisch sein"
    },
    "S012": {
        "rule": "timeline_min_entries",
        "check": "if slide_type == 'timeline': len(entries) >= 3",
        "severity": "error",
        "message": "Timeline braucht mindestens 3 Eintraege"
    },
    "S013": {
        "rule": "speaker_notes_present",
        "check": "len(slide.speaker_notes.strip()) > 0",
        "severity": "warning",
        "message": "Speaker Notes fehlen"
    },
}

GENERIC_HEADLINES = [
    "ueberblick", "zusammenfassung", "einfuehrung", "inhalt",
    "weitere punkte", "details", "informationen", "folie",
    "overview", "summary", "introduction", "agenda"
]

MAX_CHARS_FOR_TYPE = {
    "title_hero": 130,
    "section_divider": 100,
    "key_statement": 150,
    "bullets_focused": 250,
    "three_cards": 400,
    "kpi_dashboard": 300,
    "image_text_split": 250,
    "comparison": 350,
    "timeline": 500,
    "process_flow": 450,
    "chart_insight": 200,
    "image_fullbleed": 60,
    "agenda": 280,
    "closing": 250,
}
```

### Deck-Level Checks (deterministisch, Code)

```python
DECK_RULES = {
    "D001": {
        "rule": "starts_with_title_hero",
        "check": "slides[0].slide_type == 'title_hero'",
        "severity": "error"
    },
    "D002": {
        "rule": "ends_with_closing",
        "check": "slides[-1].slide_type == 'closing'",
        "severity": "error"
    },
    "D003": {
        "rule": "min_type_variety",
        "check": "len(set(s.slide_type for s in slides)) >= 3",
        "severity": "error",
        "message": "Mindestens 3 verschiedene Slide-Typen im Deck"
    },
    "D004": {
        "rule": "no_consecutive_bullets",
        "check": "no two consecutive bullets_focused",
        "severity": "error",
        "message": "Keine 2 bullets_focused hintereinander"
    },
    "D005": {
        "rule": "no_consecutive_same_type",
        "check": "no three consecutive same slide_type",
        "severity": "warning"
    },
    "D006": {
        "rule": "audience_fit",
        "check": "audience-spezifische Pflicht-Typen vorhanden",
        "severity": "warning",
        "message": "Zielgruppen-Anforderungen nicht erfuellt"
    },
    "D007": {
        "rule": "image_style_compliance",
        "check": "Alle Visuals entsprechen dem gewaehlten Bildstil",
        "severity": "error"
    },
    "D008": {
        "rule": "history_needs_timeline",
        "check": "if 'history' in themes: any(s.slide_type == 'timeline' for s in slides)",
        "severity": "warning"
    },
    "D009": {
        "rule": "financial_needs_data",
        "check": "if 'financials' in themes: any(s.slide_type in ['kpi_dashboard', 'chart_insight'])",
        "severity": "warning"
    },
    "D010": {
        "rule": "slide_count_range",
        "check": "5 <= len(slides) <= 25",
        "severity": "error"
    },
    "D011": {
        "rule": "section_divider_placement",
        "check": "section_divider nie als letzte oder vorletzte Folie",
        "severity": "error"
    },
    "D012": {
        "rule": "max_key_statements",
        "check": "count(key_statement) <= 2",
        "severity": "warning"
    },
}
```

### LLM-basierte Quality Checks (optional, Stage 8)

```python
LLM_REVIEW_CHECKS = {
    "L001": {
        "rule": "narrative_coherence",
        "prompt": "Pruefe, ob die Foliensequenz einen logischen roten Faden hat.",
        "severity": "warning"
    },
    "L002": {
        "rule": "audience_language_fit",
        "prompt": "Pruefe, ob Tonalitaet und Komplexitaet zur Zielgruppe passen.",
        "severity": "warning"
    },
    "L003": {
        "rule": "headline_quality",
        "prompt": "Pruefe, ob alle Headlines spezifisch und aussagekraeftig sind.",
        "severity": "warning"
    },
    "L004": {
        "rule": "redundancy_check",
        "prompt": "Pruefe, ob Inhalte ueber Folien hinweg redundant sind.",
        "severity": "warning"
    },
}
```

### Entscheidungslogik

```
Score-Berechnung:
  - Start: 100 Punkte
  - Pro "error": -15 Punkte
  - Pro "warning": -5 Punkte
  - Pro LLM-Finding: -3 Punkte

Entscheidung:
  score >= 85 -> PASS (direkt ausgeben)
  score 70-84 -> PASS_WITH_WARNINGS (ausgeben + Warnungen anzeigen)
  score 50-69 -> AUTO_FIX (auto-fixable Issues beheben, dann re-check)
  score < 50  -> REGENERATE (betroffene Slides an Stage 3 zurueck)

Regeneration:
  - Max 2 Versuche pro Slide
  - Max 1 Deck-Level-Regeneration
  - Nach Max-Versuchen: Ausgabe mit Warnungen
```

---

## 6. Prompt-Architektur

### Prompt 1: Input Interpreter

```
ROLLE: Du bist ein Briefing-Analyst fuer Geschaeftspraesentationen.

ZIEL: Uebersetze die Nutzeranfrage in ein strukturiertes Briefing.

INPUT: Freitext-Prompt des Nutzers, optional Dokumentinhalte.

OUTPUT-FORMAT: JSON gemaess InterpretedBriefing-Schema.

REGELN:
- Leite Zielgruppe aus Kontext ab wenn nicht explizit genannt.
- Extrahiere alle konkreten Fakten, Zahlen, Namen.
- Identifiziere Content-Themes (financials, strategy, etc.).
- Wenn das Thema unklar ist, setze "needs_clarification": true.
- Halte "goal" auf einen Satz.
- "requested_slide_count": wenn nicht genannt, schaetze sinnvoll (8-15).

WANN IM FLOW: Stage 1, einmal pro Praesentation.
```

### Prompt 2: Storyline Planner

```
ROLLE: Du bist ein Storytelling-Experte fuer Geschaeftspraesentationen.

ZIEL: Erstelle einen narrativen Bogen mit Story-Beats.

INPUT: InterpretedBriefing (JSON).

OUTPUT-FORMAT: JSON gemaess Storyline-Schema.

REGELN:
- Jeder Beat hat genau EINE Kernaussage.
- Kernaussage ist ein vollstaendiger Satz, max 120 Zeichen.
- Waehle einen narrative_arc der zum Thema passt:
  - Quartalsbericht -> situation_complication_resolution
  - Strategiepraesentation -> problem_solution
  - Projektupdate -> chronological
  - Workshop -> thematic_cluster
  - Entscheidungsvorlage -> compare_decide
- Beats muessen einen klaren Spannungsbogen haben.
- Nicht mehr als 1 Beat pro geplanter Folie.
- "opening" und "closing" Beat sind Pflicht.
- Maximal 2 "transition" Beats.
- suggested_slide_types: schlage max 2 passende Typen vor.

WANN IM FLOW: Stage 2, einmal pro Praesentation.
```

### Prompt 3: Slide Planner

```
ROLLE: Du bist ein Praesentations-Architekt.

ZIEL: Uebersetze jeden Story-Beat in einen konkreten SlidePlan.

INPUT:
- Storyline (JSON)
- InterpretedBriefing (JSON)
- ERLAUBTE_SLIDE_TYPEN: [Liste mit Beschreibungen]
- TRANSFORMATIONSREGELN: [Theme->Typ Mappings]
- SEQUENZREGELN: [Reihenfolge-Constraints]
- ZIELGRUPPEN_PROFIL: [Constraints fuer die aktuelle Zielgruppe]

OUTPUT-FORMAT: JSON gemaess PresentationPlan-Schema.

REGELN:
- Du DARFST NUR Slide-Typen aus ERLAUBTE_SLIDE_TYPEN verwenden.
- Du MUSST die TRANSFORMATIONSREGELN beachten.
- Du MUSST die SEQUENZREGELN einhalten.
- Schreibe KEINEN Fliesstext in content_blocks. Nur strukturierte Daten.
- Jede Headline muss spezifisch sein. VERBOTEN: "Ueberblick", "Zusammenfassung".
- headline: max 60 Zeichen.
- subheadline: max 100 Zeichen.
- core_message: vollstaendiger Satz, max 120 Zeichen.
- Fuelle content_blocks mit konkreten Platzhalter-Inhalten (nicht Lorem Ipsum).
- Setze visual.type und visual.image_role nur wenn der Slide-Typ es erlaubt.

WANN IM FLOW: Stage 3, einmal pro Praesentation. Kann bei Regeneration
einzelner Slides erneut aufgerufen werden.
```

### Prompt 4: Content Filler

```
ROLLE: Du bist ein Texter fuer Geschaeftspraesentationen.

ZIEL: Finalisiere den Text fuer EINE Folie.

INPUT:
- Ein einzelner SlidePlan (JSON)
- Zielgruppen-Profil
- Bildstil-Profil
- Quelldokument-Kontext (falls vorhanden)

OUTPUT-FORMAT: JSON gemaess FilledSlide-Schema.

REGELN:
- Schreibe PRAEZISE und KURZ.
- Halte dich EXAKT an die Zeichenlimits des Slide-Typs.
- Bei Zielgruppe "management": Jeder Bullet MUSS einen Bold-Prefix haben.
- Bei Zielgruppe "customer": Sprache muss ueberzeugend, nicht intern sein.
- Bei Zielgruppe "workshop": Sprache darf offener und fragender sein.
- KEIN Marketing-Sprech. Keine leeren Phrasen.
- Jeder Bullet muss einen konkreten Informationsgehalt haben.
- Wenn du den Text nicht sinnvoll kuerzen kannst, melde das als Flag.

WANN IM FLOW: Stage 5, einmal pro Folie (parallelisierbar).
```

### Prompt 5: Quality Reviewer

```
ROLLE: Du bist ein Design-Reviewer fuer Geschaeftspraesentationen.

ZIEL: Bewerte die Qualitaet des gesamten Decks.

INPUT:
- PresentationPlan mit allen FilledSlides (JSON)
- InterpretedBriefing (JSON)
- Bisherige Validierungsergebnisse

OUTPUT-FORMAT: JSON mit Findings pro Check (L001-L004).

REGELN:
- Pruefe narrativen Zusammenhang ueber Folien hinweg.
- Pruefe Zielgruppen-Fit der Sprache.
- Pruefe Headline-Qualitaet (spezifisch vs. generisch).
- Pruefe Redundanzen zwischen Folien.
- Fuer jedes Finding: Erklaere kurz das Problem und schlage Fix vor.
- Bewerte: "acceptable" oder "needs_revision" pro Finding.

WANN IM FLOW: Stage 8, einmal nach Rendering. Optional.
```

### Prompt 6: Slide Regenerator

```
ROLLE: Du bist ein Praesentations-Architekt (wie Prompt 3).

ZIEL: Regeneriere EINE spezifische Folie, die die Validierung nicht bestanden hat.

INPUT:
- Der fehlerhafte SlidePlan (JSON)
- Die spezifischen Validierungsfehler
- Der Kontext der umgebenden Folien (vorherige + naechste)
- Die urspruengliche Storyline-Beat

OUTPUT-FORMAT: Ein einzelner korrigierter SlidePlan (JSON).

REGELN:
- Behebe ALLE gemeldeten Fehler.
- Aendere den Slide-Typ wenn noetig.
- Behalte die core_message wenn moeglich bei.
- Beachte den Kontext der umgebenden Folien.

WANN IM FLOW: Nach Stage 4 oder Stage 8, bei FAIL oder REGENERATE.
```

---

## 7. Template- und Rendering-Strategie

### Grundprinzip

```
LLM entscheidet:        WAS gesagt wird (Inhalt, Struktur, Typ-Auswahl)
Code entscheidet:        WIE es aussieht (Layout, Positionen, Schriften, Farben)
Template entscheidet:    WOMIT es gestaltet wird (Farbpalette, Fonts, Markenidentitaet)
```

### Slide-Typ zu Layout Mapping

Jeder Slide-Typ hat ein deterministic Layout-Blueprint. Das Blueprint definiert:
- Welche Elemente existieren
- Wo sie positioniert sind (in cm, relativ zur Slide-Groesse)
- Welche Schriftgroessen verwendet werden
- Wie viel Platz fuer Content verfuegbar ist

```python
LAYOUT_BLUEPRINTS = {
    "title_hero": {
        "elements": [
            {"type": "headline", "x": 1.5, "y": 8.0, "w": 22.0, "h": 4.0,
             "font_size": 44, "bold": True, "alignment": "left"},
            {"type": "subheadline", "x": 1.5, "y": 12.5, "w": 22.0, "h": 2.0,
             "font_size": 22, "bold": False, "alignment": "left"},
            {"type": "accent_bar", "x": 1.5, "y": 7.0, "w": 4.0, "h": 0.15,
             "fill": "accent_color"}
        ],
        "background": "primary_dark_or_image",
        "whitespace_ratio": 0.6
    },

    "bullets_focused": {
        "elements": [
            {"type": "headline", "x": 1.5, "y": 1.5, "w": 22.0, "h": 2.5,
             "font_size": 28, "bold": True, "alignment": "left"},
            {"type": "bullet_area", "x": 1.5, "y": 5.0, "w": 14.0, "h": 10.0,
             "font_size": 18, "bullet_spacing": 1.2,
             "bold_prefix_size": 18, "bold_prefix_color": "accent_color"},
        ],
        "background": "white_or_light",
        "whitespace_ratio": 0.4
    },

    "kpi_dashboard": {
        "elements": [
            {"type": "headline", "x": 1.5, "y": 1.5, "w": 22.0, "h": 2.0,
             "font_size": 28, "bold": True},
            {"type": "kpi_grid", "x": 1.5, "y": 4.5, "w": 22.0, "h": 10.0,
             "grid_cols": "auto",  # 2-5 basierend auf KPI-Anzahl
             "value_font_size": 40, "label_font_size": 14,
             "trend_icon_size": 18, "delta_font_size": 14,
             "card_padding": 0.8, "card_corner_radius": 0.3}
        ],
        "background": "white_or_light",
        "whitespace_ratio": 0.3
    },

    "three_cards": {
        "elements": [
            {"type": "headline", "x": 1.5, "y": 1.5, "w": 22.0, "h": 2.0,
             "font_size": 28, "bold": True},
            {"type": "card_grid", "x": 1.5, "y": 4.5, "w": 22.0, "h": 11.0,
             "cols": 3, "card_gap": 0.8,
             "card_title_size": 20, "card_body_size": 14,
             "card_bg": "surface_light", "card_corner_radius": 0.3,
             "icon_size": 2.0, "icon_position": "top_center"}
        ],
        "background": "white_or_light",
        "whitespace_ratio": 0.25
    },

    "comparison": {
        "elements": [
            {"type": "headline", "x": 1.5, "y": 1.5, "w": 22.0, "h": 2.0,
             "font_size": 28, "bold": True},
            {"type": "column_left", "x": 1.5, "y": 4.5, "w": 10.5, "h": 11.0,
             "header_size": 20, "body_size": 15, "bg": "surface_light"},
            {"type": "divider", "x": 12.5, "y": 4.5, "w": 0.05, "h": 11.0,
             "color": "border_color"},
            {"type": "column_right", "x": 13.0, "y": 4.5, "w": 10.5, "h": 11.0,
             "header_size": 20, "body_size": 15, "bg": "surface_light"}
        ],
        "background": "white_or_light"
    },

    "timeline": {
        "elements": [
            {"type": "headline", "x": 1.5, "y": 1.5, "w": 22.0, "h": 2.0,
             "font_size": 28, "bold": True},
            {"type": "timeline_track", "x": 1.5, "y": 5.0, "w": 22.0, "h": 10.5,
             "orientation": "horizontal",
             "node_size": 0.8, "node_color": "accent_color",
             "track_color": "border_color", "track_thickness": 0.1,
             "date_size": 12, "title_size": 16, "desc_size": 12}
        ],
        "background": "white_or_light"
    },

    "image_text_split": {
        "elements": [
            {"type": "headline", "x_text_side": 1.5, "y": 1.5, "w": 11.0, "h": 2.0,
             "font_size": 28, "bold": True},
            {"type": "body_area", "x_text_side": 1.5, "y": 4.5, "w": 11.0, "h": 10.0,
             "font_size": 16},
            {"type": "image_area", "x_image_side": 13.0, "y": 0, "w": 12.33, "h": 19.05,
             "object_fit": "cover"}
        ],
        "split_ratio": 0.5,
        "image_side": "alternating"  # links/rechts wechselnd im Deck
    },

    "chart_insight": {
        "elements": [
            {"type": "headline", "x": 1.5, "y": 1.5, "w": 22.0, "h": 2.0,
             "font_size": 28, "bold": True},
            {"type": "chart_area", "x": 1.5, "y": 4.0, "w": 16.0, "h": 11.0},
            {"type": "takeaway_area", "x": 18.5, "y": 4.0, "w": 5.0, "h": 11.0,
             "font_size": 14, "color": "text_muted"}
        ],
        "background": "white_or_light"
    },

    "image_fullbleed": {
        "elements": [
            {"type": "background_image", "x": 0, "y": 0, "w": "full", "h": "full",
             "object_fit": "cover"},
            {"type": "text_overlay", "x": 1.5, "y": 12.0, "w": 15.0, "h": 3.0,
             "font_size": 32, "bold": True, "color": "white",
             "overlay_bg": "rgba(0,0,0,0.5)", "overlay_padding": 0.8}
        ]
    },

    "process_flow": {
        "elements": [
            {"type": "headline", "x": 1.5, "y": 1.5, "w": 22.0, "h": 2.0,
             "font_size": 28, "bold": True},
            {"type": "process_track", "x": 1.5, "y": 4.5, "w": 22.0, "h": 11.0,
             "orientation": "horizontal",
             "step_shape": "rounded_rect", "arrow_style": "chevron",
             "step_number_size": 24, "step_title_size": 16, "step_desc_size": 12,
             "step_bg": "accent_light", "arrow_color": "accent_color"}
        ],
        "background": "white_or_light"
    },

    "agenda": {
        "elements": [
            {"type": "headline", "x": 1.5, "y": 1.5, "w": 22.0, "h": 2.5,
             "font_size": 32, "bold": True},
            {"type": "agenda_list", "x": 1.5, "y": 5.0, "w": 14.0, "h": 10.0,
             "item_size": 20, "number_size": 20, "number_color": "accent_color",
             "item_spacing": 1.5}
        ],
        "background": "white_or_light"
    },

    "key_statement": {
        "elements": [
            {"type": "quote_mark", "x": 3.0, "y": 4.0, "size": 5.0,
             "color": "accent_color", "opacity": 0.15},
            {"type": "statement_text", "x": 4.0, "y": 5.5, "w": 17.0, "h": 6.0,
             "font_size": 32, "bold": True, "alignment": "left",
             "line_spacing": 1.4},
            {"type": "attribution", "x": 4.0, "y": 12.5, "w": 17.0, "h": 1.5,
             "font_size": 16, "color": "text_muted"}
        ],
        "background": "white_or_light"
    },

    "section_divider": {
        "elements": [
            {"type": "section_title", "x": 1.5, "y": 7.0, "w": 22.0, "h": 4.0,
             "font_size": 40, "bold": True, "alignment": "center"},
            {"type": "accent_shape", "x": 10.5, "y": 12.0, "w": 4.0, "h": 0.2,
             "fill": "accent_color"}
        ],
        "background": "primary_dark"
    },

    "closing": {
        "elements": [
            {"type": "headline", "x": 1.5, "y": 5.0, "w": 22.0, "h": 4.0,
             "font_size": 36, "bold": True, "alignment": "center"},
            {"type": "takeaways", "x": 4.0, "y": 10.0, "w": 17.0, "h": 5.0,
             "font_size": 18, "alignment": "center"},
            {"type": "contact", "x": 4.0, "y": 16.0, "w": 17.0, "h": 2.0,
             "font_size": 14, "color": "text_muted", "alignment": "center"}
        ],
        "background": "primary_dark_or_white"
    }
}
```

### Zielgruppen-zu-Style-Mapping

```python
AUDIENCE_STYLES = {
    "management": {
        "headline_size_modifier": 1.1,      # 10% groesser
        "body_size_modifier": 0.9,           # 10% kleiner (weniger Text erwartet)
        "whitespace_modifier": 1.15,         # 15% mehr Weissraum
        "accent_usage": "sparse",            # Akzentfarbe nur fuer Key-Elemente
        "preferred_bg": "white",
        "kpi_value_size_modifier": 1.2,      # Zahlen extra gross
        "bullet_style": "bold_prefix",       # Immer Bold-Prefix bei Bullets
    },
    "team": {
        "headline_size_modifier": 1.0,
        "body_size_modifier": 1.0,
        "whitespace_modifier": 1.0,
        "accent_usage": "moderate",
        "preferred_bg": "white",
        "bullet_style": "standard",
    },
    "customer": {
        "headline_size_modifier": 1.05,
        "body_size_modifier": 0.95,
        "whitespace_modifier": 1.2,          # Viel Weissraum, professionell
        "accent_usage": "bold",              # Staerkere Farbakzente
        "preferred_bg": "alternating",       # Abwechselnd weiss und Akzent-BG
        "image_frequency": "high",
        "bullet_style": "icon_prefix",       # Wenn moeglich Icons statt Dots
    },
    "workshop": {
        "headline_size_modifier": 1.0,
        "body_size_modifier": 1.05,
        "whitespace_modifier": 0.9,          # Etwas dichter, mehr Content
        "accent_usage": "playful",           # Mehrere Akzentfarben
        "preferred_bg": "white",
        "bullet_style": "standard",
    },
}
```

### Bildstil-zu-Visual-Mapping

```python
IMAGE_STYLE_RENDERING = {
    "photo": {
        "image_generation_prompt_prefix": "Professional business photography, ",
        "image_treatment": "full_color",
        "corner_radius": 0,                  # Keine Eckenrundung bei Photos
        "shadow": True,
        "icon_style": None,                  # Keine Icons
    },
    "illustration": {
        "image_generation_prompt_prefix": "Modern flat illustration style, ",
        "image_treatment": "full_color",
        "corner_radius": 0.3,
        "shadow": False,
        "icon_style": "illustrated",
    },
    "minimal": {
        "image_generation_prompt_prefix": None,  # Keine Bildgenerierung
        "image_treatment": "geometric_shapes",
        "corner_radius": 0,
        "shadow": False,
        "icon_style": "line_icons",          # Nur Line-Icons
        "accent_shapes": True,               # Geometrische Akzentformen
    },
    "data_visual": {
        "image_generation_prompt_prefix": None,
        "image_treatment": "charts_only",
        "chart_style": "modern_flat",
        "chart_colors": "from_template_palette",
        "icon_style": "data_icons",
    },
    "none": {
        "image_generation_prompt_prefix": None,
        "image_treatment": "none",
        "icon_style": None,
        "accent_shapes": False,
    },
}
```

### Was NICHT dem LLM ueberlassen wird

Das folgende wird ausschliesslich im Code determiniert:

1. **Schriftgroessen** -- fest pro Element-Typ und Zielgruppe
2. **Positionen** -- Pixel-/cm-genaue Platzierung aus Blueprints
3. **Abstaende** -- Padding, Margins, Gaps aus Blueprints
4. **Farben** -- aus Template-Palette oder Custom Color
5. **Schriftarten** -- aus Template oder Custom Font
6. **Hintergruende** -- aus Layout-Blueprint + Zielgruppen-Stil
7. **Bildgroessen und -positionen** -- aus Blueprint, Bild wird eingepasst
8. **Chart-Styling** -- Farben, Achsen, Grid aus Template-Palette
9. **Weissraum-Verteilung** -- aus Blueprint + Zielgruppen-Modifier
10. **Element-Reihenfolge** -- fest pro Slide-Typ

---

## 8. Modul- und Projektstruktur

```
pptx-service/
  app/
    # --- Pipeline Stages ---
    pipeline/
      __init__.py
      orchestrator.py          # Steuert die 8-Stufen-Pipeline
      stage_input.py           # Stage 1: Input Interpreter
      stage_storyline.py       # Stage 2: Storyline Planner
      stage_slide_planner.py   # Stage 3: Slide Planner
      stage_validator.py       # Stage 4: Schema Validator
      stage_content_filler.py  # Stage 5: Content Filler
      stage_layout_engine.py   # Stage 6: Template Mapper + Layout Engine
      stage_renderer.py        # Stage 7: PPTX Renderer
      stage_review.py          # Stage 8: Post-Generation Review

    # --- Prompts ---
    prompts/
      __init__.py
      interpreter_prompt.py
      storyline_prompt.py
      slide_planner_prompt.py
      content_filler_prompt.py
      quality_reviewer_prompt.py
      regenerator_prompt.py
      prompt_utils.py          # Audience/ImageStyle Profile-Texte

    # --- Schemas & Models ---
    schemas/
      __init__.py
      briefing.py              # InterpretedBriefing Pydantic Model
      storyline.py             # Storyline Pydantic Model
      slide_plan.py            # SlidePlan, PresentationPlan Models
      content_blocks.py        # ContentBlock Variants
      filled_slide.py          # FilledSlide Model
      render_instruction.py    # RenderInstruction Model
      quality_report.py        # QualityReport Model
      chart_spec.py            # ChartSpec Model

    # --- Validators ---
    validators/
      __init__.py
      slide_rules.py           # Slide-Level Checks (S001-S013)
      deck_rules.py            # Deck-Level Checks (D001-D012)
      type_constraints.py      # Pro-Typ Content-Constraints
      sequence_rules.py        # Sequenz-Regeln
      auto_fixes.py            # Automatische Korrekturen

    # --- Slide Types ---
    slide_types/
      __init__.py
      registry.py              # SlideTypeRegistry: alle erlaubten Typen
      type_definitions.py      # Typ-Definitionen mit Constraints
      transformation_map.py    # Theme->Typ und Beat->Typ Mappings
      audience_modifiers.py    # Zielgruppen-spezifische Typ-Regeln
      image_style_modifiers.py # Bildstil-spezifische Regeln

    # --- Layout & Templates ---
    layouts/
      __init__.py
      blueprints.py            # Layout-Blueprints pro Slide-Typ
      audience_styles.py       # Zielgruppen-Style-Modifier
      image_styles.py          # Bildstil-Rendering-Config
      element_calculator.py    # Berechnet finale Positionen/Groessen
      template_adapter.py      # Passt Blueprints an User-Templates an

    # --- Rendering ---
    renderers/
      __init__.py
      pptx_renderer.py         # Hauptrenderer: RenderInstruction -> pptx
      shape_factory.py         # Erzeugt python-pptx Shapes
      text_renderer.py         # Text-Formatting, Auto-Fit
      chart_renderer.py        # Chart-Rendering via matplotlib
      image_renderer.py        # Bild-Platzierung und -Generierung
      kpi_renderer.py          # KPI-Dashboard-Rendering
      timeline_renderer.py     # Timeline-Rendering
      process_renderer.py      # Process-Flow-Rendering
      card_renderer.py         # Card-Grid-Rendering
      comparison_renderer.py   # Comparison-Spalten-Rendering

    # --- Services (bestehend, angepasst) ---
    services/
      llm_service.py           # LLM-Aufrufe (Gemini), structured output
      image_service.py         # Imagen 3.0 Bildgenerierung
      template_service.py      # Template-Profil laden
      chart_service.py         # matplotlib Charts (bestehend)

    # --- API ---
    api/
      routes/
        generate.py            # POST /generate -> Pipeline starten
        validate.py            # POST /validate -> nur Validierung
        preview.py             # POST /preview -> Marp-Preview (bestehend)

    # --- Config ---
    config/
      slide_type_catalog.yaml  # Slide-Typ-Definitionen als YAML
      validation_rules.yaml    # Validator-Regeln als YAML
      audience_profiles.yaml   # Zielgruppen-Profile
      image_style_profiles.yaml

backend/
  src/
    chat/
      chat.service.ts          # Vereinfacht: ruft Pipeline auf, kein Mega-Prompt
      chat.controller.ts
    export/
      export.service.ts        # Ruft pptx-service Pipeline auf
    preview/
      preview.service.ts       # Marp-Preview (bestehend)

frontend/
  src/app/
    features/
      briefing/                # Step 1+2: Setup + Chat (vereint)
      plan-review/             # NEU: Step 3 - PresentationPlan reviewen
      slide-review/            # Step 4: Einzelfolien pruefen
      export-panel/            # Step 5: Export
```

### Neue vs. bestehende Module

```
BESTEHEND (anpassen):
  - services/image_service.py -> unveraendert, wird von Stage 7 aufgerufen
  - services/chart_service.py -> unveraendert, wird von Stage 7 aufgerufen
  - services/template_service.py -> erweitern um Layout-Adapter
  - api/routes/generate.py -> neuer Einstiegspunkt fuer Pipeline

NEU (bauen):
  - pipeline/* -> komplette Pipeline-Orchestrierung
  - prompts/* -> alle Prompt-Definitionen
  - schemas/* -> Pydantic Models
  - validators/* -> Validierungslogik
  - slide_types/* -> Typ-Registry und Mappings
  - layouts/* -> Layout-Blueprints und Calculator
  - renderers/* -> Typ-spezifische Renderer

ENTFERNT:
  - services/pptx_service.py -> ersetzt durch pipeline/orchestrator.py + renderers/
  - services/markdown_service.py -> nicht mehr noetig (kein Markdown-Zwischenformat)
  - Backend BASE_SYSTEM_PROMPT -> ersetzt durch Prompt-Suite
```

---

## 9. Umsetzungsplan

### Phase 1: Schnellster Hebel (1-2 Wochen)

**Ziel**: Sofort bessere Ergebnisse ohne Architektur-Komplettumbau.

```
1.1  Slide-Typ-Registry bauen (slide_types/registry.py)
     - 14 Typen definieren mit Constraints
     - Content-Limits pro Typ
     -> Aufwand: 1 Tag

1.2  Pydantic-Schemas definieren (schemas/*)
     - SlidePlan, PresentationPlan, ContentBlock
     - Validierung direkt eingebaut
     -> Aufwand: 1 Tag

1.3  Slide-Level Validator bauen (validators/slide_rules.py)
     - 13 Regeln implementieren
     - Auto-Fix fuer Zeichenlimits und Bullet-Count
     -> Aufwand: 1 Tag

1.4  Deck-Level Validator bauen (validators/deck_rules.py)
     - 12 Regeln implementieren
     -> Aufwand: 0.5 Tage

1.5  Bestehenden Prompt aufteilen in 2 LLM-Calls:
     - Call 1: Slide Planner (structured output -> PresentationPlan JSON)
     - Call 2: Content Filler (pro Slide, parallel)
     - Validator dazwischen
     -> Aufwand: 2-3 Tage

1.6  Layout-Blueprints fuer Top-5-Typen implementieren:
     - title_hero, bullets_focused, kpi_dashboard, three_cards, chart_insight
     -> Aufwand: 3-4 Tage
```

**Ergebnis Phase 1**: Strukturierte Folien statt freiem Markdown. Validierung. 5 echte Layouts.

### Phase 2: Architektur-Umbau (2-3 Wochen)

**Ziel**: Vollstaendige Pipeline mit allen Stages.

```
2.1  Pipeline-Orchestrator bauen
     - 8 Stages mit klaren Interfaces
     - Fehlerbehandlung und Regeneration-Loop
     -> Aufwand: 2 Tage

2.2  Stage 1 (Input Interpreter) + Stage 2 (Storyline Planner)
     - Prompts definieren und testen
     - Structured Output via Gemini
     -> Aufwand: 2-3 Tage

2.3  Verbleibende 9 Layout-Blueprints implementieren
     - timeline, process_flow, comparison, image_text_split,
       image_fullbleed, key_statement, section_divider, agenda, closing
     -> Aufwand: 5-7 Tage

2.4  Typ-spezifische Renderer bauen
     - Ein Renderer pro Slide-Typ
     - Teilen gemeinsame Basis (shape_factory, text_renderer)
     -> Aufwand: 3-5 Tage (parallel zu 2.3)

2.5  Transformationslogik implementieren
     - Theme->Typ Mappings
     - Zielgruppen-Modifier
     - Bildstil-Modifier
     - Sequenz-Regeln
     -> Aufwand: 2 Tage

2.6  Markdown-Zwischenformat eliminieren
     - Backend ruft Pipeline direkt auf
     - Kein Marp-Markdown mehr noetig fuer Generierung
     - Marp bleibt nur fuer Live-Preview
     -> Aufwand: 1-2 Tage
```

**Ergebnis Phase 2**: Vollstaendige Pipeline. Alle 14 Slide-Typen. Deterministische Layouts.

### Phase 3: Qualitaetssteigerung (1-2 Wochen)

**Ziel**: Automatische Qualitaetssicherung und -verbesserung.

```
3.1  Stage 8: Post-Generation Review
     - LLM-basierte Checks (L001-L004)
     - Score-Berechnung
     - Regeneration-Flow
     -> Aufwand: 2-3 Tage

3.2  Auto-Fix-Engine erweitern
     - Text-Kuerzung mit LLM
     - Typ-Wechsel bei Validierungsfehlern
     - Bullet-Konsolidierung
     -> Aufwand: 2 Tage

3.3  Template-Adapter verfeinern
     - User-Templates besser integrieren
     - Farb-DNA auf Blueprints anwenden
     - Font-Mapping
     -> Aufwand: 2-3 Tage

3.4  Bildintegration verbessern
     - image_role-basierte Platzierung
     - Bild-Prompt aus Slide-Kontext generieren
     - Fallback-Logik fuer fehlgeschlagene Bildgenerierung
     -> Aufwand: 2 Tage
```

**Ergebnis Phase 3**: Automatische Qualitaetskontrolle. Bessere Bilder. Template-Integration.

### Phase 4: Review / UX / Iteration (laufend)

```
4.1  Frontend: PresentationPlan-Review-Step
     - User sieht geplante Folien vor Rendering
     - Kann Slide-Typen aendern, Reihenfolge anpassen
     -> Aufwand: 3-5 Tage

4.2  Frontend: Slide-Typ-Vorschau
     - Thumbnail-Preview pro Slide-Typ
     - Drag & Drop Reihenfolge
     -> Aufwand: 2-3 Tage

4.3  A/B-Testing-Framework
     - Alte vs. neue Pipeline vergleichen
     - Metriken: Folientyp-Vielfalt, Textmenge, Validierungsscore
     -> Aufwand: 2 Tage

4.4  Prompt-Tuning basierend auf echten Ergebnissen
     - Systematisches Testen mit 10-20 realen Briefings
     - Prompt-Iteration pro Stage
     -> Aufwand: laufend
```

### Kritischer Pfad

```
Phase 1.1 -> 1.2 -> 1.5 -> 1.3 -> 1.6
                                    |
                              Phase 2.1 -> 2.2 -> 2.3/2.4 -> 2.5 -> 2.6
                                                                      |
                                                                Phase 3.1 -> 3.2
```

**Groesster Qualitaetshebel**: Phase 1.5 (Prompt-Aufteilung) + Phase 1.6 (Layout-Blueprints). Diese beiden Schritte allein werden die Qualitaet dramatisch verbessern.

---

## 10. Konkrete Artefakte

### Artefakt 1: JSON-Schema fuer PresentationPlan

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PresentationPlan",
  "type": "object",
  "required": ["audience", "image_style", "slides"],
  "properties": {
    "audience": {
      "type": "string",
      "enum": ["team", "management", "customer", "workshop"]
    },
    "image_style": {
      "type": "string",
      "enum": ["photo", "illustration", "minimal", "data_visual", "none"]
    },
    "slides": {
      "type": "array",
      "minItems": 5,
      "maxItems": 25,
      "items": { "$ref": "#/definitions/SlidePlan" }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "total_slides": { "type": "integer" },
        "estimated_duration_minutes": { "type": "integer" },
        "content_density": { "type": "string", "enum": ["light", "medium", "dense"] }
      }
    }
  },
  "definitions": {
    "SlidePlan": {
      "type": "object",
      "required": ["position", "slide_type", "headline", "core_message", "content_blocks"],
      "properties": {
        "position": { "type": "integer", "minimum": 1 },
        "slide_type": {
          "type": "string",
          "enum": [
            "title_hero", "section_divider", "key_statement", "bullets_focused",
            "three_cards", "kpi_dashboard", "image_text_split", "comparison",
            "timeline", "process_flow", "chart_insight", "image_fullbleed",
            "agenda", "closing"
          ]
        },
        "headline": { "type": "string", "maxLength": 60 },
        "subheadline": { "type": "string", "maxLength": 100 },
        "core_message": { "type": "string", "maxLength": 120 },
        "content_blocks": {
          "type": "array",
          "items": { "$ref": "#/definitions/ContentBlock" }
        },
        "visual": { "$ref": "#/definitions/Visual" },
        "speaker_notes": { "type": "string", "maxLength": 500 }
      }
    },
    "ContentBlock": {
      "type": "object",
      "required": ["type"],
      "properties": {
        "type": {
          "type": "string",
          "enum": ["text", "bullets", "kpi", "quote", "label_value",
                   "comparison_column", "process_step", "timeline_entry", "card"]
        },
        "items": { "type": "array" },
        "label": { "type": "string" },
        "value": { "type": "string" },
        "trend": { "type": "string", "enum": ["up", "down", "neutral"] },
        "delta": { "type": "string" },
        "text": { "type": "string" },
        "attribution": { "type": "string" },
        "pairs": { "type": "array" },
        "column_label": { "type": "string" },
        "date": { "type": "string" },
        "title": { "type": "string" },
        "description": { "type": "string" },
        "step_number": { "type": "integer" },
        "body": { "type": "string" },
        "icon_hint": { "type": "string" }
      }
    },
    "Visual": {
      "type": "object",
      "properties": {
        "type": { "type": "string", "enum": ["photo", "illustration", "icon", "chart", "diagram", "none"] },
        "image_role": { "type": "string", "enum": ["hero", "supporting", "decorative", "evidence", "none"] },
        "image_description": { "type": "string", "maxLength": 200 },
        "chart_spec": { "$ref": "#/definitions/ChartSpec" }
      }
    },
    "ChartSpec": {
      "type": "object",
      "required": ["chart_type", "data"],
      "properties": {
        "chart_type": { "type": "string", "enum": ["bar", "horizontal_bar", "stacked_bar", "line", "pie", "donut"] },
        "title": { "type": "string", "maxLength": 50 },
        "data": {
          "type": "object",
          "properties": {
            "labels": { "type": "array", "items": { "type": "string" } },
            "series": { "type": "array", "items": {
              "type": "object",
              "properties": {
                "name": { "type": "string" },
                "values": { "type": "array", "items": { "type": "number" } }
              }
            }}
          }
        },
        "unit": { "type": "string" },
        "highlight_index": { "type": "integer" }
      }
    }
  }
}
```

### Artefakt 2: Harte Validator-Regeln (kompakte Liste)

```
SLIDE-LEVEL:
  S001  headline_required          ERROR   Jede Folie braucht Headline
  S002  headline_max_60            ERROR   Headline max 60 Zeichen [auto-fix: truncate]
  S003  core_message_required      ERROR   Kernaussage Pflicht
  S004  valid_slide_type           ERROR   Typ muss aus Katalog sein
  S005  bullets_max_3              ERROR   Max 3 Bullets [auto-fix: trim]
  S006  bullet_max_60_chars        ERROR   Bullet max 60 Zeichen [auto-fix: truncate]
  S007  no_generic_headline        WARN    Keine generischen Headlines
  S008  content_matches_type       ERROR   Content-Bloecke muessen zum Typ passen
  S009  visual_role_valid          WARN    Dekorativ nur bei image_fullbleed
  S010  text_density_limit         ERROR   Max Zeichen pro Typ [auto-fix: shorten]
  S011  kpi_numeric_value          ERROR   KPI-Werte muessen Zahlen sein
  S012  timeline_min_3             ERROR   Timeline min 3 Eintraege
  S013  speaker_notes_present      WARN    Speaker Notes empfohlen

DECK-LEVEL:
  D001  starts_title_hero          ERROR   Erste Folie muss title_hero sein
  D002  ends_closing               ERROR   Letzte Folie muss closing sein
  D003  min_3_types                ERROR   Min 3 verschiedene Slide-Typen
  D004  no_consecutive_bullets     ERROR   Keine 2 bullets_focused hintereinander
  D005  no_3_same_type             WARN    Keine 3 gleichen Typen hintereinander
  D006  audience_fit               WARN    Zielgruppen-Pflichttypen vorhanden
  D007  image_style_compliance     ERROR   Visuals passen zum Bildstil
  D008  history_needs_timeline     WARN    History-Thema braucht Timeline
  D009  financial_needs_data       WARN    Finanz-Thema braucht KPI/Chart
  D010  slide_count_5_25           ERROR   5-25 Folien
  D011  divider_not_at_end         ERROR   section_divider nicht am Ende
  D012  max_2_key_statements       WARN    Max 2 key_statement im Deck
```

### Artefakt 3: Erlaubte Slide-Typen (kompakt)

```
TYPE                 CONTENT_BLOCKS_ALLOWED          MAX_TEXT  IMAGE
title_hero           -                               130      optional hero
section_divider      -                               100      none
key_statement        quote                           150      none
bullets_focused      bullets (max 3)                 250      none
three_cards          card (exactly 3)                400      optional icons
kpi_dashboard        kpi (2-5)                       300      none
image_text_split     bullets (max 3) or text         250      required supporting/evidence
comparison           comparison_column (exactly 2)   350      none
timeline             timeline_entry (3-6)            500      none
process_flow         process_step (3-5)              450      none
chart_insight        chart + bullets (max 2)         200      chart required
image_fullbleed      text overlay (max 60 chars)      60      required hero
agenda               bullets (3-6, als Agenda)       280      none
closing              bullets (max 3) + contact       250      none
```

### Artefakt 4: Mapping-Tabelle Zielgruppe x Bildstil x Slide-Typ

```
                    photo           illustration    minimal         data_visual     none
management:
  BEVORZUGT         image_text      three_cards     key_statement   kpi_dashboard   key_statement
                    kpi_dashboard   kpi_dashboard   kpi_dashboard   chart_insight   kpi_dashboard
                    chart_insight   key_statement   bullets_focused                 bullets_focused
  VERBOTEN          -               -               image_fullbleed image_fullbleed image_fullbleed
                                                                                    image_text_split

team:
  BEVORZUGT         image_text      process_flow    bullets_focused chart_insight   bullets_focused
                    bullets_focused comparison      process_flow    kpi_dashboard   process_flow
                    process_flow    bullets_focused comparison                      comparison
  VERBOTEN          -               -               image_fullbleed image_fullbleed image_fullbleed
                                                                                    image_text_split

customer:
  BEVORZUGT         image_fullbleed image_fullbleed key_statement   chart_insight   key_statement
                    image_text      image_text      three_cards     comparison      three_cards
                    key_statement   three_cards     closing                         closing
  VERBOTEN          -               -               -               image_fullbleed image_fullbleed
                                                                                    image_text_split

workshop:
  BEVORZUGT         image_text      three_cards     three_cards     comparison      three_cards
                    three_cards     comparison      comparison      process_flow    comparison
                    comparison      process_flow    process_flow                    process_flow
  VERBOTEN          kpi_dashboard   kpi_dashboard   image_fullbleed image_fullbleed image_fullbleed
                                                    kpi_dashboard                   image_text_split
```

### Artefakt 5: Prompt-Suite (Dateinamen + Kurzbeschreibung)

```
prompts/
  interpreter_prompt.py       # User-Input -> InterpretedBriefing JSON
                               # Input: Freitext. Output: Briefing JSON.
                               # 1 LLM-Call.

  storyline_prompt.py         # Briefing -> Storyline mit Beats
                               # Input: Briefing JSON. Output: Storyline JSON.
                               # 1 LLM-Call.

  slide_planner_prompt.py     # Storyline -> PresentationPlan mit SlidePlans
                               # Input: Storyline + Briefing + Typ-Katalog + Regeln.
                               # Output: PresentationPlan JSON.
                               # 1 LLM-Call (structured output).

  content_filler_prompt.py    # SlidePlan -> FilledSlide mit finalen Texten
                               # Input: 1 SlidePlan + Audience Profile.
                               # Output: 1 FilledSlide JSON.
                               # N LLM-Calls (1 pro Folie, parallelisierbar).

  quality_reviewer_prompt.py  # Fertiges Deck -> QualityReport
                               # Input: Alle FilledSlides + Briefing.
                               # Output: Findings JSON.
                               # 1 LLM-Call (optional).

  regenerator_prompt.py       # Fehlerhafte Folie -> Korrigierter SlidePlan
                               # Input: SlidePlan + Fehler + Kontext.
                               # Output: 1 korrigierter SlidePlan JSON.
                               # N LLM-Calls (1 pro fehlerhafte Folie).

  prompt_utils.py             # Audience Profiles, ImageStyle Profiles als Text
                               # Wird in andere Prompts injected.
```

### Artefakt 6: Pseudocode-Flow des Gesamtsystems

```python
async def generate_presentation(user_input: str, files: list[File],
                                 audience: str, image_style: str,
                                 template_id: str | None) -> PptxResult:

    # ── Stage 1: Input Interpretation ──
    briefing = await llm.structured_call(
        prompt=INTERPRETER_PROMPT,
        input={"user_input": user_input, "files": extract_text(files)},
        output_schema=InterpretedBriefing,
    )
    briefing.audience = audience  # Override mit UI-Auswahl
    briefing.image_style = image_style

    if briefing.needs_clarification:
        return ClarificationNeeded(briefing.clarification_questions)

    # ── Stage 2: Storyline Planning ──
    storyline = await llm.structured_call(
        prompt=STORYLINE_PROMPT,
        input={"briefing": briefing},
        output_schema=Storyline,
    )
    if not validate_storyline(storyline):
        storyline = await llm.structured_call(  # 1 Retry
            prompt=STORYLINE_PROMPT + "\nVORHERIGER VERSUCH WAR FEHLERHAFT.",
            input={"briefing": briefing},
            output_schema=Storyline,
        )

    # ── Stage 3: Slide Planning ──
    type_catalog = SlideTypeRegistry.get_catalog(audience, image_style)
    transform_rules = TransformationMap.get_rules(audience, image_style)

    plan = await llm.structured_call(
        prompt=SLIDE_PLANNER_PROMPT,
        input={
            "storyline": storyline,
            "briefing": briefing,
            "allowed_types": type_catalog,
            "transform_rules": transform_rules,
            "sequence_rules": SEQUENCE_RULES,
        },
        output_schema=PresentationPlan,
    )

    # ── Stage 4: Schema Validation ──
    validation = validate_plan(plan)  # Deterministic, no LLM

    for attempt in range(MAX_REGEN_ATTEMPTS):  # max 2
        failed_slides = [s for s in validation.slide_results if not s.passed]
        if not failed_slides:
            break

        for failed in failed_slides:
            context = get_surrounding_slides(plan, failed.slide_index)
            fixed = await llm.structured_call(
                prompt=REGENERATOR_PROMPT,
                input={
                    "failed_slide": plan.slides[failed.slide_index],
                    "errors": failed.issues,
                    "context": context,
                    "beat": storyline.beats[failed.slide_index],
                },
                output_schema=SlidePlan,
            )
            plan.slides[failed.slide_index] = fixed

        validation = validate_plan(plan)

    # ── Stage 5: Content Filling ──
    audience_profile = get_audience_profile(audience)
    image_style_profile = get_image_style_profile(image_style)

    filled_slides = await asyncio.gather(*[
        llm.structured_call(
            prompt=CONTENT_FILLER_PROMPT,
            input={
                "slide_plan": slide,
                "audience_profile": audience_profile,
                "image_style_profile": image_style_profile,
            },
            output_schema=FilledSlide,
        )
        for slide in plan.slides
    ])

    # Apply hard limits (auto-fix)
    for slide in filled_slides:
        slide = auto_fix_text_limits(slide)

    # ── Stage 6: Template Mapping + Layout Engine ──
    template_profile = load_template(template_id) if template_id else None
    custom_style = {"color": briefing.custom_color, "font": briefing.custom_font}

    render_instructions = []
    for i, slide in enumerate(filled_slides):
        blueprint = get_blueprint(slide.slide_type)
        style_modifiers = AUDIENCE_STYLES[audience]
        image_config = IMAGE_STYLE_RENDERING[image_style]

        instruction = layout_engine.calculate(
            slide=slide,
            blueprint=blueprint,
            template=template_profile,
            custom_style=custom_style,
            style_modifiers=style_modifiers,
            image_config=image_config,
            slide_index=i,
            total_slides=len(filled_slides),
        )
        render_instructions.append(instruction)

    # ── Stage 7: PPTX Rendering ──
    pptx_bytes = pptx_renderer.render(
        instructions=render_instructions,
        template_path=template_profile.path if template_profile else None,
    )

    # ── Stage 8: Post-Generation Review ──
    # Deterministic checks on rendered content
    quality = run_deck_checks(filled_slides, plan, briefing)

    # Optional LLM review
    if quality.overall_score >= 50:  # Only if worth reviewing
        llm_findings = await llm.structured_call(
            prompt=QUALITY_REVIEWER_PROMPT,
            input={
                "slides": filled_slides,
                "briefing": briefing,
                "current_score": quality.overall_score,
            },
            output_schema=LlmQualityFindings,
        )
        quality.add_findings(llm_findings)

    # ── Decision ──
    if quality.overall_score >= 70:
        return PptxResult(
            pptx=pptx_bytes,
            plan=plan,
            quality=quality,
            slides=filled_slides,
        )
    elif quality.has_regeneratable_slides and not already_regenerated:
        # Regenerate worst slides and re-run from Stage 3
        return await regenerate_and_retry(plan, quality, storyline, briefing)
    else:
        # Output with warnings
        return PptxResult(
            pptx=pptx_bytes,
            plan=plan,
            quality=quality,
            slides=filled_slides,
            warnings=quality.all_findings,
        )
```

---

## Risiken und typische Fehlerquellen

1. **LLM ignoriert Typ-Constraints**: Structured Output (JSON Mode) mit striktem Schema reduziert das Risiko. Validator faengt den Rest ab. Risiko: mittel.

2. **Regenerations-Loop**: Wenn ein Slide nach 2 Versuchen nicht valid ist, muss ein Fallback-Typ erzwungen werden. Nie unendlich loopen.

3. **Latenz**: 4+ LLM-Calls statt 1 erhoehen die Gesamtdauer. Mitigation: Content Filler parallelisieren (Stage 5), Storyline + Slide Planning kann oft in 1 Call kombiniert werden wenn noetig.

4. **Template-Adapter-Komplexitaet**: Bestehende User-Templates auf die 14 Blueprints zu mappen ist nicht-trivial. Start: nur Custom Color/Font, kein Template-Mapping in Phase 1.

5. **Prompt-Drift**: Bei 6 Prompts steigt das Risiko inkonsistenter Ergebnisse. Mitigation: Shared prompt_utils.py fuer Audience/Style Profile-Texte.

6. **Over-Engineering**: 14 Slide-Typen mit je eigenem Renderer ist viel Code. Start mit 5 Typen in Phase 1, Rest schrittweise.

---

## Annahmen

- **LLM**: Gemini 2.x mit zuverlaessigem JSON/Structured Output Mode.
- **Bildgenerierung**: Imagen 3.0 bleibt als Bildquelle, aber image_role steuert ob und wie Bilder verwendet werden.
- **Template-System**: Bestehende .pptx-Templates koennen weiterhin als Basis dienen, aber die Layout-Logik wird primaer durch Blueprints gesteuert.
- **Frontend**: Der Wizard-Flow wird um einen "Plan Review"-Step erweitert (zwischen Generierung und Folien-Review).
- **Performance**: 4-6 LLM-Calls sind in 15-30 Sekunden machbar (Gemini ist schnell). Content Filler laeuft parallel.
