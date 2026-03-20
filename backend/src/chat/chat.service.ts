import { Injectable, Logger } from '@nestjs/common';
import OpenAI from 'openai';
import { SettingsService } from '../settings/settings.service';
import { TemplatesService, LayoutConstraint, TemplateTheme } from '../templates/templates.service';
import { TemplateAnalysisService, TemplateAnalysis, TemplateProfile } from '../templates/template-analysis.service';
import { ChatResponseDto, SlideDto, ClarifyResponseDto } from './chat.dto';

const BASE_SYSTEM_PROMPT = `Du bist "Clarity Engine" — ein Experte für strategisches Präsentationsdesign \
und Business-Kommunikation. Du erstellst professionelle, visuell überzeugende und inhaltlich \
exzellente Präsentationen im strukturierten Markdown-Format.

DEINE GRUNDPRINZIPIEN:
1. KLARHEIT VOR DICHTE: "Eine Kernaussage pro Folie" ist heilig. Überladene Folien werden \
   auf mehrere Folien aufgeteilt. Komplexe Themen werden in verständliche Einzelfolien heruntergebrochen.
2. AUSSAGEKRÄFTIGE TITEL: Folientitel sind prägnante Aussagen, die die Kernbotschaft transportieren — \
   NICHT bloße Schlagworte. Beispiel: "Umsatz im Q3 um 15% gesteigert" statt "Umsatz Q3".
3. NARRATIVER ROTER FADEN: Jede Präsentation folgt einer klaren Dramaturgie: \
   Einstieg (Problem/Kontext) → Hauptteil (Analyse/Lösung/Daten) → Schluss (Zusammenfassung/Call to Action).
4. SPRECHERNOTIZEN NUTZEN: Alle Details, Hintergrundinformationen und Erläuterungen gehören in \
   die Sprechernotizen (<!-- notes: -->). Die Folie selbst bleibt schlank und visuell klar.
5. PROFESSIONELLER TONFALL: Aktive Sprache, keine Füllwörter, kein Jargon. \
   Klare, stakeholder-gerechte Kommunikation.

DEIN ARBEITSPROZESS:
- Bei Dokumenten als Eingabe: Extrahiere Kernaussagen, Schlüsseldaten und die logische Struktur. \
  Fasse lange Absätze in prägnante Stichpunkte zusammen. Überflüssiges weglassen.
- Bei Prompts: Folge den Anweisungen. Ergänze fehlende Struktur eigenständig \
  (Einleitung, Schluss, Gliederung).
- Denke immer visuell: Wo sinnvoll, schlage Diagramme, Vergleiche oder Gegenüberstellungen \
  in den Sprechernotizen vor.

FORMAT-REGELN (STRIKT — KEINE AUSNAHMEN):
- Jede Folie beginnt mit "---" als Trenner (außer die erste Folie).
- Die erste Folie ist IMMER eine Titelfolie mit <!-- layout: title -->.
- Jede Folie hat einen <!-- layout: TYPE --> Kommentar. Erlaubte Typen:
  title, section, content, two_column, image, chart, closing
- Überschriften: # für Folientitel, ## für Untertitel.
- Aufzählungen mit "- " für Bullet Points.
- Sprechernotizen nach "<!-- notes:" bis "-->" — nutze sie IMMER für Kontext und Details.
- Max 4-5 Bullet Points pro Folie. Kürzer ist besser.
- Bullet Points: Maximal 1-2 Zeilen. Kernaussage, kein Fließtext.
- Antworte NUR mit dem Markdown, keine Erklärungen oder Kommentare außerhalb.

BILD-REGELN (STRIKT):
- Bilder NUR auf Folien mit <!-- layout: image --> verwenden.
- Auf image-Folien: GENAU EIN Bild pro Folie mit der Syntax: ![Beschreibung](placeholder)
- Das Bild steht DIREKT unter dem Titel, OHNE Bullet Points.
- Die Bildbeschreibung im Alt-Text muss konkret und visuell sein.
- NIEMALS ![...](placeholder) auf content-, two_column- oder anderen Folien verwenden.
- Maximale Struktur einer Bildfolie:
  <!-- layout: image -->
  # Folientitel
  ![Bildbeschreibung](placeholder)
  <!-- notes: Kontext zum Bild -->

DIAGRAMM-REGELN:
- Diagramme NUR auf Folien mit <!-- layout: chart --> verwenden.
- Auf chart-Folien: GENAU EIN Diagramm-Block pro Folie im JSON-Format.
- Das Diagramm steht DIREKT unter dem Titel.
- Syntax für Diagramme:
  \`\`\`chart
  {"type":"bar","title":"Umsatz nach Quartal","labels":["Q1","Q2","Q3","Q4"],
   "datasets":[{"label":"2025","values":[120,150,180,200]},{"label":"2024","values":[100,120,140,160]}],
   "x_label":"Quartal","y_label":"Umsatz (Mio. €)","show_values":true}
  \`\`\`
- Erlaubte Diagramm-Typen: bar, line, pie, donut, stacked_bar, horizontal_bar
- Wähle den Diagramm-Typ passend zu den Daten:
  * bar: Kategorien vergleichen (Umsatz, Kosten, Mitarbeiter)
  * line: Zeitverläufe und Trends
  * pie/donut: Anteile an einem Ganzen (max 6 Segmente)
  * stacked_bar: Zusammensetzung über Kategorien
  * horizontal_bar: Ranking / Sortierung
- Maximale Struktur einer Diagrammfolie:
  <!-- layout: chart -->
  # Folientitel
  \`\`\`chart
  {"type":"bar","labels":[...],"datasets":[...],"show_values":true}
  \`\`\`
  <!-- notes: Erklärung und Quellenangaben -->

BEISPIEL:
<!-- layout: title -->
# Digitale Transformation beschleunigt Wachstum
## Quartalsbericht Q1 2026 für das Management

<!-- notes: Begrüßung, kurze Agenda: Finanzergebnisse, strategische Initiativen, Ausblick -->

---

<!-- layout: section -->
# Finanzielle Highlights

---

<!-- layout: content -->
# Umsatz um 15% gegenüber Vorjahr gesteigert
- Gesamtumsatz: €234 Mio. (+15% YoY)
- Haupttreiber: Digitale Produkte (+28%)
- EBITDA-Marge auf 23,4% verbessert
- Kundenbasis: +12.000 Neukunden

<!-- notes: Der Umsatzanstieg ist primär auf das Wachstum im Segment Digitale Produkte zurückzuführen. \
Die EBITDA-Marge profitiert von Skaleneffekten in der Cloud-Infrastruktur. Details auf Nachfrage. -->

---

<!-- layout: two_column -->
# Wir liegen vor dem Wettbewerb
## Unser Unternehmen
- Marktanteil: 34%
- Wachstum: +8% YoY
## Wettbewerb
- Wettbewerber A: 28%
- Wettbewerber B: 19%

<!-- notes: Quelle: Marktanalyse McKinsey Q4 2025. Unser Vorsprung wächst insbesondere im KMU-Segment. -->

---

<!-- layout: closing -->
# Nächste Schritte
## Fragen & Diskussion

---

<!-- layout: image -->
# Das Team hinter der Transformation

![Gruppenfoto des Projektteams in einem modernen Büro mit Whiteboard im Hintergrund](placeholder)

<!-- notes: Foto des erweiterten Projektteams. Aufgenommen beim letzten Sprint Review im März 2026. -->

---

<!-- layout: chart -->
# Umsatzentwicklung zeigt starkes Wachstum

\`\`\`chart
{"type":"bar","title":"Umsatz nach Quartal","labels":["Q1","Q2","Q3","Q4"],"datasets":[{"label":"2026","values":[234,256,280,310]},{"label":"2025","values":[180,200,220,250]}],"y_label":"Umsatz (Mio. €)","show_values":true}
\`\`\`

<!-- notes: Vergleich 2026 vs. 2025 zeigt durchgängig zweistelliges Wachstum. Haupttreiber: Digitale Produkte. -->
`;

const AUDIENCE_PROMPTS: Record<string, string> = {
  team: `ZIELGRUPPE: Team / Kolleg:innen
- Pragmatischer, direkter Ton. Technische Begriffe sind erlaubt.
- Fokus auf Umsetzung: Was ist zu tun? Wer? Bis wann?
- Action Items und nächste Schritte konkret benennen.
- Details dürfen auf die Folien — das Team braucht Kontext zum Arbeiten.
- Sprechernotizen für Hintergrundinformationen und Quellen.`,

  management: `ZIELGRUPPE: Management / C-Level / Stakeholder
- Strategischer, ergebnisorientierter Ton. Kein Fachjargon.
- Fokus auf Business Impact: KPIs, ROI, strategische Entscheidungen.
- "So what?" bei jeder Folie — was bedeutet das für die Strategie?
- Folie zeigt nur Kernaussage + 2-3 starke Datenpunkte.
- Alle Details und Herleitungen in die Sprechernotizen.
- Executive Summary als zweite Folie nach dem Titel.`,

  casual: `ZIELGRUPPE: Workshop / Meeting / Informell
- Lockerer, einladender Ton. Kurze, aktivierende Sätze.
- Sehr wenig Text pro Folie — visuell und leicht denken.
- Interaktive Elemente in Sprechernotizen vorschlagen (Fragen ans Publikum, Diskussionspunkte).
- Maximal 3 Bullets pro Folie, jeweils nur eine Zeile.
- Mehr section-Folien als thematische Denkpausen einsetzen.`,
};

const VALID_LAYOUTS = new Set(['title', 'section', 'content', 'two_column', 'image', 'chart', 'closing']);

const IMAGE_STYLE_PROMPTS: Record<string, string> = {
  photo: `BILDSTIL: Fotografie
- Verwende den Layout-Typ "image" für Bildfolien.
- Beschreibe realistische, professionelle Fotos als Bildbeschreibung.
- Setze Bildbeschreibungen als: ![Detaillierte Beschreibung des gewünschten Fotos](placeholder)
- Mindestens 2-3 Bildfolien pro Präsentation einbauen, um visuelle Abwechslung zu schaffen.
- Bildbeschreibungen müssen konkret und visuell sein, z.B.: "Modernes Büro mit Team am Whiteboard bei einem Workshop"
- Nutze Bilder als emotionale Verstärker für die Kernbotschaft der jeweiligen Folie.`,

  illustration: `BILDSTIL: Illustration & Grafiken
- Verwende den Layout-Typ "image" für Bildfolien.
- Beschreibe Infografiken, Diagramme, Illustrationen und schematische Darstellungen.
- Setze Bildbeschreibungen als: ![Detaillierte Beschreibung der Illustration](placeholder)
- Mindestens 2-3 Bildfolien pro Präsentation einbauen.
- Bevorzuge erklärende Grafiken: Flowcharts, Prozessdiagramme, Vergleichsmatrizen, Zeitachsen.
- Bildbeschreibungen müssen die Art der Grafik und ihren Inhalt klar benennen, z.B.: "Flowchart: Drei-Schritte-Prozess von Anfrage über Validierung bis zur Freigabe"`,

  minimal: `BILDSTIL: Minimal / Icons
- Verwende den Layout-Typ "image" sparsam, nur wenn ein Icon oder Symbol die Aussage unterstützt.
- Beschreibe abstrakte Formen, Icons oder symbolische Darstellungen.
- Setze Bildbeschreibungen als: ![Beschreibung des Icons oder Symbols](placeholder)
- 1-2 Bildfolien pro Präsentation maximal.
- Bevorzuge einfache, flache Icons und geometrische Formen.
- Bildbeschreibungen kurz halten, z.B.: "Zahnrad-Icon symbolisiert Automatisierung"`,

  none: `BILDSTIL: Keine Bilder
- Verwende NIEMALS den Layout-Typ "image".
- Die Präsentation besteht ausschließlich aus Text-Layouts: title, section, content, two_column, closing.
- Nutze stattdessen starke Bullet Points, Zahlen und Vergleiche für visuelle Wirkung.
- Setze section-Folien als visuelle Pausen zwischen Themenblöcken ein.`,
};

@Injectable()
export class ChatService {
  private readonly logger = new Logger(ChatService.name);

  constructor(
    private readonly settings: SettingsService,
    private readonly templates: TemplatesService,
    private readonly analysis: TemplateAnalysisService,
  ) {}

  private async createClient(): Promise<OpenAI> {
    const token = await this.settings.getAccessToken();
    return new OpenAI({
      baseURL: this.settings.getBaseURL(),
      apiKey: token,
    });
  }

  async clarify(
    prompt: string,
    documentTexts: string[] = [],
  ): Promise<ClarifyResponseDto> {
    this.logger.log(`Clarify check for: ${prompt.slice(0, 80)}...`);

    const hasDocuments = documentTexts.length > 0;

    const systemPrompt = `Du bist ein Experte für Präsentationsdesign. Deine Aufgabe: Bewerte, ob der \
folgende Prompt EINDEUTIG GENUG ist, um eine professionelle Präsentation zu erstellen.

WICHTIG — Bevorzuge KLAR:
- Frage NUR, wenn das Thema wirklich mehrdeutig ist oder ein Fachbegriff völlig unterschiedliche \
  Bedeutungen haben könnte (z.B. "KNX" könnte Bustechnologie oder etwas anderes sein).
- Frage NICHT nach Zielgruppe, Umfang oder Detailtiefe — das sind Standardentscheidungen, \
  die du als Experte selbst treffen kannst.
- Wenn der Nutzer ein konkretes Thema mit erkennbarem Fokus nennt, ist das KLAR.
- Beispiele für KLAR: "Präsentation über unsere Q1-Ergebnisse", "10 Folien über Cloud Migration", \
  "Vergleich React vs Angular für unser Team"
- Beispiele für Rückfragen: "Präsentation über KNX" (mehrdeutig), "Präsentation über das Projekt" \
  (welches Projekt?), "Etwas über Sicherheit" (IT-Sicherheit? Arbeitssicherheit?)

${hasDocuments ? 'HINWEIS: Der Nutzer hat Dokumente angehängt. Wenn Dokumente vorhanden sind, antworte IMMER mit KLAR — die Dokumente liefern den nötigen Kontext.' : ''}

ANTWORT-FORMAT:
- Wenn der Prompt klar genug ist: Antworte NUR mit dem Wort KLAR
- Wenn das Thema wirklich unklar ist: Stelle 2-3 kurze Fragen mit "- ". Erkläre kurz, warum du fragst.`;

    const client = await this.createClient();

    try {
      const response = await client.chat.completions.create({
        model: this.settings.getModel(),
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: prompt },
        ],
        temperature: 0.3,
        max_tokens: 4096,
      });

      const choice = response.choices[0];
      const answer = choice?.message?.content?.trim() ?? '';

      if (!answer || answer.toUpperCase().startsWith('KLAR')) {
        this.logger.log('Clarify: prompt is clear, no questions needed');
        return { needsClarification: false, questions: '' };
      }

      this.logger.log('Clarify: questions generated');
      return { needsClarification: true, questions: answer };
    } catch (err) {
      this.logger.warn(`Clarify LLM call failed: ${err}`);
      return { needsClarification: false, questions: '' };
    }
  }

  async generate(
    prompt: string,
    documentTexts: string[] = [],
    templateId?: string,
    audience?: string,
    imageStyle?: string,
  ): Promise<ChatResponseDto> {
    this.logger.log(`Generating slides for: ${prompt.slice(0, 80)}... [audience=${audience ?? 'default'}, imageStyle=${imageStyle ?? 'default'}]`);

    let userContent = prompt;
    if (documentTexts.length > 0) {
      userContent = `AUFGABE: ${prompt}

QUELLMATERIAL (extrahiert aus ${documentTexts.length} Dokument${documentTexts.length > 1 ? 'en' : ''}):
Extrahiere die Kernaussagen, Schlüsseldaten und die logische Struktur. \
Fasse lange Absätze in prägnante Stichpunkte zusammen. Überflüssiges weglassen. \
Details und Hintergrundinformationen gehören in die Sprechernotizen.

${documentTexts.join('\n\n')}`;
    }

    const theme = templateId ? await this.templates.getTheme(templateId) : null;
    const aiAnalysis = templateId ? await this.analysis.getAnalysis(templateId) : null;
    const systemPrompt = await this.buildSystemPrompt(templateId, audience, imageStyle);

    const client = await this.createClient();
    const model = this.settings.getModel();

    let response: OpenAI.Chat.Completions.ChatCompletion;
    try {
      response = await client.chat.completions.create({
        model,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userContent },
        ],
        temperature: 0.5,
        max_tokens: 8192,
      });
    } catch (err: unknown) {
      const status = (err as { status?: number }).status;
      if (status === 404) {
        throw new Error(
          `Modell "${model}" ist in der aktuellen Region nicht verfügbar. ` +
          `Bitte wechsle in den Einstellungen zu einem anderen Modell (z.B. gemini-2.5-flash) oder einer anderen Region.`,
        );
      }
      throw err;
    }

    let markdown = response.choices[0]?.message?.content?.trim() ?? '';
    let slides = this.parseMarkdown(markdown);

    // Post-generation step 1: fix structural issues (images on wrong slides, etc.)
    const structuralResult = await this.validateStructure(client, markdown, slides);
    markdown = structuralResult.markdown;
    slides = structuralResult.slides;

    // Post-generation step 2: validate readability and auto-fix overflow
    const constraintMap = this.buildConstraintMapFromAll(theme, aiAnalysis);
    if (constraintMap.size > 0) {
      const validated = await this.validateAndFix(client, markdown, slides, constraintMap);
      markdown = validated.markdown;
      slides = validated.slides;
    }

    this.logger.log(`Generated ${slides.length} slides`);
    return { markdown, slides };
  }

  /**
   * Check for structural issues: images on wrong slides, misplaced markdown syntax, etc.
   * Auto-fix via Gemini if problems found.
   */
  private async validateStructure(
    client: OpenAI,
    markdown: string,
    slides: SlideDto[],
  ): Promise<{ markdown: string; slides: SlideDto[] }> {
    const issues: string[] = [];

    for (let i = 0; i < slides.length; i++) {
      const slide = slides[i];
      const slideNum = i + 1;

      // Check: image markdown on non-image slides
      const rawSlides = markdown.split(/^\s*---\s*$/m).filter((s) => s.trim());
      const rawSlide = rawSlides[i] ?? '';
      const hasImageMd = /!\[[^\]]*\]\([^)]*\)/.test(rawSlide);

      if (hasImageMd && slide.layout !== 'image') {
        issues.push(
          `Folie ${slideNum} (${slide.layout}): Enthält Bild-Markdown ![...](placeholder), ist aber KEIN image-Layout. ` +
          `Bild-Syntax darf NUR auf <!-- layout: image --> Folien stehen.`,
        );
      }

      // Check: image slide without image markdown
      if (slide.layout === 'image' && !hasImageMd) {
        issues.push(
          `Folie ${slideNum} (image): Ist als Bild-Layout markiert, enthält aber kein ![Beschreibung](placeholder).`,
        );
      }

      // Check: image slide has bullets (shouldn't)
      if (slide.layout === 'image' && slide.bullets.length > 0) {
        issues.push(
          `Folie ${slideNum} (image): Bild-Folien sollten KEINE Bullet Points enthalten. ` +
          `Text gehört in die Sprechernotizen.`,
        );
      }
    }

    if (issues.length === 0) {
      this.logger.log('Structural check passed — no issues detected');
      return { markdown, slides };
    }

    this.logger.warn(`Structural issues found: ${issues.length}, requesting Gemini fix`);

    const fixPrompt = `Du bist "Clarity Engine" — ein Experte für Präsentationsdesign. \
Die folgende Markdown-Präsentation hat STRUKTURELLE PROBLEME, die behoben werden müssen.

GEFUNDENE PROBLEME:
${issues.map((i) => `- ${i}`).join('\n')}

KORREKTUR-REGELN:
1. Bild-Markdown (![Beschreibung](placeholder)) darf NUR auf Folien mit <!-- layout: image --> stehen.
2. Wenn ein Bild auf einer falschen Folie steht: Erstelle eine NEUE image-Folie direkt danach \
   und verschiebe das Bild dorthin. Oder entferne das Bild und verlagere die Beschreibung in die Sprechernotizen.
3. image-Folien haben NUR: layout-Kommentar, # Titel, ![Beschreibung](placeholder), Sprechernotizen.
   KEINE Bullet Points, KEIN Fließtext auf image-Folien.
4. Behalte alle anderen Folien UNVERÄNDERT.
5. Behalte alle <!-- layout: TYPE --> und <!-- notes: --> Kommentare bei.
6. Antworte NUR mit dem vollständigen korrigierten Markdown.`;

    try {
      const response = await client.chat.completions.create({
        model: this.settings.getModel(),
        messages: [
          { role: 'system', content: fixPrompt },
          { role: 'user', content: markdown },
        ],
        temperature: 0.2,
        max_tokens: 8192,
      });

      const fixedMarkdown = response.choices[0]?.message?.content?.trim() ?? '';
      if (!fixedMarkdown) return { markdown, slides };

      const fixedSlides = this.parseMarkdown(fixedMarkdown);
      if (fixedSlides.length > 0) {
        this.logger.log(`Structural fix applied: ${slides.length} → ${fixedSlides.length} slides`);
        return { markdown: fixedMarkdown, slides: fixedSlides };
      }
    } catch (err) {
      this.logger.warn(`Structural fix LLM call failed: ${err}`);
    }

    return { markdown, slides };
  }

  private async buildSystemPrompt(templateId?: string, audience?: string, imageStyle?: string): Promise<string> {
    const audienceBlock = audience && AUDIENCE_PROMPTS[audience]
      ? `\n${AUDIENCE_PROMPTS[audience]}\n`
      : '';

    const imageBlock = imageStyle && IMAGE_STYLE_PROMPTS[imageStyle]
      ? `\n${IMAGE_STYLE_PROMPTS[imageStyle]}\n`
      : '';

    if (!templateId || templateId === 'default') {
      return `${BASE_SYSTEM_PROMPT}${audienceBlock}${imageBlock}`;
    }

    // Try rich profile first (from deep learning)
    const profile = this.analysis.getProfile(templateId);
    const aiAnalysis = await this.analysis.getAnalysis(templateId);
    const theme = await this.templates.getTheme(templateId);

    if (!theme && !aiAnalysis && !profile) {
      return `${BASE_SYSTEM_PROMPT}${audienceBlock}${imageBlock}`;
    }

    // Build template design info — profile is richest, then analysis, then theme
    let templateBlock = '';

    if (profile) {
      templateBlock = this.buildProfilePromptBlock(profile);
    } else if (aiAnalysis) {
      templateBlock = this.buildAnalysisPromptBlock(aiAnalysis, theme);
    } else if (theme) {
      templateBlock = this.buildThemeFallbackBlock(theme);
    }

    return `${BASE_SYSTEM_PROMPT}${audienceBlock}${imageBlock}\n${templateBlock}`;
  }

  private buildProfilePromptBlock(profile: TemplateProfile): string {
    // Group layouts by type for cleaner presentation
    const byType = new Map<string, Array<typeof profile.layout_catalog[0]>>();
    for (const m of profile.layout_catalog) {
      if (m.mapped_type === 'unused') continue;
      if (!byType.has(m.mapped_type)) byType.set(m.mapped_type, []);
      byType.get(m.mapped_type)!.push(m);
    }

    const layoutLines: string[] = [];
    for (const [type, layouts] of byType) {
      if (layouts.length === 1) {
        const m = layouts[0];
        const constraintStr = this.formatConstraints(m);
        layoutLines.push(`- ${type} ("${m.layout_name}"): ${m.description}${constraintStr}\n  → ${m.recommended_usage}`);
      } else {
        // Multiple layouts for same type — list them
        for (const m of layouts) {
          const constraintStr = this.formatConstraints(m);
          layoutLines.push(`- ${type} ("${m.layout_name}"): ${m.description}${constraintStr}\n  → ${m.recommended_usage}`);
        }
      }
    }

    const colorInfo = profile.color_dna;
    const typo = profile.typography_dna;
    const chartGuide = profile.chart_guidelines;

    let chartBlock = '';
    if (chartGuide.color_sequence.length > 0) {
      chartBlock = `
DIAGRAMM-STIL (passend zum Corporate Design):
- Farbreihenfolge für Datenreihen: ${chartGuide.color_sequence.join(', ')}
- Schriftart: ${chartGuide.font_family}
- Stil: Modern, flach, ohne 3D-Effekte — passend zum Template-Design
- Nutze die chart-Folien aktiv für datengetriebene Aussagen!`;
    }

    return `
TEMPLATE-PROFIL "${profile.template_name || profile.template_id}" (Deep Learning):
${profile.description}

DESIGN-PERSÖNLICHKEIT:
${profile.design_personality || 'Professionelles Corporate Design'}

VERFÜGBARE LAYOUT-TYPEN: ${profile.supported_layout_types.join(', ')}

LAYOUT-KATALOG MIT EINSCHRÄNKUNGEN:
${layoutLines.join('\n')}

VISUELLE DNA:
- Schrift Überschriften: ${typo.heading_font}
- Schrift Text: ${typo.body_font}
- Primärfarbe: ${colorInfo.primary}
- Akzentfarben: ${colorInfo.accent1}, ${colorInfo.accent2}, ${colorInfo.accent3}
- Hintergrund: ${colorInfo.background}
- Folienformat: ${profile.slide_width_cm} × ${profile.slide_height_cm} cm
${chartBlock}

DESIGN-RICHTLINIEN:
${profile.guidelines}

REGELN FÜR TEXTLÄNGE:
- Überschreite NIEMALS die angegebenen maximalen Bullet-Anzahlen und Zeichenlimits.
- Wenn du mehr Inhalte hast als auf eine Folie passen, teile sie auf mehrere Folien auf.
  Verwende dafür den gleichen Layout-Typ und nummeriere: "Thema (1/2)", "Thema (2/2)".
- Bei two_column: Beide Spalten haben jeweils das gleiche Limit.
- Bei image: Der Textbereich ist deutlich kleiner — kürze radikal.
- Titel sollten einzeilig und unter dem Zeichenlimit bleiben.

STRATEGISCHE FOLIENGESTALTUNG:
- Folientitel als prägnante Aussagen formulieren: "Umsatz um 15% gesteigert" statt "Umsatz".
- Eine Kernaussage pro Folie — lieber eine Folie mehr als eine überladene.
- Alle Details, Hintergrundinformationen und Quellenangaben in Sprechernotizen (<!-- notes: -->).
- Nutze two_column für Gegenüberstellungen (Ist/Soll, Vor/Nach, Wir/Wettbewerb).
- Nutze section-Folien als Kapitelüberschriften für den narrativen roten Faden.
- Nutze chart-Folien für datengetriebene Aussagen mit konkreten Zahlen.
- Passe den Tonfall dem Corporate Design an: ${profile.design_personality ? profile.design_personality.split('.')[0] : 'professionell und modern'}.
`;
  }

  private formatConstraints(m: { max_bullets: number; max_chars_per_bullet: number; title_max_chars: number }): string {
    const constraints: string[] = [];
    if (m.max_bullets > 0) constraints.push(`max ${m.max_bullets} Bullets`);
    if (m.max_chars_per_bullet > 0) constraints.push(`max ${m.max_chars_per_bullet} Zeichen/Zeile`);
    if (m.title_max_chars > 0) constraints.push(`Titel max ${m.title_max_chars} Zeichen`);
    return constraints.length > 0 ? ` | Limits: ${constraints.join(', ')}` : '';
  }

  private buildAnalysisPromptBlock(
    analysis: TemplateAnalysis,
    theme: TemplateTheme | null,
  ): string {
    const mappings = analysis.layout_mappings
      .filter((m) => m.mapped_type !== 'unused')
      .map((m) => {
        const constraints = [];
        if (m.max_bullets > 0) constraints.push(`max ${m.max_bullets} Bullets`);
        if (m.max_chars_per_bullet > 0) constraints.push(`max ${m.max_chars_per_bullet} Zeichen/Zeile`);
        if (m.title_max_chars > 0) constraints.push(`Titel max ${m.title_max_chars} Zeichen`);
        const constraintStr = constraints.length > 0 ? ` | Limits: ${constraints.join(', ')}` : '';
        return `- ${m.mapped_type} ("${m.layout_name}"): ${m.description}${constraintStr}\n  → ${m.recommended_usage}`;
      })
      .join('\n');

    const themeInfo = theme
      ? `\nDas Design verwendet:
- Schriftart Überschriften: ${theme.heading_font}
- Schriftart Text: ${theme.body_font}
- Primärfarbe: ${theme.accent_color}
- Hintergrund: ${theme.bg_color}
- Folienformat: ${theme.slide_width_cm} × ${theme.slide_height_cm} cm`
      : '';

    return `
TEMPLATE-ANALYSE (KI-generiert):
${analysis.description}

VERFÜGBARE LAYOUTS MIT EINSCHRÄNKUNGEN:
${mappings}
${themeInfo}

DESIGN-RICHTLINIEN:
${analysis.guidelines}

REGELN FÜR TEXTLÄNGE:
- Überschreite NIEMALS die angegebenen maximalen Bullet-Anzahlen und Zeichenlimits.
- Wenn du mehr Inhalte hast als auf eine Folie passen, teile sie auf mehrere Folien auf.
  Verwende dafür den gleichen Layout-Typ und nummeriere: "Thema (1/2)", "Thema (2/2)".
- Bei two_column: Beide Spalten haben jeweils das gleiche Limit.
- Bei image: Der Textbereich ist deutlich kleiner — kürze radikal.
- Titel sollten einzeilig und unter dem Zeichenlimit bleiben.

STRATEGISCHE FOLIENGESTALTUNG:
- Folientitel als prägnante Aussagen formulieren: "Umsatz um 15% gesteigert" statt "Umsatz".
- Eine Kernaussage pro Folie — lieber eine Folie mehr als eine überladene.
- Alle Details, Hintergrundinformationen und Quellenangaben in Sprechernotizen (<!-- notes: -->).
- Nutze two_column für Gegenüberstellungen (Ist/Soll, Vor/Nach, Wir/Wettbewerb).
- Nutze section-Folien als Kapitelüberschriften für den narrativen roten Faden.
- Passe den Tonfall dem Corporate Design des Folienmasters an.
`;
  }

  private buildThemeFallbackBlock(theme: TemplateTheme): string {
    const layoutInfo = theme.layouts
      .map((name, i) => `  ${i}: "${name}"`)
      .join('\n');

    const constraintsBlock = this.buildConstraintsBlock(theme.layout_constraints);

    return `
FOLIENMASTER-INFORMATIONEN:
Der gewählte Folienmaster "${theme.template_name || theme.template_id}" hat folgende Layouts:
${layoutInfo}

Das Design verwendet:
- Schriftart Überschriften: ${theme.heading_font}
- Schriftart Text: ${theme.body_font}
- Primärfarbe: ${theme.accent_color}
- Hintergrund: ${theme.bg_color}
- Folienformat: ${theme.slide_width_cm} × ${theme.slide_height_cm} cm

DESIGN-EINSCHRÄNKUNGEN (WICHTIG — unbedingt einhalten!):
${constraintsBlock}

REGELN FÜR TEXTLÄNGE:
- Überschreite NIEMALS die angegebene maximale Bullet-Anzahl pro Folie.
- Halte Bullet Points kürzer als die angegebene max. Zeichenzahl pro Zeile.
- Wenn du mehr Inhalte hast als auf eine Folie passen, teile sie auf mehrere Folien auf.
  Verwende dafür den gleichen Layout-Typ und nummeriere: "Thema (1/2)", "Thema (2/2)".
- Bei two_column: Beide Spalten haben jeweils das gleiche Limit.
- Bei image: Der Textbereich ist deutlich kleiner — kürze radikal.
- Titel sollten einzeilig und unter dem Zeichenlimit bleiben.

STRATEGISCHE FOLIENGESTALTUNG:
- Folientitel als prägnante Aussagen formulieren: "Umsatz um 15% gesteigert" statt "Umsatz".
- Eine Kernaussage pro Folie — lieber eine Folie mehr als eine überladene.
- Alle Details, Hintergrundinformationen und Quellenangaben in Sprechernotizen (<!-- notes: -->).
- Nutze two_column für Gegenüberstellungen (Ist/Soll, Vor/Nach, Wir/Wettbewerb).
- Nutze section-Folien als Kapitelüberschriften für den narrativen roten Faden.
- Passe den Tonfall dem Corporate Design des Folienmasters an.
`;
  }

  private buildConstraintsBlock(constraints: LayoutConstraint[]): string {
    // Pick the primary (highest-scoring / first) constraint per layout type
    const primaryByType = new Map<string, LayoutConstraint>();
    for (const c of constraints) {
      if (!primaryByType.has(c.layout_type)) {
        primaryByType.set(c.layout_type, c);
      }
    }

    const lines: string[] = [];
    for (const [type, c] of primaryByType) {
      if (type === 'title' || type === 'section') {
        lines.push(`- ${type}: Titel max ${c.title_max_chars || 50} Zeichen`);
      } else if (type === 'content') {
        lines.push(
          `- ${type}: max ${c.max_bullets} Bullet Points, max ${c.max_chars_per_bullet} Zeichen/Zeile, Titel max ${c.title_max_chars} Zeichen`,
        );
      } else if (type === 'two_column') {
        lines.push(
          `- ${type}: max ${c.max_bullets} Bullets pro Spalte, max ${c.max_chars_per_bullet} Zeichen/Zeile, Titel max ${c.title_max_chars} Zeichen`,
        );
      } else if (type === 'image') {
        lines.push(
          `- ${type}: max ${c.max_bullets} Bullet Points, max ${c.max_chars_per_bullet} Zeichen/Zeile (Textbereich neben Bild ist klein!)`,
        );
      } else if (type === 'closing') {
        lines.push(`- ${type}: max ${c.max_bullets} Zeilen, max ${c.max_chars_per_bullet} Zeichen/Zeile`);
      }
    }
    return lines.join('\n');
  }

  // ── Readability validation & auto-split ────────────────────────────────

  /** Build a unified constraint map from AI analysis (preferred) or theme extraction (fallback). */
  private buildConstraintMapFromAll(
    theme: TemplateTheme | null,
    aiAnalysis: TemplateAnalysis | null,
  ): Map<string, LayoutConstraint> {
    const map = new Map<string, LayoutConstraint>();

    // Prefer AI analysis
    if (aiAnalysis?.layout_mappings?.length) {
      for (const m of aiAnalysis.layout_mappings) {
        if (m.mapped_type === 'unused' || map.has(m.mapped_type)) continue;
        map.set(m.mapped_type, {
          layout_name: m.layout_name,
          layout_type: m.mapped_type,
          placeholders: [],
          max_bullets: m.max_bullets,
          max_chars_per_bullet: m.max_chars_per_bullet,
          title_max_chars: m.title_max_chars,
        });
      }
    }

    // Fill gaps from theme constraints
    if (theme?.layout_constraints?.length) {
      for (const c of theme.layout_constraints) {
        if (!map.has(c.layout_type)) {
          map.set(c.layout_type, c);
        }
      }
    }

    return map;
  }

  private async validateAndFix(
    client: OpenAI,
    markdown: string,
    slides: SlideDto[],
    constraintMap: Map<string, LayoutConstraint>,
  ): Promise<{ markdown: string; slides: SlideDto[] }> {
    const issues = this.detectOverflow(slides, constraintMap);

    if (issues.length === 0) {
      this.logger.log('Readability check passed — no overflow detected');
      return { markdown, slides };
    }

    this.logger.warn(`Readability issues found on ${issues.length} slide(s), requesting Gemini fix`);

    const fixPrompt = this.buildFixPrompt(markdown, issues, constraintMap);

    try {
      const response = await client.chat.completions.create({
        model: this.settings.getModel(),
        messages: [
          { role: 'system', content: fixPrompt },
          { role: 'user', content: markdown },
        ],
        temperature: 0.3,
        max_tokens: 4096,
      });

      const fixedMarkdown = response.choices[0]?.message?.content?.trim() ?? '';
      if (!fixedMarkdown) {
        return { markdown, slides };
      }

      const fixedSlides = this.parseMarkdown(fixedMarkdown);
      // Only accept the fix if it actually produced slides
      if (fixedSlides.length > 0) {
        this.logger.log(
          `Readability fix applied: ${slides.length} → ${fixedSlides.length} slides`,
        );
        return { markdown: fixedMarkdown, slides: fixedSlides };
      }
    } catch (err) {
      this.logger.warn(`Readability fix LLM call failed: ${err}`);
    }

    return { markdown, slides };
  }

  private detectOverflow(
    slides: SlideDto[],
    constraintMap: Map<string, LayoutConstraint>,
  ): Array<{ slideIndex: number; slide: SlideDto; reason: string }> {
    const issues: Array<{ slideIndex: number; slide: SlideDto; reason: string }> = [];

    for (let i = 0; i < slides.length; i++) {
      const slide = slides[i];
      const constraint = constraintMap.get(slide.layout);
      if (!constraint) continue;

      const reasons: string[] = [];

      // Check bullet count overflow
      if (constraint.max_bullets > 0 && slide.bullets.length > constraint.max_bullets) {
        reasons.push(
          `${slide.bullets.length} Bullets (max ${constraint.max_bullets})`,
        );
      }

      // Check bullet text length
      if (constraint.max_chars_per_bullet > 0) {
        for (const bullet of slide.bullets) {
          if (bullet.length > constraint.max_chars_per_bullet) {
            reasons.push(
              `Bullet "${bullet.slice(0, 30)}..." hat ${bullet.length} Zeichen (max ${constraint.max_chars_per_bullet})`,
            );
            break; // one example is enough
          }
        }
      }

      // Check title length
      if (constraint.title_max_chars > 0 && slide.title.length > constraint.title_max_chars) {
        reasons.push(
          `Titel "${slide.title.slice(0, 30)}..." hat ${slide.title.length} Zeichen (max ${constraint.title_max_chars})`,
        );
      }

      if (reasons.length > 0) {
        issues.push({ slideIndex: i + 1, slide, reason: reasons.join('; ') });
      }
    }

    return issues;
  }

  private buildFixPrompt(
    _markdown: string,
    issues: Array<{ slideIndex: number; slide: SlideDto; reason: string }>,
    constraintMap: Map<string, LayoutConstraint>,
  ): string {
    const issueList = issues
      .map((i) => `- Folie ${i.slideIndex} (${i.slide.layout}): ${i.reason}`)
      .join('\n');

    const constraintList = [...constraintMap.entries()]
      .map(([type, c]) => {
        if (type === 'content') {
          return `- ${type}: max ${c.max_bullets} Bullets, max ${c.max_chars_per_bullet} Zeichen/Zeile`;
        }
        if (type === 'two_column') {
          return `- ${type}: max ${c.max_bullets} Bullets/Spalte, max ${c.max_chars_per_bullet} Zeichen/Zeile`;
        }
        if (type === 'image') {
          return `- ${type}: max ${c.max_bullets} Bullets, max ${c.max_chars_per_bullet} Zeichen/Zeile`;
        }
        return `- ${type}: max ${c.title_max_chars} Zeichen Titel`;
      })
      .join('\n');

    return `Du bist "Clarity Engine" — ein Experte für Präsentationsdesign. Die folgende Markdown-Präsentation \
hat Lesbarkeitsprobleme, weil Texte die Platzhalter-Grenzen des Folienmasters überschreiten.

PROBLEME:
${issueList}

DESIGN-LIMITS:
${constraintList}

REGELN:
1. Gib die GESAMTE korrigierte Präsentation im gleichen Markdown-Format zurück.
2. Kürze zu lange Bullet Points auf die Kernaussage. Details in <!-- notes: --> verschieben.
3. Teile übervolle Folien in mehrere Folien auf: gleicher Layout-Typ, Titel mit "(1/2)", "(2/2)".
4. Folientitel als prägnante Aussagen formulieren, nicht als Schlagworte.
5. Behalte alle <!-- layout: TYPE --> und <!-- notes: --> Kommentare bei.
6. Ändere NICHT Folien, die keine Probleme haben.
7. Antworte NUR mit dem korrigierten Markdown.`;
  }

  parseMarkdown(markdown: string): SlideDto[] {
    const rawSlides = markdown
      .split(/^\s*---\s*$/m)
      .filter((s) => s.trim());

    return rawSlides.map((raw) => this.parseSlide(raw.trim())).filter(Boolean) as SlideDto[];
  }

  private parseSlide(raw: string): SlideDto | null {
    if (!raw) return null;

    const layoutMatch = raw.match(/<!--\s*layout:\s*(\w+)\s*-->/);
    let layout = layoutMatch?.[1] ?? 'content';
    if (!VALID_LAYOUTS.has(layout)) layout = 'content';

    const notesMatch = raw.match(/<!--\s*notes:\s*([\s\S]*?)\s*-->/);
    const notes = notesMatch?.[1]?.trim() ?? '';

    const clean = raw
      .replace(/<!--\s*layout:\s*\w+\s*-->/g, '')
      .replace(/<!--\s*notes:[\s\S]*?-->/g, '')
      .trim();

    const h1 = clean.match(/^#\s+(.+)$/m);
    const h2 = clean.match(/^##\s+(.+)$/m);
    const bullets = [...clean.matchAll(/^[-*]\s+(.+)$/gm)].map((m) => m[1]);

    let leftColumn = '';
    let rightColumn = '';
    if (layout === 'two_column') {
      [leftColumn, rightColumn] = this.parseTwoColumns(clean);
    }

    // Extract image description from ![desc](url)
    const imgMatch = clean.match(/!\[([^\]]+)\]\([^)]*\)/);
    const imageDescription = imgMatch?.[1]?.trim() ?? '';

    return {
      layout,
      title: h1?.[1]?.trim() ?? '',
      subtitle: h2?.[1]?.trim() ?? '',
      body: '',
      bullets,
      notes,
      imageDescription,
      leftColumn,
      rightColumn,
    };
  }

  private parseTwoColumns(text: string): [string, string] {
    // Find all ## headings and their positions
    const headingPattern = /^##\s+.+$/gm;
    const headings: Array<{ index: number; length: number }> = [];
    let match: RegExpExecArray | null;
    while ((match = headingPattern.exec(text)) !== null) {
      headings.push({ index: match.index, length: match[0].length });
    }

    // Need exactly 2 ## headings for left/right columns
    if (headings.length < 2) return ['', ''];

    const extractBullets = (t: string): string =>
      [...t.matchAll(/^[-*]\s+(.+)$/gm)]
        .map((m) => `- ${m[1]}`)
        .join('\n');

    const leftContent = text.slice(
      headings[0].index + headings[0].length,
      headings[1].index,
    );
    const rightContent = text.slice(headings[1].index + headings[1].length);

    return [extractBullets(leftContent), extractBullets(rightContent)];
  }
}
