# V2 Pipeline Refactoring — Verbindlicher Umsetzungsplan

---

## 1. KERNDIAGNOSE

Der zentrale Fehler: **Die Qualitaetskontrolle sitzt an der falschen Stelle und ist zu weich.**

Konkret:

1. **Validation vor Content-Filling.** Stage 4 validiert den Plan, aber Stage 5 fuellt den Text. Danach validiert niemand mehr. Die Folien koennen nach dem Filling unterfuellt, thematisch schwach oder mit generischen Titeln befuellt sein — ohne dass ein Validator sie jemals sieht.

2. **Titel-Logik rein prompt-basiert.** Die S014-Heuristik (`len(words) <= 3 and len(headline) < 30`) ist zu simpel. Ein Titel wie "Bier im Mittelalter" hat 3 Worte und 19 Zeichen, wird aber nicht immer gefangen. Es gibt keine linguistische Pruefung auf Verb oder Praedikat.

3. **Topic-Klassifikation fehlt als eigener Schritt.** Der Interpreter soll Thementyp erkennen, Topic-spezifische Deck-Regeln erzwingen UND das Briefing extrahieren — zu viel fuer einen Prompt. Historische Themen werden nur per Keyword-Suche in D009 erkannt, nicht per expliziter Klassifikation.

4. **Kein Post-Fill-Validator.** Nach Stage 5 fehlt ein Validator, der die finalen Texte prueft — headline-Qualitaet, Block-Befuellung, Bild-Funktion. Der Stage-8-Reviewer ist ein Stub (`return validation_quality`).

5. **Regeneration nur auf Plan-Ebene.** `_regenerate_slide` ersetzt den Plan, aber nicht den gefuellten Text. Stage 5 laeuft spaeter nochmal drueber, aber wenn Stage 5 einen schwachen Titel liefert, repariert niemand das.

6. **SlideTypeDefinition hat keine Mindestanforderungen.** `required_fields` ist bei allen Typen nur `["headline"]`. Die eigentlichen Mindestanforderungen (3 Cards, 4 Timeline-Eintraege) stehen nur im Prompt und in S015 — aber nicht in der Registry, die der Code auswerten koennte.

---

## 2. ZIELARCHITEKTUR

```
Input → [1: Interpret] → [2: Classify] → [3: Storyline] → [4: Slide Plan]
     → [5: Plan Validate] → [6: Plan Regenerate] → [7: Content Fill]
     → [8: Fill Validate] → [9: Fill Regenerate] → [10: Layout]
     → [11: Render] → [12: Post-Review]
```

### Stage 1: Input Interpreter
- **Zweck:** User-Input + Dokument in strukturiertes Briefing uebersetzen.
- **Input:** `user_input: str`, `document_text: str`
- **Output:** `InterpretedBriefing`
- **LLM:** Extrahiert Fakten, Themen, Constraints. Structured JSON output.
- **Code:** Fallback-Defaults fuer fehlende Felder. Validiert `requested_slide_count` Range.
- **Fehler:** Fallback auf Minimal-Briefing mit Topic = Input.

### Stage 2: Topic Classifier (NEU)
- **Zweck:** Thementyp erkennen und Deck-Constraints ableiten.
- **Input:** `InterpretedBriefing`
- **Output:** `TopicClassification` (topic_type, required_slide_types, forbidden_patterns, deck_template, narrative_arc)
- **LLM:** Nein. Deterministisch.
- **Code:** Keyword-Matching auf `content_themes` + `topic` + `key_facts`. Liefert harte Constraints.
- **Regeln:**
  - Keywords `geschichte, history, entwicklung, chronolog, evolution, jahrhundert, epoche` → `topic_type: "historical"`
  - Keywords `strategie, roadmap, plan, vision` → `topic_type: "strategy"`
  - Keywords `vergleich, versus, alternativen, gegenueber` → `topic_type: "comparison"`
  - Keywords `kpi, kennzahlen, performance, metriken, analyse` → `topic_type: "analytics"`
  - Keywords `workshop, diskussion, brainstorm` → `topic_type: "workshop"`
  - Keywords `update, status, quartal, monatsbericht` → `topic_type: "executive_update"`
  - Sonst: `topic_type: "general"`
- **Output-Beispiel:**
  ```json
  {
    "topic_type": "historical",
    "narrative_arc": "chronological",
    "required_slide_types": ["timeline"],
    "recommended_slide_types": ["comparison", "image_text_split"],
    "forbidden_patterns": ["no_consecutive_bullets_only", "no_all_same_type"],
    "min_content_slides": 6,
    "deck_template": "historical_short"
  }
  ```
- **Fehler:** Fallback auf `"general"`.

### Stage 3: Storyline Planner
- **Zweck:** Narrative Arc mit Story Beats.
- **Input:** `InterpretedBriefing`, `TopicClassification`
- **Output:** `Storyline`
- **LLM:** Erzeugt Beats mit core_message, beat_type, suggested_slide_types.
- **Code:** Injiziert `narrative_arc` aus TopicClassification. Validiert Beat-Count gegen `requested_slide_count`. Erzwingt opening/closing.
- **Fehler:** Fallback-Storyline mit generischen Beats.

### Stage 4: Slide Planner
- **Zweck:** Beats in konkrete SlidePlans uebersetzen.
- **Input:** `Storyline`, `InterpretedBriefing`, `TopicClassification`
- **Output:** `PresentationPlan`
- **LLM:** Waehlt slide_type, schreibt headline, definiert content_blocks und visual.
- **Code:** Injiziert TopicClassification-Constraints in Prompt. Erzwingt Sequence Rules.
- **Fehler:** Retry 1x, dann Abort.

### Stage 5: Plan Validator
- **Zweck:** Harte Pruefung des Plans VOR Content-Filling.
- **Input:** `PresentationPlan`, `TopicClassification`
- **Output:** `ValidationResult` (pass/fail + findings per slide)
- **LLM:** Nein. Deterministisch.
- **Code:** Slide-Level + Deck-Level Regeln. S001-S018, D001-D013. Prueft auch TopicClassification-Constraints (required_slide_types vorhanden?).
- **Fehler:** Bei FAIL → Stage 6.

### Stage 6: Plan Regenerator
- **Zweck:** Gezielte Reparatur fehlerhafter Slides im Plan.
- **Input:** `PresentationPlan`, `ValidationResult`, Kontext-Slides
- **Output:** Reparierter `PresentationPlan`
- **LLM:** Nur fuer Slides mit Fehlern, die nicht auto-fixbar sind. Pro Slide ein LLM-Call.
- **Code:** Auto-Fixes zuerst (Truncation, Decorative→Supporting). LLM nur fuer semantische Probleme (underfilled, weak title, wrong type).
- **Fehler:** Max 2 Runden. Dann weiter mit Warnings.

### Stage 7: Content Filler
- **Zweck:** Finalisiert alle Texte pro Slide.
- **Input:** `PresentationPlan` (validiert)
- **Output:** `list[FilledSlide]`
- **LLM:** Pro Slide ein LLM-Call. Ersetzt Platzhalter durch finale Texte.
- **Code:** Parallel mit `asyncio.gather`. Berechnet TextMetrics.
- **Fehler:** Fallback auf Plan-Texte.

### Stage 8: Fill Validator (NEU)
- **Zweck:** Harte Pruefung der gefuellten Texte.
- **Input:** `list[FilledSlide]`, `TopicClassification`
- **Output:** `ValidationResult`
- **LLM:** Nein. Deterministisch.
- **Code:** Prueft:
  - Headline ist Aussage (Verb-Heuristik + Laenge + kein reiner Themen-Titel)
  - Content Blocks vollstaendig befuellt (min chars pro Block-Typ)
  - Keine Platzhalter-Texte
  - Bild-Beschreibung spezifisch genug
  - TextMetrics innerhalb der Limits
- **Fehler:** Bei FAIL → Stage 9.

### Stage 9: Fill Regenerator (NEU)
- **Zweck:** Gezielte Text-Reparatur nach Filling.
- **Input:** `list[FilledSlide]`, `ValidationResult`
- **Output:** Reparierte `list[FilledSlide]`
- **LLM:** Nur fuer Slides mit Fill-Fehlern. Pro Slide ein LLM-Call mit spezifischem Regenerator-Prompt.
- **Code:** Auto-Fixes zuerst (Truncation). LLM fuer: schwache Titel, unterfuellte Blocks, generische Bilder.
- **Fehler:** Max 1 Runde. Dann weiter.

### Stage 10: Layout Engine
- **Zweck:** FilledSlides → RenderInstructions.
- **Input:** `list[FilledSlide]`, Audience, ImageStyle
- **Output:** `list[RenderInstruction]`
- **LLM:** Nein. Deterministisch.
- **Code:** Blueprint-Lookup + Audience-Modifier + dynamische Umverteilung.

### Stage 11: PPTX Renderer
- **Zweck:** RenderInstructions → .pptx Datei.
- **Input:** `list[RenderInstruction]`
- **Output:** `Path` zur .pptx
- **LLM:** Nein.
- **Code:** python-pptx. Shapes, Textboxen, Bilder, Charts.

### Stage 12: Post-Generation Review
- **Zweck:** Optionaler finaler Quality-Check.
- **Input:** `list[FilledSlide]`, `PresentationPlan`, `QualityReport`
- **Output:** `QualityReport` (angereichert)
- **LLM:** Optional. Kann visuelles QA machen (LibreOffice → PDF → JPEG Inspektion).
- **Code:** Score-Berechnung. Warning-Aggregation.

---

## 3. DATENMODELL

### TopicClassification (NEU)

```python
class TopicType(str, Enum):
    HISTORICAL = "historical"
    STRATEGY = "strategy"
    COMPARISON = "comparison"
    ANALYTICS = "analytics"
    WORKSHOP = "workshop"
    EXECUTIVE_UPDATE = "executive_update"
    PROCESS = "process"
    GENERAL = "general"

class TopicClassification(BaseModel):
    topic_type: TopicType
    narrative_arc: NarrativeArc
    required_slide_types: list[SlideType] = Field(default_factory=list)
    recommended_slide_types: list[SlideType] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)
    min_content_slides: int = Field(5)
    deck_template: str = Field("general")
```

### SlidePlan (erweitert)

```python
class SlidePlan(BaseModel):
    position: int = Field(..., ge=1)
    slide_type: SlideType
    beat_ref: int = Field(0)
    topic_role: str = Field("")  # "opening", "epoch_1", "transition", "synthesis", etc.
    headline: str = Field(..., max_length=70)
    subheadline: str = Field("", max_length=120)
    core_message: str = Field("", max_length=150)
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    visual: Visual = Field(default_factory=Visual)
    speaker_notes: str = Field("", max_length=600)
    transition_hint: str = Field("")
    # NEU:
    required_elements: list[str] = Field(default_factory=list)  # computed from slide_type
    validation_flags: list[str] = Field(default_factory=list)   # set by validators
    regeneration_strategy: str = Field("none")                   # "none", "title_only", "content_only", "full", "type_change"
```

### TitleSpec (NEU)

```python
class TitleSpec(BaseModel):
    raw_title: str
    is_statement: bool = Field(False)
    has_verb: bool = Field(False)
    word_count: int = Field(0)
    char_count: int = Field(0)
    is_topic_label: bool = Field(False)
    quality_score: float = Field(0.0)  # 0-1
    issues: list[str] = Field(default_factory=list)
```

### VisualSpec (NEU — ersetzt `Visual`)

```python
class VisualSpec(BaseModel):
    type: VisualType = Field(VisualType.NONE)
    image_role: ImageRole = Field(ImageRole.NONE)
    image_description: str = Field("", max_length=250)
    image_function: str = Field("")     # "zeitgeist", "anchor", "contrast", "evidence", "hero"
    chart_spec: ChartSpec | None = Field(None)
    is_functional: bool = Field(True)   # computed by validator
```

### ValidationResult (NEU — ersetzt QualityReport fuer Zwischen-Checks)

```python
class ValidationVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    REGENERATE = "regenerate"

class SlideValidation(BaseModel):
    slide_index: int
    verdict: ValidationVerdict
    findings: list[QualityFinding] = Field(default_factory=list)
    regeneration_action: str = Field("none")  # "title_only", "content_only", "full", "type_change"

class ValidationResult(BaseModel):
    verdict: ValidationVerdict
    overall_score: float = Field(100.0)
    slide_validations: list[SlideValidation] = Field(default_factory=list)
    deck_findings: list[QualityFinding] = Field(default_factory=list)
    requires_regeneration: bool = Field(False)
    regeneration_scope: str = Field("none")  # "slides_only", "deck_structure", "full_replan"
```

### RegenerationAction (NEU)

```python
class RegenerationAction(BaseModel):
    slide_index: int
    action_type: str  # "title_only", "content_fill", "type_change", "full_regen", "remove"
    reason: str
    target_slide_type: SlideType | None = None  # only for type_change
    specific_errors: list[str] = Field(default_factory=list)
    priority: int = Field(1)  # 1=high, 2=medium, 3=low
```

### PresentationPlan (erweitert)

```python
class PresentationPlan(BaseModel):
    audience: Audience = Field(Audience.MANAGEMENT)
    image_style: ImageStyleType = Field(ImageStyleType.MINIMAL)
    topic_classification: TopicClassification | None = Field(None)  # NEU
    slides: list[SlidePlan] = Field(default_factory=list)
    metadata: PresentationMetadata = Field(default_factory=PresentationMetadata)
```

---

## 4. ERLAUBTE SLIDE-TYPEN

14 Typen bleiben. Jeder bekommt harte Constraints.

### title_hero
- **Zweck:** Eroeffnungsfolie. Setzt Thema und Ton.
- **Wann:** Immer Position 1. Nie woanders.
- **Erlaubte Inhalte:** headline (Thesen-Titel), subheadline (Kontext), optional Hero-Bild.
- **Verbotene Inhalte:** Bullets, Cards, KPIs.
- **Pflichtfelder:** headline.
- **Optional:** subheadline, visual (hero image).
- **Mindestanforderungen:** headline >= 15 chars.
- **Typische Fehlform:** Titel besteht nur aus einem Wort. Kein Subheadline.
- **Zielgruppen:** Alle.
- **Bildstile:** photo (Hero-Bild), illustration (Hintergrundbild), minimal (kein Bild).
- **Validator:** Headline muss Aussage sein. Max 1 pro Deck.

### section_divider
- **Zweck:** Visueller Schnitt zwischen Sektionen.
- **Wann:** Vor neuem Themenblock. Nie am Ende.
- **Erlaubte Inhalte:** headline, core_message.
- **Verbotene Inhalte:** Bullets, Cards, Bilder.
- **Pflichtfelder:** headline.
- **Mindestanforderungen:** headline >= 10 chars.
- **Typische Fehlform:** Drei section_dividers hintereinander. Divider ohne folgenden Inhalt.
- **Zielgruppen:** Alle.
- **Validator:** Max 2 pro Deck. Nie an Position N oder N-1.

### key_statement
- **Zweck:** Eine starke Aussage oder Zitat.
- **Wann:** Nach Evidenz-Folien als Verdichtung. Oder als Ueberleitung.
- **Erlaubte Inhalte:** quote oder text Block.
- **Verbotene Inhalte:** Bullets, Cards, KPIs, Bilder.
- **Pflichtfelder:** headline + 1 quote oder text Block.
- **Mindestanforderungen:** quote.text >= 30 chars.
- **Typische Fehlform:** Generischer Satz ohne Substanz. Wiederholung der Headline.
- **Zielgruppen:** management (stark), customer (stark), team (selten).
- **Validator:** Max 2 pro Deck. Quote darf nicht identisch mit Headline sein.

### bullets_focused
- **Zweck:** Kernpunkte verdichtet auf 2-3 Bullets.
- **Wann:** Fuer Zusammenfassungen, Massnahmen, Key Takeaways.
- **Erlaubte Inhalte:** 1 bullets Block (2-3 Items).
- **Verbotene Inhalte:** Mehr als 3 Bullets. Bilder.
- **Pflichtfelder:** headline + 1 bullets Block mit >= 2 Items.
- **Mindestanforderungen:** Jeder Bullet >= 30 chars. Bei management: bold_prefix pflicht.
- **Typische Fehlform:** Bullet = "Punkt 1", "Punkt 2". Weniger als 2 Bullets.
- **Zielgruppen:** Alle.
- **Validator:** Keine 2 consecutiven bullets_focused. Bullets > 30 chars.

### three_cards
- **Zweck:** Drei gleichwertige Aspekte, Optionen oder Saeulen.
- **Wann:** Fuer Vorteile, Saeulen, Team-Rollen, Features.
- **Erlaubte Inhalte:** Exakt 3 card Blocks.
- **Verbotene Inhalte:** Weniger/mehr als 3 Cards. Bilder.
- **Pflichtfelder:** headline + 3 card Blocks.
- **Mindestanforderungen:** card.title >= 10 chars, card.body >= 40 chars.
- **Typische Fehlform:** Cards mit identischem Body-Text. Body < 20 chars.
- **Validator:** Exakt 3 Cards. Jeder Body >= 40 chars. Keine identischen Bodies.

### kpi_dashboard
- **Zweck:** 3-4 Kennzahlen visualisiert.
- **Wann:** Fuer Ergebnisse, Performance, Statusupdates.
- **Erlaubte Inhalte:** 3-4 kpi Blocks.
- **Verbotene Inhalte:** Weniger als 3 KPIs. Bilder. Bullets.
- **Pflichtfelder:** headline + 3-4 kpi Blocks.
- **Mindestanforderungen:** kpi.value nicht leer. kpi.label nicht leer.
- **Typische Fehlform:** Alle Trends "neutral". Values sind Platzhalter ("XX%").
- **Zielgruppen:** management (stark), team, customer (selten).
- **Bildstile:** data_visual (bevorzugt), minimal.
- **Validator:** 3-4 KPIs. Value nicht leer. Kein Platzhalter.

### image_text_split
- **Zweck:** Bild + Text nebeneinander. Fuer visuelle Evidenz oder Kontext.
- **Wann:** Fuer Epochen-Illustration, Produktbilder, Standort-Kontext.
- **Erlaubte Inhalte:** headline, subheadline, 1 bullets/text Block, 1 Bild.
- **Verbotene Inhalte:** Bild ohne funktionale Rolle.
- **Pflichtfelder:** headline + visual.image_description (>= 20 chars) + 1 content Block.
- **Mindestanforderungen:** Bild-Rolle != decorative. Content Block >= 2 Bullets oder Text >= 50 chars.
- **Typische Fehlform:** "Ein modernes Buerogebaeude" als Bild zu einem Thema, das nichts mit Bueros zu tun hat.
- **Zielgruppen:** customer (stark), team.
- **Bildstile:** photo (bevorzugt), illustration.
- **Validator:** image_role IN (supporting, evidence, hero). image_description >= 20 chars.

### comparison
- **Zweck:** Zwei Optionen, Zustaende oder Epochen gegenueberstellen.
- **Wann:** Vorher/Nachher, Alt/Neu, Option A/B.
- **Erlaubte Inhalte:** Exakt 2 comparison_column Blocks.
- **Verbotene Inhalte:** Weniger/mehr als 2 Spalten. Bilder.
- **Pflichtfelder:** headline + 2 comparison_column Blocks.
- **Mindestanforderungen:** Jede Spalte >= 3 Items. column_label nicht leer.
- **Typische Fehlform:** Spalten mit identischen Items. Spalten mit nur 1 Item.
- **Validator:** Exakt 2 Spalten. >= 3 Items je Spalte.

### timeline
- **Zweck:** Chronologische Abfolge von Ereignissen/Meilensteinen.
- **Wann:** Fuer historische Entwicklung, Projektplaene, Roadmaps.
- **Erlaubte Inhalte:** 3-6 timeline_entry Blocks.
- **Verbotene Inhalte:** Weniger als 3 Eintraege. Bilder.
- **Pflichtfelder:** headline + >= 3 timeline_entry Blocks.
- **Mindestanforderungen:** Jeder Eintrag: date, title, description >= 20 chars.
- **Typische Fehlform:** Eintraege ohne Description. Nicht-chronologische Sortierung.
- **Zielgruppen:** Alle.
- **Validator:** >= 3 Eintraege. Dates muessen chronologisch sortierbar sein. Description >= 20 chars.

### process_flow
- **Zweck:** 3-5 sequentielle Schritte.
- **Wann:** Fuer Prozesse, Vorgehensmodelle, Anleitungen.
- **Erlaubte Inhalte:** 3-5 process_step Blocks.
- **Verbotene Inhalte:** Weniger als 3 Schritte. Bilder.
- **Pflichtfelder:** headline + 3-5 process_step Blocks.
- **Mindestanforderungen:** step.title >= 5 chars, step.description >= 20 chars.
- **Typische Fehlform:** "Schritt 1", "Schritt 2" ohne echten Titel.
- **Validator:** 3-5 Steps. Title nicht nur "Schritt X".

### chart_insight
- **Zweck:** Daten-Chart mit kurzer Kommentierung.
- **Wann:** Fuer Zahlen, Trends, Verteilungen.
- **Erlaubte Inhalte:** 1 chart_spec, 1-2 bullets Block (Takeaways).
- **Verbotene Inhalte:** Kein chart_spec vorhanden.
- **Pflichtfelder:** headline + visual.chart_spec.
- **Mindestanforderungen:** chart_spec.data darf nicht leer sein.
- **Typische Fehlform:** Chart ohne Daten. Chart ohne Headline-Insight.
- **Bildstile:** data_visual (bevorzugt).
- **Validator:** chart_spec.data.labels nicht leer. chart_spec.data.series nicht leer.

### image_fullbleed
- **Zweck:** Ganzseitiges Bild mit minimalem Text-Overlay.
- **Wann:** Fuer emotionale Wirkung, Hero-Shots, Stimmungsbilder.
- **Erlaubte Inhalte:** headline (kurz), 1 text Block (max 60 chars).
- **Verbotene Inhalte:** Bullets, Cards, KPIs.
- **Pflichtfelder:** headline + visual.image_description.
- **Mindestanforderungen:** headline <= 40 chars. image_description >= 30 chars.
- **Typische Fehlform:** Generisches Stockfoto. Zu langer Text ueber dem Bild.
- **Zielgruppen:** customer (stark).
- **Bildstile:** photo (einzig sinnvoll).
- **Validator:** Nur bei image_style photo. Max 2 pro Deck. image_role = hero oder decorative.

### agenda
- **Zweck:** Inhaltsverzeichnis / Ablauf.
- **Wann:** Position 2 oder 3 im Deck. Optional.
- **Erlaubte Inhalte:** 1 bullets Block (3-6 Agenda-Punkte).
- **Verbotene Inhalte:** Bilder, KPIs.
- **Pflichtfelder:** headline + 1 bullets Block.
- **Mindestanforderungen:** >= 3 Agenda-Punkte.
- **Typische Fehlform:** Headline "Agenda" ohne Kontext. Punkte = Slide-Titel.
- **Validator:** Max 1 pro Deck. Position <= 3.

### closing
- **Zweck:** Abschluss mit Synthese / Call-to-Action / Summary.
- **Wann:** Immer letzte Position.
- **Erlaubte Inhalte:** 1 bullets Block (2-3 Summary-Punkte), 1 quote Block.
- **Verbotene Inhalte:** KPIs, Cards, Bilder. Langer Fliesstext.
- **Pflichtfelder:** headline + 1 content Block.
- **Mindestanforderungen:** Content Block vorhanden. Keine Wiederholung der Eroeffnung.
- **Typische Fehlform:** "Vielen Dank fuer Ihre Aufmerksamkeit" ohne Inhalt. Prose-Wall.
- **Validator:** Muss letzter Slide sein. headline != title_hero headline. Content Block vorhanden.

---

## 5. TITLE LOGIC FIX

### Regeln fuer gute Aussage-Titel

1. Ein guter Titel enthaelt ein **Verb** (konjugiert oder Partizip).
2. Ein guter Titel hat **mindestens 5 Woerter**.
3. Ein guter Titel transportiert ein **Ergebnis, eine Erkenntnis oder eine Behauptung**.
4. Ein guter Titel ist **nicht als Wikipedia-Artikel-Ueberschrift verwendbar**.
5. Ein guter Titel beantwortet die Frage: **"Was ist die zentrale Aussage dieser Folie?"**

### Negativmuster

```python
TOPIC_LABEL_PATTERNS = [
    # "Thema X" ohne Verb
    r"^[A-Z][a-zaeoeueAeOeUe\s&]+$",  # Nur Nomen/Adjektive, kein Verb
    # "X und Y" / "X & Y" ohne Praedikat
    r"^.{5,30}\s+(und|&|oder)\s+.{5,30}$",
    # "X im Y" / "X in der Y"
    r"^.{3,20}\s+(im|in der|in den|des|der)\s+.{3,20}$",
    # Einworttitel
    r"^\w+$",
    # Nur 2-3 Woerter ohne Verb
    # detected by word_count + verb check
]

WEAK_TITLE_KEYWORDS = {
    "ueberblick", "einleitung", "zusammenfassung", "hintergrund",
    "kontext", "ausgangslage", "aktuelle entwicklungen", "fazit",
    "ergebnis", "details", "analyse", "naechste schritte",
}
```

### Prueflogik (Pseudocode)

```python
def analyze_title(headline: str, slide_type: SlideType) -> TitleSpec:
    words = headline.strip().split()
    spec = TitleSpec(
        raw_title=headline,
        word_count=len(words),
        char_count=len(headline),
    )

    # Skip types where topic labels are acceptable
    if slide_type in (SlideType.TITLE_HERO, SlideType.AGENDA):
        spec.is_statement = True
        spec.quality_score = 0.8
        return spec

    # Check 1: Has verb?
    GERMAN_VERB_ENDINGS = ("t", "en", "te", "te", "et", "st", "ert", "iert", "igt")
    GERMAN_VERBS = {"ist", "sind", "hat", "haben", "wird", "werden", "kann",
                     "macht", "zeigt", "gewinnt", "schafft", "ermoeglicht",
                     "fuehrt", "steigert", "sichert", "definiert", "praegt",
                     "veraendert", "waechst", "sinkt", "steigt"}
    has_verb = any(
        w.lower() in GERMAN_VERBS or w.lower().endswith(GERMAN_VERB_ENDINGS)
        for w in words
    )
    spec.has_verb = has_verb

    # Check 2: Topic label pattern?
    is_label = (
        len(words) <= 3
        or headline.lower().strip() in WEAK_TITLE_KEYWORDS
        or any(re.match(pat, headline) for pat in TOPIC_LABEL_PATTERNS)
    )
    spec.is_topic_label = is_label

    # Check 3: Statement quality
    spec.is_statement = has_verb and not is_label and len(words) >= 4
    spec.quality_score = (
        0.4 * int(has_verb) +
        0.3 * int(not is_label) +
        0.2 * min(len(words) / 8, 1.0) +
        0.1 * int(headline.endswith("."))
    )

    if not spec.is_statement:
        spec.issues.append("TITLE_NOT_STATEMENT")
    if spec.is_topic_label:
        spec.issues.append("TITLE_IS_TOPIC_LABEL")
    if not has_verb:
        spec.issues.append("TITLE_NO_VERB")

    return spec
```

### FAIL-Kriterien

- `quality_score < 0.4` → FAIL, regenerate title
- `is_topic_label == True` bei non-hero/non-divider → FAIL
- `has_verb == False` bei non-hero/non-divider/non-agenda → WARNING

### Regenerationslogik

Wenn Titel FAIL: Sende an LLM mit Regenerator-Prompt:
- Input: aktueller Titel + core_message + slide_type
- Prompt: "Formuliere diesen Titel als Aussage mit Verb um. Er muss eine Erkenntnis transportieren."
- Output: neuer Titel (max 70 chars)

---

## 6. THEMA-TRANSFORMATIONSLOGIK

### Historie / Geschichte

```python
HISTORICAL_DECK = {
    "narrative_arc": "chronological",
    "required_types": [SlideType.TIMELINE],
    "recommended_types": [SlideType.COMPARISON, SlideType.IMAGE_TEXT_SPLIT],
    "deck_template": [
        ("title_hero", "Eroeffnung mit These"),
        ("timeline", "Ueberblick der Gesamtentwicklung"),
        ("image_text_split|comparison|three_cards", "Epoche/Phase 1"),
        ("image_text_split|comparison|bullets_focused", "Epoche/Phase 2"),
        ("image_text_split|comparison|bullets_focused", "Epoche/Phase 3"),
        ("comparison|key_statement", "Vorletzte: heutige Relevanz / Wandel"),
        ("closing", "Synthese: was bleibt, was sich aenderte"),
    ],
    "forbidden": [
        "Keine 3+ aufeinanderfolgenden bullets_focused",
        "Keine reine Faktenauflistung ohne visuelle Differenzierung",
    ],
    "min_slides": 7,
}
```

### Strategie

```python
STRATEGY_DECK = {
    "narrative_arc": "situation_complication_resolution",
    "required_types": [SlideType.KPI_DASHBOARD],
    "recommended_types": [SlideType.PROCESS_FLOW, SlideType.THREE_CARDS],
    "deck_template": [
        ("title_hero", "These / Strategische Aussage"),
        ("kpi_dashboard|bullets_focused", "Ausgangslage / Status Quo"),
        ("key_statement|comparison", "Herausforderung / Warum jetzt"),
        ("three_cards|process_flow", "Strategische Saeulen / Massnahmen"),
        ("bullets_focused|timeline", "Umsetzung / Roadmap"),
        ("kpi_dashboard", "Erwartete Ergebnisse / Ziele"),
        ("closing", "Call to Action"),
    ],
    "forbidden": [
        "Kein Deck ohne mindestens 1 KPI/Chart",
    ],
    "min_slides": 7,
}
```

### Vergleich / Entscheidung

```python
COMPARISON_DECK = {
    "narrative_arc": "compare_decide",
    "required_types": [SlideType.COMPARISON],
    "recommended_types": [SlideType.KPI_DASHBOARD, SlideType.THREE_CARDS],
    "deck_template": [
        ("title_hero", "Entscheidungsfrage"),
        ("bullets_focused", "Kontext / Ausgangslage"),
        ("comparison", "Option A vs. Option B"),
        ("kpi_dashboard|chart_insight", "Zahlenvergleich"),
        ("key_statement", "Empfehlung"),
        ("closing", "Naechste Schritte"),
    ],
    "forbidden": [],
    "min_slides": 6,
}
```

### KPI / Analyse

```python
ANALYTICS_DECK = {
    "narrative_arc": "situation_complication_resolution",
    "required_types": [SlideType.KPI_DASHBOARD, SlideType.CHART_INSIGHT],
    "recommended_types": [],
    "deck_template": [
        ("title_hero", "Zentrale Erkenntnis"),
        ("kpi_dashboard", "Key Metrics"),
        ("chart_insight", "Trend / Entwicklung"),
        ("chart_insight|bullets_focused", "Details"),
        ("key_statement|comparison", "Interpretation"),
        ("closing", "Handlungsempfehlung"),
    ],
    "forbidden": [
        "Keine image_fullbleed",
        "Keine Slides ohne Zahlen oder Daten",
    ],
    "min_slides": 6,
}
```

### Workshop / Diskussion

```python
WORKSHOP_DECK = {
    "narrative_arc": "thematic_cluster",
    "required_types": [],
    "recommended_types": [SlideType.COMPARISON, SlideType.THREE_CARDS],
    "deck_template": [
        ("title_hero", "Thema / Leitfrage"),
        ("bullets_focused|agenda", "Ablauf / Fragen"),
        ("comparison|three_cards", "Input / Impulse"),
        ("key_statement", "Diskussionsfrage"),
        ("closing", "Zusammenfassung / naechste Schritte"),
    ],
    "forbidden": [
        "Keine datenintensiven Slides",
    ],
    "min_slides": 5,
}
```

### Executive Update

```python
EXECUTIVE_UPDATE_DECK = {
    "narrative_arc": "situation_complication_resolution",
    "required_types": [SlideType.KPI_DASHBOARD],
    "recommended_types": [SlideType.CHART_INSIGHT, SlideType.PROCESS_FLOW],
    "deck_template": [
        ("title_hero", "Headline-Erkenntnis"),
        ("kpi_dashboard", "Status / KPIs"),
        ("chart_insight|bullets_focused", "Highlights"),
        ("bullets_focused|three_cards", "Risiken / Massnahmen"),
        ("timeline|process_flow", "Naechste Schritte"),
        ("closing", "Fazit / Entscheidungsbedarf"),
    ],
    "forbidden": [],
    "min_slides": 6,
}
```

### General (Fallback)

```python
GENERAL_DECK = {
    "narrative_arc": "thematic_cluster",
    "required_types": [],
    "recommended_types": [SlideType.THREE_CARDS, SlideType.BULLETS_FOCUSED],
    "deck_template": [
        ("title_hero", "Thema"),
        ("bullets_focused|three_cards", "Kernpunkte"),
        ("image_text_split|comparison", "Vertiefung"),
        ("closing", "Zusammenfassung"),
    ],
    "forbidden": [],
    "min_slides": 5,
}
```

### Mapping-Tabelle

| topic_type       | narrative_arc                         | required_types              | min_slides |
|------------------|---------------------------------------|-----------------------------|------------|
| historical       | chronological                         | timeline                    | 7          |
| strategy         | situation_complication_resolution     | kpi_dashboard               | 7          |
| comparison       | compare_decide                        | comparison                  | 6          |
| analytics        | situation_complication_resolution     | kpi_dashboard, chart_insight| 6          |
| workshop         | thematic_cluster                      | —                           | 5          |
| executive_update | situation_complication_resolution     | kpi_dashboard               | 6          |
| process          | chronological                         | process_flow                | 6          |
| general          | thematic_cluster                      | —                           | 5          |

---

## 7. FUNCTIONAL IMAGE LOGIC

### Erlaubte Bildfunktionen

```python
class ImageFunction(str, Enum):
    ZEITGEIST = "zeitgeist"      # Stimmung/Atmosphaere einer Epoche transportieren
    ANCHOR = "anchor"            # Historische Phase oder Ort visuell verankern
    CONTRAST = "contrast"        # Wandel/Gegensatz zwischen Zustaenden zeigen
    EVIDENCE = "evidence"        # Kernaussage faktuell/visuell belegen
    HERO = "hero"                # Layout als Hauptelement tragen
    PRODUCT = "product"          # Produkt/Loesung zeigen
```

### Ungeeignete Bildverwendungen

- Generische Stockfotos ohne Bezug zum Inhalt
- "Ein modernes Buero" zu einem Thema, das nichts mit Bueros zu tun hat
- Rein dekorative Bilder, die austauschbar sind
- Bilder, die den Inhalt wiederholen statt ergaenzen

### Bildlogik je Slide-Typ

| Slide-Typ        | Bild erlaubt? | Erlaubte Rollen           | Erlaubte Funktionen           |
|------------------|---------------|---------------------------|-------------------------------|
| title_hero       | ja            | hero                      | hero, zeitgeist               |
| image_text_split | ja (pflicht)  | supporting, evidence      | zeitgeist, anchor, evidence   |
| image_fullbleed  | ja (pflicht)  | hero, decorative          | hero, zeitgeist               |
| chart_insight    | nein          | —                         | —                             |
| kpi_dashboard    | nein          | —                         | —                             |
| three_cards      | nein          | —                         | —                             |
| comparison       | nein          | —                         | —                             |
| timeline         | nein          | —                         | —                             |
| process_flow     | nein          | —                         | —                             |
| bullets_focused  | nein          | —                         | —                             |
| key_statement    | nein          | —                         | —                             |
| section_divider  | nein          | —                         | —                             |
| agenda           | nein          | —                         | —                             |
| closing          | nein          | —                         | —                             |

### Bildlogik je Zielgruppe

| Zielgruppe  | Bild-Intensitaet | Bevorzugte Funktionen     |
|-------------|-------------------|---------------------------|
| management  | niedrig           | evidence, hero            |
| team        | mittel            | anchor, evidence          |
| customer    | hoch              | hero, zeitgeist, product  |
| workshop    | niedrig           | —                         |

### Bildlogik je Bildstil

| Bildstil      | Erlaubte Funktionen          | Max Bild-Slides |
|---------------|------------------------------|-----------------|
| photo         | alle                         | 3               |
| illustration  | zeitgeist, anchor, hero      | 2               |
| minimal       | keine Bilder                 | 0               |
| data_visual   | keine Bilder (nur Charts)    | 0               |
| none          | keine Bilder                 | 0               |

### Validator-Regel

```python
def validate_image_function(slide, image_style):
    if slide.visual.image_role == ImageRole.NONE:
        return PASS
    if image_style in ("minimal", "data_visual", "none"):
        return FAIL("Bilder bei Bildstil '{image_style}' nicht erlaubt")
    if slide.visual.image_role == ImageRole.DECORATIVE and slide.slide_type != SlideType.IMAGE_FULLBLEED:
        return FAIL("Dekoratives Bild nur bei image_fullbleed erlaubt")
    if len(slide.visual.image_description) < 20:
        return FAIL("Bildbeschreibung zu kurz/generisch")
    return PASS
```

---

## 8. DECK-DRAMATURGIE

### Anfang (Slides 1-2)
- Slide 1: MUSS `title_hero` sein. Headline ist die zentrale These.
- Slide 2: Optional `agenda` (Position <= 3). Oder erster inhaltlicher Slide.

### Mittelteil (Slides 3 bis N-2)
- Mindestens 3 verschiedene Slide-Typen im Mittelteil.
- Max 60% des Mittelteils darf ein einziger Typ sein.
- Keine 3 aufeinanderfolgenden Slides des gleichen Typs.
- Max 2 aufeinanderfolgende "Low-Content" Slides (title_hero, section_divider, key_statement).

### Schluss (Slides N-1 und N)
- Slide N-1: Soll aktuelle Relevanz, Transformation oder Handlungsbedarf zeigen.
- Slide N: MUSS `closing` sein. Strukturierte Summary (Bullets/Quote), keine Prose-Wall.

### Obergrenzen fuer reduzierte Folien
- Max 3 Low-Content Slides (title_hero + section_divider + key_statement) pro Deck.
- Fuer Decks > 12 Slides: max `slides // 3` Low-Content.

### Rhythmus und Informationsdichte

```python
DENSITY_TARGETS = {
    SlideType.TITLE_HERO: "low",
    SlideType.SECTION_DIVIDER: "low",
    SlideType.KEY_STATEMENT: "low",
    SlideType.BULLETS_FOCUSED: "medium",
    SlideType.THREE_CARDS: "high",
    SlideType.KPI_DASHBOARD: "high",
    SlideType.IMAGE_TEXT_SPLIT: "medium",
    SlideType.COMPARISON: "high",
    SlideType.TIMELINE: "high",
    SlideType.PROCESS_FLOW: "high",
    SlideType.CHART_INSIGHT: "high",
    SlideType.IMAGE_FULLBLEED: "low",
    SlideType.AGENDA: "medium",
    SlideType.CLOSING: "medium",
}
```

Regel: Nach 2 "high"-Density Slides sollte ein "medium" oder "low" Slide folgen.

### Deck-Templates fuer historische Kurzdecks (8-12 Slides)

```
[title_hero] → [timeline] → [image_text_split|comparison] → [three_cards|bullets_focused]
→ [image_text_split|comparison] → [bullets_focused|three_cards] → [comparison|key_statement]
→ [closing]
```

---

## 9. VALIDATOR-ARCHITEKTUR

### Ausfuehrungsreihenfolge

```
Plan-Phase:
  1. Slide-Level Validators (S001-S018) → pro Slide
  2. Deck-Level Validators (D001-D013) → ganzes Deck
  3. Topic-Constraint Validators (T001-T005) → TopicClassification

Fill-Phase (NEU):
  4. Fill-Level Validators (F001-F008) → pro gefuelltem Slide
  5. Title Quality Validators (H001-H003) → pro Headline
```

### Slide-Level Regeln (S001-S018, bestehend + erweitert)

| Regel | Pruefung | Severity | Auto-Fix | Threshold |
|-------|----------|----------|----------|-----------|
| S001 | Headline vorhanden | error | nein | — |
| S002 | Headline <= 70 chars | error | ja (truncate) | 70 |
| S003 | core_message vorhanden | warning/error | nein | — |
| S004 | slide_type valide | error | nein | — |
| S005 | Bullets <= max_count | error | ja (trim) | per type |
| S006 | Bullet text <= 80 chars | error | ja (truncate) | 80 |
| S007 | Headline nicht generisch | warning | nein | — |
| S008 | Content blocks match type | error | nein | — |
| S009 | Image role valide | warning | ja (→ supporting) | — |
| S010 | Total text density | error | ja (truncate) | per type |
| S011 | KPI hat Value | error | nein | — |
| S012 | Timeline >= 3 Eintraege | error | nein | 3 |
| S013 | Speaker notes vorhanden | warning | nein | — |
| S014 | Headline ist Aussage | warning | nein | word_count > 3 |
| S015 | Slide type fully populated | error | nein | per type |
| S016 | Image hat Funktion | error/warning | ja (→ supporting) | desc >= 20 |
| S017 | Timeline entries complete | warning | nein | desc >= 20 |
| S018 | Cards haben Body | warning | nein | body >= 30 |

### Deck-Level Regeln (D001-D013, bestehend)

| Regel | Pruefung | Severity | Threshold |
|-------|----------|----------|-----------|
| D001 | Starts with title_hero | error | — |
| D002 | Ends with closing | error | — |
| D003 | >= 3 verschiedene Typen | error | 3 |
| D004 | Keine consecutiven bullets | error | — |
| D005 | Keine 3 gleichen hintereinander | warning | — |
| D006 | 5-25 Slides | error | 5-25 |
| D007 | Max 2 key_statements | warning | 2 |
| D008 | section_divider nicht am Ende | error | — |
| D009 | Historisch → hat Timeline | error | — |
| D010 | Max low-content Slides | warning | max(3, n//3) |
| D011 | Keine 3+ consecutiven low-content | error | 2 |
| D012 | Closing nicht prose | warning | — |
| D013 | Dramaturgische Varianz | warning | 60% |

### Topic-Constraint Regeln (NEU: T001-T005)

| Regel | Pruefung | Severity |
|-------|----------|----------|
| T001 | Required slide types aus TopicClassification vorhanden | error |
| T002 | Narrative arc stimmt mit TopicClassification | warning |
| T003 | Min content slides erreicht | error |
| T004 | Forbidden patterns nicht verletzt | error |
| T005 | Deck template grob eingehalten | warning |

### Fill-Level Regeln (NEU: F001-F008)

| Regel | Pruefung | Severity | Auto-Fix |
|-------|----------|----------|----------|
| F001 | Headline quality_score >= 0.4 | error | nein → LLM regen |
| F002 | Kein Platzhalter-Text | error | nein → LLM regen |
| F003 | Bullets >= 30 chars | warning | nein |
| F004 | Card body >= 40 chars | warning | nein |
| F005 | Timeline desc >= 20 chars | warning | nein |
| F006 | Image description >= 20 chars | warning | ja (extend) |
| F007 | TextMetrics.total_chars > 0 | error | nein |
| F008 | Management-Bullets haben bold_prefix | warning | nein |

### Title Quality Regeln (NEU: H001-H003)

| Regel | Pruefung | Severity |
|-------|----------|----------|
| H001 | Headline hat Verb | warning |
| H002 | Headline ist kein Topic-Label | error |
| H003 | Headline != Wikipedia-Heading | warning |

### Scoring

```python
score = 100.0
for finding in all_findings:
    if finding.severity == "error":
        score -= 15
    else:
        score -= 5
verdict = "pass" if score >= 70 else "fail"
requires_regeneration = score < 70 or any(f.severity == "error" for f in findings)
```

### Pseudocode

```python
def validate_plan(plan, topic_classification):
    result = ValidationResult()

    # Slide-level
    for idx, slide in enumerate(plan.slides):
        slide_val = SlideValidation(slide_index=idx)
        for check in SLIDE_CHECKS:  # S001-S018
            findings = check(slide, idx)
            slide_val.findings.extend(findings)

        # Determine per-slide verdict
        errors = [f for f in slide_val.findings if f.severity == "error"]
        if errors:
            slide_val.verdict = FAIL
            slide_val.regeneration_action = classify_regen_action(errors)
        else:
            slide_val.verdict = PASS
        result.slide_validations.append(slide_val)

    # Deck-level
    for check in DECK_CHECKS:  # D001-D013
        result.deck_findings.extend(check(plan))

    # Topic-constraint
    for check in TOPIC_CHECKS:  # T001-T005
        result.deck_findings.extend(check(plan, topic_classification))

    # Score
    all_findings = result.deck_findings + [f for sv in result.slide_validations for f in sv.findings]
    result.overall_score = compute_score(all_findings)
    result.verdict = PASS if result.overall_score >= 70 else FAIL
    result.requires_regeneration = result.verdict == FAIL

    return result
```

---

## 10. REGENERATIONSLOGIK

### Fehlerklassen und Strategien

| Fehlerklasse | Beispiel | Regenerations-Strategie | Scope |
|---|---|---|---|
| weak_title | "Bier im Mittelalter" | title_only: Nur headline neu generieren | lokal |
| underfilled_slide | three_cards mit 1 Card | content_fill: Content blocks neu generieren | lokal |
| decorative_image | image_role = decorative | visual_fix: VisualSpec neu generieren | lokal |
| wrong_slide_type | kpi_dashboard mit 1 KPI | type_change: Slide-Typ aendern + fill | lokal |
| missing_required_type | Kein Timeline bei hist. Thema | deck_insert: Slide einfuegen / Plan anpassen | global |
| weak_closing | "Vielen Dank" ohne Inhalt | content_fill: Closing neu generieren | lokal |
| too_many_same_type | 4x bullets_focused | deck_restructure: Plan-Mittelteil variieren | global |
| no_verb_in_title | "Aktuelle Trends" | title_only | lokal |
| placeholder_text | "[Platzhalter]", "XYZ" | content_fill | lokal |
| density_violation | 3 high-density hintereinander | deck_restructure | global |

### Regenerationsmatrix

```python
REGEN_MATRIX = {
    # error_type → (strategy, scope, max_attempts, llm_required)
    "TITLE_NOT_STATEMENT":    ("title_only",     "local",  2, True),
    "TITLE_IS_TOPIC_LABEL":   ("title_only",     "local",  2, True),
    "TITLE_NO_VERB":          ("title_only",     "local",  2, True),
    "SLIDE_UNDERFILLED":      ("content_fill",   "local",  1, True),
    "IMAGE_DECORATIVE":       ("visual_fix",     "local",  1, False),  # auto-fix
    "WRONG_SLIDE_TYPE":       ("type_change",    "local",  1, True),
    "MISSING_REQUIRED_TYPE":  ("deck_insert",    "global", 1, True),
    "WEAK_CLOSING":           ("content_fill",   "local",  1, True),
    "TOO_MANY_SAME_TYPE":     ("deck_restructure", "global", 1, True),
    "PLACEHOLDER_TEXT":       ("content_fill",   "local",  1, True),
    "TEXT_OVERFLOW":          ("truncate",       "local",  1, False),  # auto-fix
    "BULLET_OVERFLOW":        ("trim",           "local",  1, False),  # auto-fix
}
```

### Lokale vs. Globale Reparaturen

**Lokal (Slide-Ebene):**
- Nur den betroffenen Slide an LLM senden.
- Kontext (vorheriger + naechster Slide) mitgeben.
- Position und beat_ref beibehalten.

**Global (Deck-Ebene):**
- Den gesamten Plan an LLM senden.
- TopicClassification-Constraints mitgeben.
- Neuen Plan validieren.
- Max 1 globale Regeneration pro Pipeline-Run.

### Pseudocode

```python
async def regeneration_loop(plan, validation_result, topic_class):
    for attempt in range(MAX_REGEN_ATTEMPTS):
        # Separate local from global issues
        local_issues = [sv for sv in validation_result.slide_validations
                        if sv.verdict == FAIL and REGEN_MATRIX[sv.errors[0]].scope == "local"]
        global_issues = [f for f in validation_result.deck_findings
                         if f.severity == "error"]

        # Auto-fixes first (no LLM)
        for sv in local_issues:
            strategy = REGEN_MATRIX[sv.errors[0]].strategy
            if strategy in ("truncate", "trim", "visual_fix"):
                plan.slides[sv.slide_index] = apply_auto_fix(plan.slides[sv.slide_index])

        # LLM local regen (parallel)
        llm_tasks = [sv for sv in local_issues
                     if REGEN_MATRIX[sv.errors[0]].llm_required]
        if llm_tasks:
            results = await asyncio.gather(*[
                regenerate_slide(plan, sv.slide_index, sv.errors)
                for sv in llm_tasks
            ])
            for sv, result in zip(llm_tasks, results):
                if result:
                    plan.slides[sv.slide_index] = result

        # Global regen (sequential, max 1x)
        if global_issues and attempt == 0:
            plan = await regenerate_deck_structure(plan, global_issues, topic_class)

        # Re-validate
        validation_result = validate_plan(plan, topic_class)
        if validation_result.verdict == PASS:
            break

    return plan, validation_result
```

---

## 11. PROMPT-ARCHITEKTUR

### 1. Topic Classifier Prompt
- **Nicht noetig** — deterministisch im Code (Keyword-Matching).

### 2. Interpreter Prompt (`interpreter_prompt.py`)
- **Rolle:** Briefing-Analyst
- **Ziel:** User-Input → InterpretedBriefing JSON
- **Input:** user_input, document_text
- **Output:** InterpretedBriefing JSON
- **Regeln:** Fakten extrahieren, Themes clustern, Audience/Tone inferieren. Historical detection (Rules 8-10).
- **Wann:** Stage 1.

### 3. Storyline Planner Prompt (`storyline_prompt.py`)
- **Rolle:** Storytelling-Experte
- **Ziel:** Narrative Arc mit Story Beats
- **Input:** InterpretedBriefing JSON, TopicClassification (injiziert narrative_arc)
- **Output:** Storyline JSON
- **Regeln:** Chronological fuer historische Themen. Beat core_messages muessen Aussagen sein. Opening/Closing pflicht.
- **Wann:** Stage 3.

### 4. Slide Planner Prompt (`slide_planner_prompt.py`)
- **Rolle:** Praesentations-Architekt
- **Ziel:** Beats → SlidePlans mit headline, content_blocks, visual
- **Input:** Storyline JSON, InterpretedBriefing JSON, SlideType Catalog, Transform Rules, TopicClassification constraints
- **Output:** PresentationPlan JSON
- **Regeln:** Title Logic, Slide Type Completeness, Historical Themes, Image Function, Deck Dramaturgy.
- **Wann:** Stage 4.

### 5. Content Filler Prompt (`content_filler_prompt.py`)
- **Rolle:** Texter fuer Geschaeftspraesentationen
- **Ziel:** Plan-Texte → finale Texte
- **Input:** Single SlidePlan JSON, Audience Profile, Image Style Profile
- **Output:** Gleiche JSON-Struktur mit finalisierten Texten + text_metrics
- **Regeln:** Headline als Aussage. Alle Blocks vollstaendig. Keine Platzhalter. Completeness Check.
- **Wann:** Stage 7.

### 6. Title Regenerator Prompt (NEU: `title_regenerator_prompt.py`)
- **Rolle:** Titel-Spezialist
- **Ziel:** Schwachen Titel → Aussage-Titel
- **Input:** aktueller Titel, core_message, slide_type, Kontext
- **Output:** Neuer headline string (max 70 chars)
- **Regeln:** Muss Verb enthalten. Muss Erkenntnis transportieren. Darf kein Topic-Label sein.
- **Wann:** Stage 6 oder 9 (bei title_only Regeneration).

### 7. Slide Regenerator Prompt (`regenerator_prompt.py`)
- **Rolle:** Praesentations-Architekt fuer Reparatur
- **Ziel:** Fehlerhaften Slide reparieren
- **Input:** Failed slide JSON, Errors, Kontext-Slides
- **Output:** Repariertes SlidePlan JSON
- **Regeln:** Alle Errors fixen. Typ darf aendern. Completeness erzwingen. Title Logic.
- **Wann:** Stage 6 oder 9.

### 8. Deck Restructurer Prompt (NEU: `deck_restructurer_prompt.py`)
- **Rolle:** Deck-Architekt
- **Ziel:** Globale Deck-Struktur reparieren
- **Input:** Ganzer PresentationPlan, TopicClassification, Deck-Level Errors
- **Output:** Neuer PresentationPlan (oder diff mit eingefuegten/geaenderten Slides)
- **Regeln:** Required types einfuegen. Varianz erhoehen. Template einhalten.
- **Wann:** Stage 6 (globale Regeneration).

---

## 12. TEMPLATE- UND RENDERING-STRATEGIE

### Was das LLM entscheiden darf

- slide_type (aus erlaubtem Katalog)
- headline, subheadline, core_message (innerhalb char-Limits)
- content_block Inhalte (Texte, Labels, Values)
- visual.image_description (Prompt fuer Bildgenerierung)
- visual.image_role (aus erlaubtem Katalog)
- speaker_notes

### Was der Code erzwingen MUSS

- **Slide-Positionen:** Position 1 = title_hero, Position N = closing.
- **Layout-Geometrie:** Alle x/y/w/h Werte aus Blueprints, nie vom LLM.
- **Schriftgroessen:** Aus Blueprints * Audience-Modifier, nie vom LLM.
- **Farben:** accent_color, font_color, background aus Code-Konfiguration.
- **Abstands-Regeln:** Padding, Whitespace aus Blueprint-Konstanten.
- **Textmengen-Limits:** MAX_CHARS pro Slide-Typ, MAX_BULLET_LEN, MAX_HEADLINE_LEN.
- **Block-Count-Limits:** Exakt 3 Cards, 3-4 KPIs, 3-6 Timeline Entries, etc.
- **Sequence Rules:** Keine 2 consecutiven gleichen Low-Content Typen.
- **Visual Constraints:** image_role != decorative (ausser fullbleed). Bildstil-Kompatibilitaet.

### Zielgruppe x Bildstil → Template-Modifikation

| Audience    | photo              | illustration       | minimal            | data_visual        |
|-------------|--------------------|--------------------|--------------------|--------------------|
| management  | 1 hero, 1 split    | 1 split            | kein Bild          | charts bevorzugt   |
| team        | 1-2 splits         | 1-2 splits         | kein Bild          | charts erlaubt     |
| customer    | 2 hero, 2 splits   | 1-2 splits         | kein Bild          | 1 chart erlaubt    |
| workshop    | 0-1 hero           | 0-1 split          | kein Bild          | kein Bild          |

### Slide-Typ → Layout Blueprint

Jeder Slide-Typ hat exakt 1 Blueprint (in `blueprints.py`). Der Blueprint definiert:
- Element-Positionen (cm-Werte fuer 16:9 / 25.4x19.05cm)
- Font-Groessen (Basis-Werte, skaliert durch Audience-Modifier)
- Shape-Positionen (Akzent-Balken, Card-Hintergruende, KPI-Karten)
- Dynamische Elemente (Timeline-Nodes, KPI-Karten werden durch Engine umverteilt)

### Design-Regeln (NICHT delegierbar)

- **Weissraum:** Min 1.8cm Seitenrand. Min 1.5cm Top-Padding. Body startet bei 4.8cm.
- **Abstaende:** Min 0.6cm Gap zwischen Elementen. Min 4pt Space-After bei Bullets.
- **Containerlogik:** Cards/KPIs in rounded_rectangle Shapes (corner_radius 0.35cm). Hintergrund #f3f4f6.
- **Bildflaechen:** image_text_split: Bild rechts, 11.4cm breit, volle Hoehe. image_fullbleed: 25.4x19.05cm.
- **Titelgroessen:** title_hero: 44pt. section_divider: 40pt. closing: 36pt. Standard: 28pt.
- **Visuelle Hierarchie:** headline (bold, dunkel) > body (regular, mittel) > caption (klein, grau).
- **Textmengen:** Enforced via MAX_CHARS pro Typ. Never > 500 chars auf einer Folie.

---

## 13. MODULSTRUKTUR

```
pptx-service/app/
├── api/
│   └── routes/
│       ├── generate.py          # V1 endpoint
│       └── generate_v2.py       # V2 endpoint
├── pipeline/
│   ├── __init__.py
│   ├── orchestrator.py          # 12-Stage Pipeline
│   ├── llm_client.py            # Gemini API calls
│   └── topic_classifier.py      # NEU: deterministic topic classification
├── prompts/
│   ├── __init__.py
│   ├── interpreter_prompt.py
│   ├── storyline_prompt.py
│   ├── slide_planner_prompt.py
│   ├── content_filler_prompt.py
│   ├── regenerator_prompt.py
│   ├── title_regenerator_prompt.py   # NEU
│   ├── deck_restructurer_prompt.py   # NEU
│   ├── reviewer_prompt.py
│   └── profiles.py              # Audience/ImageStyle profiles
├── schemas/
│   ├── __init__.py
│   └── models.py                # Alle Pydantic Models
├── slide_types/
│   ├── __init__.py
│   ├── registry.py              # SlideTypeDefinition mit Constraints
│   └── transforms.py            # Theme/Beat/Audience → SlideType Mappings
├── validators/
│   ├── __init__.py              # validate_plan(), validate_filled()
│   ├── slide_rules.py           # S001-S018
│   ├── deck_rules.py            # D001-D013
│   ├── topic_rules.py           # NEU: T001-T005
│   ├── fill_rules.py            # NEU: F001-F008
│   ├── title_analyzer.py        # NEU: analyze_title(), TitleSpec
│   └── auto_fixes.py            # Auto-fixable issues
├── regeneration/                 # NEU
│   ├── __init__.py
│   ├── regen_matrix.py          # Fehlerklasse → Strategie Mapping
│   ├── slide_regenerator.py     # Lokale Slide-Regeneration
│   ├── title_regenerator.py     # Title-only Regeneration
│   └── deck_restructurer.py     # Globale Deck-Reparatur
├── layouts/
│   ├── __init__.py
│   ├── engine.py                # FilledSlide → RenderInstruction
│   └── blueprints.py            # Pixel-genaue Layout-Definitionen
├── renderers/
│   ├── __init__.py
│   └── pptx_renderer_v2.py     # RenderInstruction → .pptx
├── services/
│   ├── image_service.py         # Imagen 3.0
│   ├── chart_service.py         # matplotlib Charts
│   ├── pptx_service.py          # V1 PPTX generation
│   └── template_service.py      # Template management
└── config.py
```

### Verantwortlichkeiten

| Modul | Verantwortung |
|-------|---------------|
| `pipeline/orchestrator.py` | Sequentielle Ausfuehrung aller 12 Stages |
| `pipeline/topic_classifier.py` | Deterministische Topic-Erkennung |
| `prompts/*` | LLM-Prompt-Templates |
| `schemas/models.py` | Alle Pydantic-Datenmodelle |
| `slide_types/registry.py` | Kanonische Constraints pro Slide-Typ |
| `slide_types/transforms.py` | Mapping-Tabellen |
| `validators/*` | Deterministische Qualitaetspruefung (PASS/FAIL/REGENERATE) |
| `regeneration/*` | Gezielte Reparatur (auto-fix + LLM) |
| `layouts/*` | Semantik → Geometrie (cm-Werte) |
| `renderers/*` | Geometrie → .pptx (python-pptx) |

---

## 14. UMSETZUNGSPLAN

### Phase 1: Title Logic + Fill-Validator (groesster schneller Hebel)

**Ziel:** Schwache Titel und unterfuellte Slides nach dem Filling erkennen und reparieren.

**Was gebaut wird:**
1. `validators/title_analyzer.py` — `analyze_title()` mit Verb-Erkennung, Topic-Label-Pattern, Quality-Score
2. `validators/fill_rules.py` — F001-F008 Post-Fill Validators
3. Orchestrator: Stage 8 (Fill Validator) + Stage 9 (Fill Regenerator) einfuegen
4. S014 durch `title_analyzer` ersetzen (praezisere Heuristik)

**Warum priorisiert:** Die meisten sichtbaren Qualitaetsprobleme entstehen durch schwache Titel und unterfuellte Slides NACH dem Filling. Der aktuelle Stage-8-Reviewer ist ein Stub.

**Erwarteter Hebel:** +30% bessere Titel. +20% weniger unterfuellte Slides.

**Risiken:** False Positives bei der Verb-Erkennung (Deutsch ist komplex). Mitigiert durch quality_score Threshold (0.4 = konservativ).

### Phase 2: Topic Classifier + Topic Rules (struktureller Umbau)

**Ziel:** Thementyp determiniert Deck-Constraints bevor das LLM den Plan macht.

**Was gebaut wird:**
1. `pipeline/topic_classifier.py` — Deterministische Topic-Klassifikation
2. `schemas/models.py` — TopicClassification, TopicType
3. `validators/topic_rules.py` — T001-T005
4. Orchestrator: Stage 2 (Topic Classifier) einfuegen zwischen Interpret und Storyline
5. TopicClassification in Storyline- und SlideePlanner-Prompts injizieren

**Warum priorisiert:** Ohne Topic-Klassifikation gibt es keine harten Constraints. Historische Themen bekommen keine Timeline, Strategie-Decks kein KPI.

**Erwarteter Hebel:** +40% bessere themenspezifische Decks. Historische Themen erzwingen Timeline.

**Risiken:** Keyword-basierte Klassifikation ist limitiert. Mitigiert durch breite Keyword-Sets und Fallback auf "general".

### Phase 3: Regeneration Engine (gezielte Reparatur)

**Ziel:** Fehlerhafte Slides gezielt reparieren statt blind neu zu generieren.

**Was gebaut wird:**
1. `regeneration/regen_matrix.py` — Fehlerklasse → Strategie Mapping
2. `regeneration/slide_regenerator.py` — Lokale Slide-Regeneration mit spezifischem Prompt
3. `regeneration/title_regenerator.py` — Title-only Regeneration
4. `regeneration/deck_restructurer.py` — Globale Deck-Reparatur
5. `prompts/title_regenerator_prompt.py` — Spezialisierter Titel-Prompt
6. `prompts/deck_restructurer_prompt.py` — Deck-Restructure-Prompt

**Warum priorisiert:** Der aktuelle Regenerator macht alles oder nichts. Gezielte Reparatur spart LLM-Calls und erhoeht Praezision.

**Erwarteter Hebel:** +25% weniger LLM-Calls. +30% hoehere Reparatur-Erfolgsrate.

**Risiken:** Komplexitaet der Regenerationsmatrix. Mitigiert durch einfache Mapping-Tabelle und klare Fallback-Logik.

### Phase 4: Feinsteuerung (Quality + Review)

**Ziel:** Visuelle QA, erweiterte Registry, Performance-Optimierung.

**Was gebaut wird:**
1. SlideTypeDefinition erweitern: min_content_blocks, min_headline_words, zielgruppen_eignung
2. Stage 12 (Post-Review) implementieren: LibreOffice → PDF → Sichtpruefung
3. Mapping-Tabelle Zielgruppe x Bildstil x Slide-Typ hardcoden in `transforms.py`
4. SlidePlan erweitern: topic_role, required_elements, validation_flags, regeneration_strategy
5. Performance: LLM-Call Caching, Token-Budget-Tracking

**Warum priorisiert:** Feinsteuerung bringt marginale Verbesserungen, die nach den strukturellen Aenderungen den letzten Schliff geben.

**Erwarteter Hebel:** +10% Gesamtqualitaet. Visuelle Fehler frueh erkennen.

**Risiken:** LibreOffice-Dependency auf dem Server. Mitigiert durch optionalen Stage-12.

---

## 15. KONKRETE ARTEFAKTE

### A. JSON-Schema: PresentationPlan

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PresentationPlan",
  "type": "object",
  "required": ["audience", "image_style", "slides", "metadata"],
  "properties": {
    "audience": {"type": "string", "enum": ["management", "team", "customer", "workshop"]},
    "image_style": {"type": "string", "enum": ["photo", "illustration", "minimal", "data_visual", "none"]},
    "topic_classification": {
      "type": "object",
      "properties": {
        "topic_type": {"type": "string", "enum": ["historical", "strategy", "comparison", "analytics", "workshop", "executive_update", "process", "general"]},
        "narrative_arc": {"type": "string"},
        "required_slide_types": {"type": "array", "items": {"type": "string"}},
        "min_content_slides": {"type": "integer", "minimum": 3}
      }
    },
    "slides": {
      "type": "array",
      "items": {"$ref": "#/definitions/SlidePlan"},
      "minItems": 5,
      "maxItems": 25
    },
    "metadata": {
      "type": "object",
      "properties": {
        "total_slides": {"type": "integer"},
        "estimated_duration_minutes": {"type": "integer"},
        "content_density": {"type": "string", "enum": ["light", "medium", "dense"]}
      }
    }
  },
  "definitions": {
    "SlidePlan": {
      "type": "object",
      "required": ["position", "slide_type", "headline"],
      "properties": {
        "position": {"type": "integer", "minimum": 1},
        "slide_type": {"type": "string", "enum": ["title_hero", "section_divider", "key_statement", "bullets_focused", "three_cards", "kpi_dashboard", "image_text_split", "comparison", "timeline", "process_flow", "chart_insight", "image_fullbleed", "agenda", "closing"]},
        "beat_ref": {"type": "integer"},
        "topic_role": {"type": "string"},
        "headline": {"type": "string", "maxLength": 70},
        "subheadline": {"type": "string", "maxLength": 120},
        "core_message": {"type": "string", "maxLength": 150},
        "content_blocks": {"type": "array"},
        "visual": {
          "type": "object",
          "properties": {
            "type": {"type": "string", "enum": ["photo", "illustration", "icon", "chart", "diagram", "none"]},
            "image_role": {"type": "string", "enum": ["hero", "supporting", "decorative", "evidence", "none"]},
            "image_description": {"type": "string", "maxLength": 250},
            "image_function": {"type": "string"},
            "chart_spec": {"type": "object"}
          }
        },
        "speaker_notes": {"type": "string", "maxLength": 600},
        "required_elements": {"type": "array", "items": {"type": "string"}},
        "validation_flags": {"type": "array", "items": {"type": "string"}},
        "regeneration_strategy": {"type": "string", "enum": ["none", "title_only", "content_only", "full", "type_change"]}
      }
    }
  }
}
```

### B. Erlaubte Slide-Typen (kompakt)

```python
ALLOWED_SLIDE_TYPES = [
    "title_hero", "section_divider", "key_statement", "bullets_focused",
    "three_cards", "kpi_dashboard", "image_text_split", "comparison",
    "timeline", "process_flow", "chart_insight", "image_fullbleed",
    "agenda", "closing",
]
```

### C. Titel-Regelwerk

```python
TITLE_RULES = {
    "min_words": 4,             # Aussage braucht Subjekt + Praedikat + Objekt
    "max_chars": 70,
    "must_have_verb": True,     # fuer non-hero, non-divider, non-agenda
    "forbidden_patterns": [
        r"^[A-Z][a-z\s&]+$",   # Reines Thema ohne Verb
        r"^\w+$",               # Einwort-Titel
    ],
    "weak_keywords": [
        "ueberblick", "einleitung", "zusammenfassung", "hintergrund",
        "kontext", "ausgangslage", "aktuelle entwicklungen", "fazit",
    ],
    "quality_threshold": 0.4,   # Minimum quality_score
    "exempt_types": ["title_hero", "section_divider", "agenda"],
}
```

### D. Transformationsregeln je Thementyp

```python
TOPIC_DECK_TEMPLATES = {
    "historical": {
        "arc": "chronological",
        "required": ["timeline"],
        "recommended": ["comparison", "image_text_split"],
        "min_slides": 7,
        "pattern": "hero → timeline → epoch* → relevance → closing",
    },
    "strategy": {
        "arc": "situation_complication_resolution",
        "required": ["kpi_dashboard"],
        "recommended": ["process_flow", "three_cards"],
        "min_slides": 7,
        "pattern": "hero → status → challenge → pillars → roadmap → targets → closing",
    },
    "comparison": {
        "arc": "compare_decide",
        "required": ["comparison"],
        "recommended": ["kpi_dashboard"],
        "min_slides": 6,
        "pattern": "hero → context → comparison → data → recommendation → closing",
    },
    "analytics": {
        "arc": "situation_complication_resolution",
        "required": ["kpi_dashboard", "chart_insight"],
        "recommended": [],
        "min_slides": 6,
        "pattern": "hero → kpis → trend → details → interpretation → closing",
    },
    "executive_update": {
        "arc": "situation_complication_resolution",
        "required": ["kpi_dashboard"],
        "recommended": ["chart_insight", "process_flow"],
        "min_slides": 6,
        "pattern": "hero → status → highlights → risks → next_steps → closing",
    },
    "general": {
        "arc": "thematic_cluster",
        "required": [],
        "recommended": ["three_cards", "bullets_focused"],
        "min_slides": 5,
        "pattern": "hero → points → detail → closing",
    },
}
```

### E. Bildfunktions-Regeln

```python
IMAGE_FUNCTION_RULES = {
    "allowed_functions": ["zeitgeist", "anchor", "contrast", "evidence", "hero", "product"],
    "disallowed": ["decorative"],  # ausser bei image_fullbleed
    "min_description_length": 20,
    "max_image_slides_per_style": {
        "photo": 3, "illustration": 2, "minimal": 0, "data_visual": 0, "none": 0,
    },
    "image_slides": ["title_hero", "image_text_split", "image_fullbleed"],
    "no_image_slides": [
        "section_divider", "key_statement", "bullets_focused", "three_cards",
        "kpi_dashboard", "comparison", "timeline", "process_flow",
        "chart_insight", "agenda", "closing",
    ],
}
```

### F. Slide-Level Validator-Regeln (vollstaendig)

```python
SLIDE_VALIDATORS = [
    {"id": "S001", "check": "headline_required",         "severity": "error",   "auto_fix": False},
    {"id": "S002", "check": "headline_max_70",            "severity": "error",   "auto_fix": True,  "threshold": 70},
    {"id": "S003", "check": "core_message_required",      "severity": "warning", "auto_fix": False},
    {"id": "S004", "check": "valid_slide_type",           "severity": "error",   "auto_fix": False},
    {"id": "S005", "check": "bullets_max_count",          "severity": "error",   "auto_fix": True},
    {"id": "S006", "check": "bullet_text_max_80",         "severity": "error",   "auto_fix": True,  "threshold": 80},
    {"id": "S007", "check": "no_generic_headline",        "severity": "warning", "auto_fix": False},
    {"id": "S008", "check": "blocks_match_type",          "severity": "error",   "auto_fix": False},
    {"id": "S009", "check": "visual_role_valid",          "severity": "warning", "auto_fix": True},
    {"id": "S010", "check": "text_density_limit",         "severity": "error",   "auto_fix": True},
    {"id": "S011", "check": "kpi_has_value",              "severity": "error",   "auto_fix": False},
    {"id": "S012", "check": "timeline_min_entries",       "severity": "error",   "auto_fix": False, "threshold": 3},
    {"id": "S013", "check": "speaker_notes_present",      "severity": "warning", "auto_fix": False},
    {"id": "S014", "check": "headline_is_statement",      "severity": "warning", "auto_fix": False},
    {"id": "S015", "check": "type_fully_populated",       "severity": "error",   "auto_fix": False},
    {"id": "S016", "check": "image_has_function",         "severity": "error",   "auto_fix": True},
    {"id": "S017", "check": "timeline_entries_complete",   "severity": "warning", "auto_fix": False},
    {"id": "S018", "check": "cards_have_body",            "severity": "warning", "auto_fix": False},
]
```

### G. Deck-Level Validator-Regeln (vollstaendig)

```python
DECK_VALIDATORS = [
    {"id": "D001", "check": "starts_with_title_hero",     "severity": "error"},
    {"id": "D002", "check": "ends_with_closing",          "severity": "error"},
    {"id": "D003", "check": "min_3_type_variety",         "severity": "error",   "threshold": 3},
    {"id": "D004", "check": "no_consecutive_bullets",      "severity": "error"},
    {"id": "D005", "check": "no_3_same_type_in_row",      "severity": "warning"},
    {"id": "D006", "check": "slide_count_5_to_25",        "severity": "error",   "threshold": [5, 25]},
    {"id": "D007", "check": "max_2_key_statements",        "severity": "warning", "threshold": 2},
    {"id": "D008", "check": "no_divider_at_end",          "severity": "error"},
    {"id": "D009", "check": "historical_needs_timeline",   "severity": "error"},
    {"id": "D010", "check": "max_low_content_slides",     "severity": "warning", "threshold": "max(3, n//3)"},
    {"id": "D011", "check": "no_3_consecutive_low",       "severity": "error",   "threshold": 2},
    {"id": "D012", "check": "closing_not_prose",           "severity": "warning"},
    {"id": "D013", "check": "dramaturgic_variety",        "severity": "warning", "threshold": 0.6},
]
```

### H. Regenerationsmatrix

```python
REGEN_MATRIX = {
    "S002": {"strategy": "truncate",      "scope": "local",  "llm": False},
    "S005": {"strategy": "trim",           "scope": "local",  "llm": False},
    "S006": {"strategy": "truncate",       "scope": "local",  "llm": False},
    "S009": {"strategy": "visual_fix",     "scope": "local",  "llm": False},
    "S010": {"strategy": "truncate",       "scope": "local",  "llm": False},
    "S014": {"strategy": "title_only",     "scope": "local",  "llm": True},
    "S015": {"strategy": "content_fill",   "scope": "local",  "llm": True},
    "S016": {"strategy": "visual_fix",     "scope": "local",  "llm": False},
    "S017": {"strategy": "content_fill",   "scope": "local",  "llm": True},
    "S018": {"strategy": "content_fill",   "scope": "local",  "llm": True},
    "D009": {"strategy": "deck_insert",    "scope": "global", "llm": True},
    "D013": {"strategy": "deck_restructure", "scope": "global", "llm": True},
    "F001": {"strategy": "title_only",     "scope": "local",  "llm": True},
    "F002": {"strategy": "content_fill",   "scope": "local",  "llm": True},
    "H001": {"strategy": "title_only",     "scope": "local",  "llm": True},
    "H002": {"strategy": "title_only",     "scope": "local",  "llm": True},
}
```

### I. Pseudocode: End-to-End Flow

```python
async def run_pipeline(user_input, document_text, audience, image_style, ...):
    # Stage 1: Interpret
    briefing = await llm_interpret(user_input, document_text)

    # Stage 2: Classify (NEU, deterministic)
    topic_class = classify_topic(briefing)

    # Stage 3: Storyline
    storyline = await llm_storyline(briefing, topic_class)

    # Stage 4: Slide Plan
    plan = await llm_slide_plan(storyline, briefing, topic_class)

    # Stage 5: Plan Validate
    plan_validation = validate_plan(plan, topic_class)

    # Stage 6: Plan Regenerate
    if plan_validation.requires_regeneration:
        plan, plan_validation = await regeneration_loop(plan, plan_validation, topic_class)

    # Stage 7: Content Fill
    filled_slides = await asyncio.gather(*[llm_fill(slide) for slide in plan.slides])

    # Stage 8: Fill Validate (NEU)
    fill_validation = validate_filled(filled_slides, topic_class, audience)

    # Stage 9: Fill Regenerate (NEU)
    if fill_validation.requires_regeneration:
        filled_slides = await fill_regeneration_loop(filled_slides, fill_validation)

    # Stage 10: Layout
    render_instructions = [layout_engine.calculate(slide) for slide in filled_slides]

    # Stage 11: Render
    pptx_path = renderer.render(render_instructions)

    # Stage 12: Post-Review
    quality = post_review(filled_slides, plan, pptx_path)

    return PipelineResult(pptx_path, plan, filled_slides, quality)
```

### J. Mapping-Tabelle: Zielgruppe x Bildstil x Slide-Typ

| Audience    | Bildstil      | Bevorzugte Slide-Typen                                 | Verbotene Slide-Typen         |
|-------------|---------------|--------------------------------------------------------|-------------------------------|
| management  | photo         | kpi_dashboard, key_statement, image_text_split         | —                             |
| management  | minimal       | kpi_dashboard, key_statement, chart_insight            | image_fullbleed, image_split  |
| management  | data_visual   | chart_insight, kpi_dashboard, comparison               | image_fullbleed, image_split  |
| team        | photo         | bullets_focused, process_flow, image_text_split        | —                             |
| team        | minimal       | bullets_focused, process_flow, timeline                | image_fullbleed, image_split  |
| customer    | photo         | image_fullbleed, image_text_split, three_cards         | —                             |
| customer    | illustration  | image_text_split, three_cards, key_statement           | image_fullbleed               |
| customer    | minimal       | key_statement, three_cards, bullets_focused             | image_fullbleed, image_split  |
| workshop    | photo         | bullets_focused, comparison, three_cards               | —                             |
| workshop    | minimal       | bullets_focused, comparison, three_cards               | image_fullbleed, image_split  |

---

## ZUSAMMENFASSUNG DER ARCHITEKTUR-ENTSCHEIDUNGEN

1. **Topic Classification ist deterministisch, nicht LLM-basiert.** Keyword-Matching ist zuverlaessiger als LLM-Klassifikation und erzwingt harte Constraints.
2. **Validation passiert zweimal:** nach dem Plan UND nach dem Filling. Der aktuelle Single-Validation-Ansatz laesst Post-Fill-Fehler durch.
3. **Regeneration ist differenziert:** Title-only, Content-only, Type-Change, Deck-Restructure. Nicht alles-oder-nichts.
4. **Layout-Geometrie ist Code, nicht LLM.** Blueprints mit cm-Werten. Audience-Modifier als Skalierungsfaktoren. Keine LLM-Entscheidung ueber Schriftgroessen oder Positionen.
5. **SlideTypeDefinition wird zur Source-of-Truth** fuer min/max Constraints, nicht die Prompts. Validators lesen aus der Registry, nicht aus hartcodierten Werten.
6. **Titel-Qualitaet wird linguistisch geprueft** (Verb-Erkennung, Pattern-Matching), nicht nur ueber Laenge/Wortanzahl.
