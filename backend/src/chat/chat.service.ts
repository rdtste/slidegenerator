import { Injectable, Logger } from '@nestjs/common';
import OpenAI from 'openai';
import { SettingsService } from '../settings/settings.service';
import { TemplatesService, LayoutConstraint, TemplateTheme } from '../templates/templates.service';
import { TemplateAnalysisService, TemplateAnalysis } from '../templates/template-analysis.service';
import { ChatResponseDto, SlideDto } from './chat.dto';

const BASE_SYSTEM_PROMPT = `Du bist ein Experte für Präsentationsdesign. Du generierst strukturierte \
Markdown-Präsentationen im folgenden Format.

REGELN:
- Jede Folie beginnt mit "---" als Trenner (außer die erste Folie).
- Die erste Folie ist IMMER eine Titelfolie mit <!-- layout: title -->.
- Jede Folie hat einen <!-- layout: TYPE --> Kommentar. Erlaubte Typen:
  title, section, content, two_column, image, closing
- Überschriften: # für Folientitel, ## für Untertitel.
- Aufzählungen mit "- " für Bullet Points.
- Presenter Notes nach "<!-- notes:" bis "-->" (optional).
- Halte Folien kurz: max 5-6 Bullet Points pro Folie.
- Verwende klare, prägnante Formulierungen.
- Antworte NUR mit dem Markdown, keine Erklärungen.

BEISPIEL:
<!-- layout: title -->
# Unternehmensstrategie 2026
## Q1 Update für das Management

<!-- notes: Begrüßung und Agenda vorstellen -->

---

<!-- layout: section -->
# Agenda

---

<!-- layout: content -->
# Umsatzentwicklung
- Umsatz Q1: +15% YoY
- Haupttreiber: Digitale Produkte
- EBITDA-Marge: 23,4%

<!-- notes: Details zur Umsatzentwicklung erläutern -->

---

<!-- layout: two_column -->
# Marktvergleich
## Links
- Marktanteil: 34%
- Wachstum: +8%
## Rechts
- Wettbewerber A: 28%
- Wettbewerber B: 19%

---

<!-- layout: closing -->
# Vielen Dank
## Fragen?
`;

const VALID_LAYOUTS = new Set(['title', 'section', 'content', 'two_column', 'image', 'closing']);

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

  async generate(
    prompt: string,
    documentTexts: string[] = [],
    templateId?: string,
  ): Promise<ChatResponseDto> {
    this.logger.log(`Generating slides for: ${prompt.slice(0, 80)}...`);

    let userContent = prompt;
    if (documentTexts.length > 0) {
      userContent = `${prompt}\n\nDie folgenden Dokumente enthalten die Informationen, auf deren Basis die Präsentation erstellt werden soll:\n\n${documentTexts.join('\n\n')}`;
    }

    const theme = templateId ? await this.templates.getTheme(templateId) : null;
    const aiAnalysis = templateId ? await this.analysis.getAnalysis(templateId) : null;
    const systemPrompt = await this.buildSystemPrompt(templateId);

    const client = await this.createClient();
    const response = await client.chat.completions.create({
      model: this.settings.getModel(),
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userContent },
      ],
      temperature: 0.7,
      max_tokens: 4096,
    });

    let markdown = response.choices[0]?.message?.content?.trim() ?? '';
    let slides = this.parseMarkdown(markdown);

    // Post-generation: validate readability and auto-fix
    const constraintMap = this.buildConstraintMapFromAll(theme, aiAnalysis);
    if (constraintMap.size > 0) {
      const validated = await this.validateAndFix(client, markdown, slides, constraintMap);
      markdown = validated.markdown;
      slides = validated.slides;
    }

    this.logger.log(`Generated ${slides.length} slides`);
    return { markdown, slides };
  }

  private async buildSystemPrompt(templateId?: string): Promise<string> {
    if (!templateId || templateId === 'default') {
      return BASE_SYSTEM_PROMPT;
    }

    // Try AI analysis first (rich, template-specific)
    const aiAnalysis = await this.analysis.getAnalysis(templateId);
    const theme = await this.templates.getTheme(templateId);

    if (!theme && !aiAnalysis) {
      return BASE_SYSTEM_PROMPT;
    }

    // Build template design info
    let templateBlock = '';

    if (aiAnalysis) {
      templateBlock = this.buildAnalysisPromptBlock(aiAnalysis, theme);
    } else if (theme) {
      // Fallback: programmatic constraints from theme extraction
      templateBlock = this.buildThemeFallbackBlock(theme);
    }

    return `${BASE_SYSTEM_PROMPT}\n${templateBlock}`;
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

Berücksichtige den Stil des Folienmasters bei der Texterstellung:
- Passe den Tonfall dem Corporate Design an.
- Nutze die verfügbaren Layout-Typen optimal.
- Halte Texte kurz und professionell.
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

Berücksichtige den Stil des Folienmasters bei der Texterstellung:
- Passe den Tonfall dem Corporate Design an.
- Nutze die verfügbaren Layout-Typen optimal.
- Halte Texte kurz und professionell.
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

    return `Du bist ein Präsentations-Editor. Die folgende Markdown-Präsentation hat Lesbarkeitsprobleme,
weil Texte die Platzhalter-Grenzen des Folienmasters überschreiten.

PROBLEME:
${issueList}

DESIGN-LIMITS:
${constraintList}

REGELN:
1. Gib die GESAMTE korrigierte Präsentation im gleichen Markdown-Format zurück.
2. Kürze zu lange Bullet Points oder teile übervolle Folien in mehrere Folien auf.
3. Bei Aufteilung: gleicher Layout-Typ, Titel mit "(1/2)", "(2/2)" etc.
4. Behalte alle <!-- layout: TYPE --> und <!-- notes: --> Kommentare bei.
5. Ändere NICHT Folien, die keine Probleme haben.
6. Antworte NUR mit dem korrigierten Markdown.`;
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

    return {
      layout,
      title: h1?.[1]?.trim() ?? '',
      subtitle: h2?.[1]?.trim() ?? '',
      body: '',
      bullets,
      notes,
      imageDescription: '',
      leftColumn,
      rightColumn,
    };
  }

  private parseTwoColumns(text: string): [string, string] {
    const lower = text.toLowerCase();
    const leftMarkers = ['## links', '## left'];
    const rightMarkers = ['## rechts', '## right'];

    let leftStart = -1;
    let rightStart = -1;

    for (const m of leftMarkers) {
      const idx = lower.indexOf(m);
      if (idx >= 0) { leftStart = idx + m.length; break; }
    }
    for (const m of rightMarkers) {
      const idx = lower.indexOf(m);
      if (idx >= 0) { rightStart = idx + m.length; break; }
    }

    if (leftStart < 0 && rightStart < 0) return ['', ''];

    const extractBullets = (t: string): string =>
      [...t.matchAll(/^[-*]\s+(.+)$/gm)]
        .map((m) => `- ${m[1]}`)
        .join('\n');

    if (leftStart >= 0 && rightStart >= 0) {
      if (leftStart < rightStart) {
        return [
          extractBullets(text.slice(leftStart, lower.indexOf('## r', leftStart))),
          extractBullets(text.slice(rightStart)),
        ];
      }
      return [
        extractBullets(text.slice(leftStart)),
        extractBullets(text.slice(rightStart, lower.indexOf('## l', rightStart))),
      ];
    }

    return leftStart >= 0
      ? [extractBullets(text.slice(leftStart)), '']
      : ['', extractBullets(text.slice(rightStart))];
  }
}
