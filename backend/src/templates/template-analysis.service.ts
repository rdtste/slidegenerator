import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { SettingsService } from '../settings/settings.service';
import OpenAI from 'openai';
import * as fs from 'fs';
import * as path from 'path';

// ── Interfaces ──────────────────────────────────────────────────

export interface LayoutMapping {
  layout_index: number;
  layout_name: string;
  mapped_type: string;
  description: string;
  recommended_usage: string;
  max_bullets: number;
  max_chars_per_bullet: number;
  title_max_chars: number;
}

export interface TemplateAnalysis {
  template_id: string;
  description: string;
  layout_mappings: LayoutMapping[];
  guidelines: string;
  analyzed_at: string;
}

/** Enriched profile produced by the deep "learn" process. */
export interface TemplateProfile {
  template_id: string;
  template_name: string;
  description: string;
  design_personality: string;
  slide_width_cm: number;
  slide_height_cm: number;
  color_dna: {
    primary: string;
    accent1: string;
    accent2: string;
    accent3: string;
    accent4: string;
    accent5: string;
    accent6: string;
    background: string;
    text: string;
    heading: string;
    chart_colors: string[];
  };
  typography_dna: {
    heading_font: string;
    body_font: string;
    heading_sizes_pt: number[];
    body_sizes_pt: number[];
  };
  layout_catalog: LayoutMapping[];
  chart_guidelines: {
    color_sequence: string[];
    font_family: string;
    style: string;
    available_chart_layouts: number[];
  };
  image_guidelines: {
    available_image_layouts: number[];
    primary_aspect_ratio: string;
    style_keywords: string[];
    accent_color: string;
  };
  supported_layout_types: string[];
  guidelines: string;
  learned_at: string;
}

// ── Extended AI prompt for deep template learning ───────────────

const LEARN_PROMPT = `Du bist ein PowerPoint-Template-Experte mit tiefem Verständnis für Corporate Design.
Du analysierst Folienmastervorlagen und erstellst ein umfassendes Profil für die KI-gesteuerte Folienerstellung.

EINGABE: Du erhältst:
1. Das visuelle Profil des Templates (Farben, Schriften, Layout-Katalog mit Platzhaltertypen)
2. Besondere Fähigkeiten des Templates (PICTURE/CHART/TABLE-Platzhalter)

DEINE AUFGABE: Klassifiziere ALLE nutzbaren Layouts in einen der folgenden Typen:
- title: Titelfolie (Präsentationstitel + Untertitel)
- section: Kapitelüberschrift / Abschnittstrenner
- content: Inhalt mit Bullet Points (TITLE + OBJECT/BODY)
- two_column: Zwei-Spalten-Vergleich (2× OBJECT)
- image: Bild + Text (PICTURE-Platzhalter)
- chart: Diagramm-Folie (CHART-Platzhalter oder großer PICTURE für generiertes Diagramm)
- closing: Abschlussfolie (Danke, Kontakt)

REGELN:
- Klassifiziere ALLE Layouts mit mindestens einem relevanten Platzhalter (nicht nur 6!)
- Mehrere Layouts können denselben Typ haben (z.B. 3× content mit unterschiedlicher Ästhetik)
- Layouts mit nur meta-Platzhaltern (SLIDE_NUMBER, FOOTER, DATE) werden übersprungen
- Ein Layout mit PICTURE-Platzhalter aber OHNE CHART kann als "chart" dienen (Diagramm als Bild)
- Beschreibe jedes Layout so, dass die KI versteht WANN es am besten passt
- "design_personality" soll den Corporate-Design-Stil in 2-3 Sätzen beschreiben
- "guidelines" enthält prägnante Gestaltungshinweise passend zum Design-Stil

AUSGABE: NUR kompaktes JSON (KEINE Codeblöcke, KEINE Erklärungen):
{
  "description": "Kurze Template-Beschreibung",
  "design_personality": "Beschreibung des visuellen Stils und der Designsprache",
  "layout_mappings": [
    {
      "layout_index": 0,
      "layout_name": "Name",
      "mapped_type": "title",
      "description": "Wofür dieses Layout am besten geeignet ist",
      "recommended_usage": "Konkrete Einsatzempfehlung"
    }
  ],
  "guidelines": "Gestaltungshinweise für Texte und Inhalte"
}

WICHTIG:
- KEINE Kapazitätsangaben (max_bullets etc.) — werden automatisch berechnet
- Beschreibungen max 20 Wörter
- Jedes Layout mit nutzbaren Platzhaltern MUSS klassifiziert werden
- Bevorzuge spezifische Empfehlungen ("Ideal für Q3-Ergebnisse mit Balkendiagramm")
  statt generischer ("Für Diagramme")`;

@Injectable()
export class TemplateAnalysisService {
  private readonly logger = new Logger(TemplateAnalysisService.name);
  private readonly templatesDir: string;
  private readonly pptxServiceUrl: string;

  constructor(
    private readonly config: ConfigService,
    private readonly settings: SettingsService,
  ) {
    this.templatesDir = this.config.get<string>(
      'TEMPLATES_DIR',
      path.resolve(__dirname, '../../templates'),
    );
    this.pptxServiceUrl = this.config.get<string>(
      'PPTX_SERVICE_URL',
      'http://localhost:8000',
    );
  }

  private analysisPath(templateId: string): string {
    return path.join(this.templatesDir, `${templateId}.analysis.json`);
  }

  private profilePath(templateId: string): string {
    return path.join(this.templatesDir, `${templateId}.profile.json`);
  }

  // ── Read ──────────────────────────────────────────────────────

  async getAnalysis(templateId: string): Promise<TemplateAnalysis | null> {
    if (!templateId || templateId === 'default') return null;

    // Prefer profile (new format), fall back to analysis (legacy)
    const profile = this.getProfile(templateId);
    if (profile) {
      return {
        template_id: profile.template_id,
        description: profile.description,
        layout_mappings: profile.layout_catalog,
        guidelines: profile.guidelines,
        analyzed_at: profile.learned_at,
      };
    }

    const filePath = this.analysisPath(templateId);
    if (!fs.existsSync(filePath)) return null;

    try {
      const raw = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(raw) as TemplateAnalysis;
    } catch (err) {
      this.logger.warn(`Failed to read analysis for ${templateId}: ${err}`);
      return null;
    }
  }

  getProfile(templateId: string): TemplateProfile | null {
    if (!templateId || templateId === 'default') return null;

    const filePath = this.profilePath(templateId);
    if (!fs.existsSync(filePath)) return null;

    try {
      const raw = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(raw) as TemplateProfile;
    } catch (err) {
      this.logger.warn(`Failed to read profile for ${templateId}: ${err}`);
      return null;
    }
  }

  // ── Learn (deep analysis) ────────────────────────────────────

  async learnTemplate(templateId: string): Promise<TemplateProfile | null> {
    this.logger.log(`Starting deep learning for template: ${templateId}`);

    // 1. Fetch deep profile from pptx-service
    const rawProfile = await this.fetchProfile(templateId);
    if (!rawProfile) {
      this.logger.warn(`Could not fetch profile for ${templateId}, falling back to legacy`);
      const legacy = await this.analyzeTemplate(templateId);
      return legacy ? this.legacyToProfile(legacy) : null;
    }

    // 2. Fetch raw structure for constraint computation
    const structure = await this.fetchStructure(templateId);

    // 3. Send to AI for semantic classification
    const classified = await this.classifyWithProfile(templateId, rawProfile);
    if (!classified) {
      this.logger.warn(`AI classification failed for ${templateId}`);
      return null;
    }

    // 4. Merge AI classification with extracted profile data
    const profile = this.mergeProfile(templateId, rawProfile, classified, structure);

    // 5. Store as .profile.json
    const filePath = this.profilePath(templateId);
    fs.writeFileSync(filePath, JSON.stringify(profile, null, 2), 'utf-8');
    this.logger.log(
      `Profile saved for ${templateId}: ${profile.layout_catalog.length} layouts, ` +
      `${profile.supported_layout_types.length} types, ` +
      `chart_colors=${profile.color_dna.chart_colors.length}`,
    );

    // Also write legacy .analysis.json for backward compatibility
    const legacyAnalysis: TemplateAnalysis = {
      template_id: profile.template_id,
      description: profile.description,
      layout_mappings: profile.layout_catalog,
      guidelines: profile.guidelines,
      analyzed_at: profile.learned_at,
    };
    fs.writeFileSync(this.analysisPath(templateId), JSON.stringify(legacyAnalysis, null, 2), 'utf-8');

    return profile;
  }

  /** Legacy analyze — kept for backward compat, but learnTemplate is preferred. */
  async analyzeTemplate(templateId: string): Promise<TemplateAnalysis | null> {
    this.logger.log(`Starting AI analysis for template: ${templateId}`);

    const structure = await this.fetchStructure(templateId);
    if (!structure) {
      this.logger.warn(`Could not fetch structure for ${templateId}`);
      return null;
    }

    const analysis = await this.classifyWithAi(templateId, structure);
    if (!analysis) {
      this.logger.warn(`AI classification failed for ${templateId}`);
      return null;
    }

    const filePath = this.analysisPath(templateId);
    fs.writeFileSync(filePath, JSON.stringify(analysis, null, 2), 'utf-8');
    this.logger.log(
      `Analysis saved for ${templateId}: ${analysis.layout_mappings.length} mappings`,
    );

    return analysis;
  }

  deleteAnalysis(templateId: string): void {
    for (const p of [this.analysisPath(templateId), this.profilePath(templateId)]) {
      if (fs.existsSync(p)) {
        fs.unlinkSync(p);
        this.logger.log(`Deleted: ${path.basename(p)}`);
      }
    }
  }

  // ── Fetch from pptx-service ──────────────────────────────────

  private async fetchProfile(templateId: string): Promise<Record<string, unknown> | null> {
    try {
      const response = await fetch(
        `${this.pptxServiceUrl}/api/v1/templates/${encodeURIComponent(templateId)}/learn`,
        { method: 'POST' },
      );
      if (!response.ok) return null;
      return await response.json() as Record<string, unknown>;
    } catch (err) {
      this.logger.warn(`Failed to fetch profile for ${templateId}: ${err}`);
      return null;
    }
  }

  private async fetchStructure(templateId: string): Promise<Record<string, unknown> | null> {
    try {
      const response = await fetch(
        `${this.pptxServiceUrl}/api/v1/templates/${encodeURIComponent(templateId)}/structure`,
      );
      if (!response.ok) return null;
      return await response.json() as Record<string, unknown>;
    } catch (err) {
      this.logger.warn(`Failed to fetch structure for ${templateId}: ${err}`);
      return null;
    }
  }

  // ── AI classification with rich profile ──────────────────────

  private async classifyWithProfile(
    templateId: string,
    rawProfile: Record<string, unknown>,
  ): Promise<{
    description: string;
    design_personality: string;
    layout_mappings: Array<{
      layout_index: number;
      layout_name: string;
      mapped_type: string;
      description: string;
      recommended_usage: string;
    }>;
    guidelines: string;
  } | null> {
    try {
      const token = await this.settings.getAccessToken();
      const client = new OpenAI({
        baseURL: this.settings.getBaseURL(),
        apiKey: token,
      });

      // Compact the profile for the prompt — include layout details + capabilities
      const catalog = (rawProfile['layout_catalog'] as Array<Record<string, unknown>>) ?? [];
      const compactLayouts = catalog
        .filter((ld) => {
          const phTypes = (ld['placeholder_types'] as string[]) ?? [];
          return phTypes.some((t) => !['SLIDE_NUMBER', 'FOOTER', 'DATE'].includes(t));
        })
        .map((ld) => ({
          idx: ld['index'],
          name: ld['name'],
          types: ld['placeholder_types'],
          pic: ld['has_picture'] ? `${ld['picture_width_cm']}×${ld['picture_height_cm']}cm ${ld['picture_aspect_ratio']}` : undefined,
          chart: ld['has_chart'] || undefined,
          table: ld['has_table'] || undefined,
          content: ld['content_width_cm'] ? `${ld['content_width_cm']}×${ld['content_height_cm']}cm` : undefined,
        }));

      const colorDna = rawProfile['color_dna'] as Record<string, unknown> | undefined;
      const typoDna = rawProfile['typography_dna'] as Record<string, unknown> | undefined;

      const compactProfile = {
        id: templateId,
        name: rawProfile['template_name'],
        slide: `${rawProfile['slide_width_cm']}×${rawProfile['slide_height_cm']}cm`,
        colors: colorDna ? {
          accent1: colorDna['accent1'],
          accent2: colorDna['accent2'],
          bg: colorDna['background'],
          text: colorDna['text'],
        } : undefined,
        fonts: typoDna ? {
          heading: typoDna['heading_font'],
          body: typoDna['body_font'],
        } : undefined,
        supported: rawProfile['supported_layout_types'],
        layouts: compactLayouts,
      };

      this.logger.log(
        `Sending ${compactLayouts.length} layouts to AI for deep learning of ${templateId}`,
      );

      const response = await client.chat.completions.create({
        model: this.settings.getModel(),
        messages: [
          { role: 'system', content: LEARN_PROMPT },
          {
            role: 'user',
            content: `Template-Profil:\n${JSON.stringify(compactProfile)}`,
          },
        ],
        temperature: 0.2,
        max_tokens: 65536,
      });

      const finishReason = response.choices[0]?.finish_reason;
      this.logger.log(`AI learn response for ${templateId}, finish_reason=${finishReason}`);

      const raw = response.choices[0]?.message?.content?.trim() ?? '';
      if (!raw || raw.length < 50) {
        this.logger.warn(`AI returned insufficient content for ${templateId}`);
        return null;
      }

      this.logger.debug(`AI learn response (first 600 chars): ${raw.slice(0, 600)}`);

      let jsonStr = raw.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '');

      if (finishReason === 'length') {
        this.logger.warn(`Response truncated for ${templateId}, attempting JSON repair`);
        jsonStr = this.repairTruncatedJson(jsonStr);
      }

      return JSON.parse(jsonStr);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      this.logger.error(`AI learn classification error for ${templateId}: ${message}`);
      return null;
    }
  }

  // ── Merge AI classification with extracted profile ───────────

  private mergeProfile(
    templateId: string,
    rawProfile: Record<string, unknown>,
    classified: {
      description: string;
      design_personality: string;
      layout_mappings: Array<{
        layout_index: number;
        layout_name: string;
        mapped_type: string;
        description: string;
        recommended_usage: string;
      }>;
      guidelines: string;
    },
    structure: Record<string, unknown> | null,
  ): TemplateProfile {
    const colorDna = (rawProfile['color_dna'] ?? {}) as Record<string, unknown>;
    const typoDna = (rawProfile['typography_dna'] ?? {}) as Record<string, unknown>;
    const chartGuidelines = (rawProfile['chart_guidelines'] ?? {}) as Record<string, unknown>;
    const imageGuidelines = (rawProfile['image_guidelines'] ?? {}) as Record<string, unknown>;
    const catalog = (rawProfile['layout_catalog'] ?? []) as Array<Record<string, unknown>>;

    // Enrich AI mappings with computed constraints from structure data
    const enrichedMappings = classified.layout_mappings.map((m) => {
      const catalogEntry = catalog.find((c) => c['index'] === m.layout_index);
      return {
        layout_index: m.layout_index,
        layout_name: m.layout_name,
        mapped_type: m.mapped_type,
        description: m.description,
        recommended_usage: m.recommended_usage,
        max_bullets: (catalogEntry?.['max_bullets'] as number) ?? 0,
        max_chars_per_bullet: (catalogEntry?.['max_chars_per_bullet'] as number) ?? 0,
        title_max_chars: (catalogEntry?.['title_max_chars'] as number) ?? 0,
      };
    });

    // If structure data available, also compute constraints from raw placeholders
    if (structure) {
      const structureData = structure as {
        layouts: Array<{
          index: number;
          placeholders: Array<{
            type_id: number;
            width_cm: number;
            height_cm: number;
            font_sizes_pt: number[];
          }>;
        }>;
      };

      for (const mapping of enrichedMappings) {
        if (mapping.max_bullets === 0) {
          const computed = this.computeConstraints(mapping, structureData);
          mapping.max_bullets = computed.max_bullets;
          mapping.max_chars_per_bullet = computed.max_chars_per_bullet;
          mapping.title_max_chars = computed.title_max_chars;
        }
      }
    }

    return {
      template_id: templateId,
      template_name: (rawProfile['template_name'] as string) ?? '',
      description: classified.description,
      design_personality: classified.design_personality ?? '',
      slide_width_cm: (rawProfile['slide_width_cm'] as number) ?? 33.9,
      slide_height_cm: (rawProfile['slide_height_cm'] as number) ?? 19.1,
      color_dna: {
        primary: (colorDna['primary'] as string) ?? '#000000',
        accent1: (colorDna['accent1'] as string) ?? '#0969da',
        accent2: (colorDna['accent2'] as string) ?? '#22c55e',
        accent3: (colorDna['accent3'] as string) ?? '#f59e0b',
        accent4: (colorDna['accent4'] as string) ?? '#ef4444',
        accent5: (colorDna['accent5'] as string) ?? '#8b5cf6',
        accent6: (colorDna['accent6'] as string) ?? '#06b6d4',
        background: (colorDna['background'] as string) ?? '#FFFFFF',
        text: (colorDna['text'] as string) ?? '#000000',
        heading: (colorDna['heading'] as string) ?? '#000000',
        chart_colors: (colorDna['chart_colors'] as string[]) ?? [],
      },
      typography_dna: {
        heading_font: (typoDna['heading_font'] as string) ?? 'Calibri',
        body_font: (typoDna['body_font'] as string) ?? 'Calibri',
        heading_sizes_pt: (typoDna['heading_sizes_pt'] as number[]) ?? [],
        body_sizes_pt: (typoDna['body_sizes_pt'] as number[]) ?? [],
      },
      layout_catalog: enrichedMappings,
      chart_guidelines: {
        color_sequence: (chartGuidelines['color_sequence'] as string[]) ?? [],
        font_family: (chartGuidelines['font_family'] as string) ?? 'Calibri',
        style: (chartGuidelines['style'] as string) ?? 'modern_flat',
        available_chart_layouts: (chartGuidelines['available_chart_layouts'] as number[]) ?? [],
      },
      image_guidelines: {
        available_image_layouts: (imageGuidelines['available_image_layouts'] as number[]) ?? [],
        primary_aspect_ratio: (imageGuidelines['primary_aspect_ratio'] as string) ?? '16:9',
        style_keywords: (imageGuidelines['style_keywords'] as string[]) ?? [],
        accent_color: (imageGuidelines['accent_color'] as string) ?? '#0969da',
      },
      supported_layout_types: (rawProfile['supported_layout_types'] as string[]) ?? [],
      guidelines: classified.guidelines,
      learned_at: new Date().toISOString(),
    };
  }

  private legacyToProfile(analysis: TemplateAnalysis): TemplateProfile {
    return {
      template_id: analysis.template_id,
      template_name: '',
      description: analysis.description,
      design_personality: '',
      slide_width_cm: 33.9,
      slide_height_cm: 19.1,
      color_dna: {
        primary: '#000000', accent1: '#0969da', accent2: '#22c55e',
        accent3: '#f59e0b', accent4: '#ef4444', accent5: '#8b5cf6',
        accent6: '#06b6d4', background: '#FFFFFF', text: '#000000',
        heading: '#000000', chart_colors: [],
      },
      typography_dna: {
        heading_font: 'Calibri', body_font: 'Calibri',
        heading_sizes_pt: [], body_sizes_pt: [],
      },
      layout_catalog: analysis.layout_mappings,
      chart_guidelines: {
        color_sequence: [], font_family: 'Calibri',
        style: 'modern_flat', available_chart_layouts: [],
      },
      image_guidelines: {
        available_image_layouts: [], primary_aspect_ratio: '16:9',
        style_keywords: [], accent_color: '#0969da',
      },
      supported_layout_types: ['title', 'section', 'content', 'two_column', 'image', 'closing'],
      guidelines: analysis.guidelines,
      learned_at: analysis.analyzed_at,
    };
  }

  private async classifyWithAi(
    templateId: string,
    structure: unknown,
  ): Promise<TemplateAnalysis | null> {
    try {
      const token = await this.settings.getAccessToken();
      const client = new OpenAI({
        baseURL: this.settings.getBaseURL(),
        apiKey: token,
      });

      // Filter out layouts that only have meta placeholders (footer/date/slide-number)
      // and compact the structure to reduce token usage
      const structureData = structure as {
        template_id: string;
        slide_width_cm: number;
        slide_height_cm: number;
        layouts: Array<{
          index: number;
          name: string;
          placeholders: Array<{
            index: number;
            type_id: number;
            type_name: string;
            name: string;
            width_cm: number;
            height_cm: number;
            font_sizes_pt: number[];
            [key: string]: unknown;
          }>;
        }>;
      };
      const META_PH_TYPES = new Set([13, 14, 15, 16]); // SLIDE_NUMBER, DATE, FOOTER

      const compactLayouts = structureData.layouts
        .filter((layout) =>
          layout.placeholders.some((ph) => !META_PH_TYPES.has(ph.type_id)),
        )
        .map((layout) => ({
          idx: layout.index,
          name: layout.name,
          phs: layout.placeholders
            .filter((ph) => !META_PH_TYPES.has(ph.type_id))
            .map((ph) => ({
              type: ph.type_name,
              w: ph.width_cm,
              h: ph.height_cm,
              fonts: ph.font_sizes_pt,
            })),
        }));

      const compactStructure = {
        id: structureData.template_id,
        slide: `${structureData.slide_width_cm}x${structureData.slide_height_cm}cm`,
        layouts: compactLayouts,
      };

      this.logger.log(
        `Sending ${compactLayouts.length}/${structureData.layouts.length} layouts to AI for ${templateId}`,
      );

      // Gemini 2.5 Flash is a "thinking" model — internal reasoning tokens
      // count toward max_tokens. Use a high limit to accommodate both
      // thinking budget and actual JSON output.
      const response = await client.chat.completions.create({
        model: this.settings.getModel(),
        messages: [
          { role: 'system', content: LEARN_PROMPT },
          {
            role: 'user',
            content: `Template: ${templateId}\n\n${JSON.stringify(compactStructure)}`,
          },
        ],
        temperature: 0.2,
        max_tokens: 65536,
      });

      const finishReason = response.choices[0]?.finish_reason;
      this.logger.log(`AI response received for ${templateId}, finish_reason=${finishReason}`);

      const raw = response.choices[0]?.message?.content?.trim() ?? '';
      if (!raw) {
        this.logger.warn(`AI returned empty content for ${templateId}`);
        return null;
      }

      if (raw.length < 50) {
        this.logger.warn(`AI response too short for ${templateId}: ${raw}`);
        return null;
      }

      this.logger.debug(`AI raw response (first 500 chars): ${raw.slice(0, 500)}`);

      // Strip potential markdown code block wrappers
      let jsonStr = raw.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '');

      // If truncated, try to repair JSON by closing open structures
      if (finishReason === 'length') {
        this.logger.warn(`Response truncated for ${templateId}, attempting JSON repair`);
        jsonStr = this.repairTruncatedJson(jsonStr);
      }

      const parsed = JSON.parse(jsonStr) as {
        description: string;
        layout_mappings: Array<{
          layout_index: number;
          layout_name: string;
          mapped_type: string;
          description: string;
          recommended_usage: string;
          max_bullets?: number;
          max_chars_per_bullet?: number;
          title_max_chars?: number;
        }>;
        guidelines: string;
      };

      // Compute constraints deterministically from actual placeholder dimensions
      const enrichedMappings = parsed.layout_mappings.map((m) =>
        this.computeConstraints(m, structureData),
      );

      return {
        template_id: templateId,
        description: parsed.description,
        layout_mappings: enrichedMappings,
        guidelines: parsed.guidelines,
        analyzed_at: new Date().toISOString(),
      };
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      const stack = err instanceof Error ? err.stack : '';
      this.logger.error(`AI classification error for ${templateId}: ${message}`);
      if (stack) this.logger.debug(stack);
      return null;
    }
  }

  /**
   * Attempt to repair truncated JSON by closing open brackets/braces.
   * Trims back to the last complete array element if possible.
   */
  private repairTruncatedJson(json: string): string {
    // Find the layout_mappings array and trim to last complete object
    const arrayStart = json.indexOf('"layout_mappings"');
    if (arrayStart === -1) return json;

    // Try to find the last complete object in the array (ending with })
    const lastCompleteObj = json.lastIndexOf('}');
    if (lastCompleteObj === -1) return json;

    // Check if we're inside the layout_mappings array
    let trimmed = json.slice(0, lastCompleteObj + 1);

    // Count open/close brackets to determine what needs closing
    let braces = 0;
    let brackets = 0;
    for (const ch of trimmed) {
      if (ch === '{') braces++;
      if (ch === '}') braces--;
      if (ch === '[') brackets++;
      if (ch === ']') brackets--;
    }

    // Close open structures
    while (brackets > 0) {
      trimmed += ']';
      brackets--;
    }
    while (braces > 0) {
      trimmed += '}';
      braces--;
    }

    // If guidelines field is missing, inject a default before final }
    if (!trimmed.includes('"guidelines"')) {
      const lastBrace = trimmed.lastIndexOf('}');
      trimmed =
        trimmed.slice(0, lastBrace) +
        ',"guidelines":"Texte kurz und prägnant halten."}';
    }

    return trimmed;
  }

  // Placeholder type IDs from OOXML spec
  private static readonly PH_TITLE = 1;
  private static readonly PH_BODY = 2;
  private static readonly PH_OBJECT = 7;
  private static readonly PH_PICTURE = 18;
  private static readonly META_PH_TYPES = new Set([13, 14, 15, 16]);

  /**
   * Compute max_bullets, max_chars_per_bullet, title_max_chars from actual
   * placeholder dimensions — not from AI estimation.
   *
   * Uses conservative factors:
   *  - Line height = font_pt × 0.065 cm (accounts for 1.2× line spacing)
   *  - Char width  = font_pt × 0.022 cm (accounts for bullet indent + padding)
   *  - Safety margin: 80% of theoretical max
   */
  private computeConstraints(
    mapping: {
      layout_index: number;
      layout_name: string;
      mapped_type: string;
      description: string;
      recommended_usage: string;
      max_bullets?: number;
      max_chars_per_bullet?: number;
      title_max_chars?: number;
    },
    structureData: {
      layouts: Array<{
        index: number;
        placeholders: Array<{
          type_id: number;
          width_cm: number;
          height_cm: number;
          font_sizes_pt: number[];
        }>;
      }>;
    },
  ): LayoutMapping {
    const layout = structureData.layouts.find(
      (l) => l.index === mapping.layout_index,
    );

    let maxBullets = 0;
    let maxCharsPerBullet = 0;
    let titleMaxChars = 0;

    if (layout) {
      const contentPhs = layout.placeholders.filter(
        (ph) => !TemplateAnalysisService.META_PH_TYPES.has(ph.type_id),
      );

      // Find the title placeholder (TITLE type, or largest-font BODY for title layouts)
      const titlePh =
        contentPhs.find(
          (ph) => ph.type_id === TemplateAnalysisService.PH_TITLE,
        ) ??
        (mapping.mapped_type === 'title' || mapping.mapped_type === 'section'
          ? contentPhs.reduce(
              (best, ph) => {
                const font = ph.font_sizes_pt[0] ?? 18;
                const bestFont = best?.font_sizes_pt[0] ?? 0;
                return font > bestFont ? ph : best;
              },
              undefined as (typeof contentPhs)[0] | undefined,
            )
          : undefined);

      if (titlePh) {
        const font = titlePh.font_sizes_pt[0] ?? 18;
        // Conservative: char width with padding
        titleMaxChars = Math.floor(
          (titlePh.width_cm / (font * 0.022)) * 0.8,
        );
      }

      // Find the content placeholder (OBJECT preferred, then large BODY)
      const contentPh =
        contentPhs.find(
          (ph) => ph.type_id === TemplateAnalysisService.PH_OBJECT,
        ) ??
        contentPhs.find(
          (ph) =>
            ph.type_id === TemplateAnalysisService.PH_BODY &&
            ph !== titlePh &&
            ph.height_cm > 3,
        );

      if (contentPh) {
        const font = contentPh.font_sizes_pt[0] ?? 18;
        // Conservative: line height with spacing, safety margin
        const rawLines = contentPh.height_cm / (font * 0.065);
        maxBullets = Math.floor(rawLines * 0.8);

        // For two_column, check if there are 2 OBJECT placeholders
        if (mapping.mapped_type === 'two_column') {
          const objectPhs = contentPhs.filter(
            (ph) => ph.type_id === TemplateAnalysisService.PH_OBJECT,
          );
          if (objectPhs.length >= 2) {
            // Use the narrower of the two columns
            const narrowest = objectPhs.reduce((a, b) =>
              a.width_cm < b.width_cm ? a : b,
            );
            const colFont = narrowest.font_sizes_pt[0] ?? 18;
            const colLines = narrowest.height_cm / (colFont * 0.065);
            maxBullets = Math.floor(colLines * 0.8);
            maxCharsPerBullet = Math.floor(
              (narrowest.width_cm / (colFont * 0.022)) * 0.8,
            );
          }
        }

        if (maxCharsPerBullet === 0) {
          maxCharsPerBullet = Math.floor(
            (contentPh.width_cm / (font * 0.022)) * 0.8,
          );
        }
      }
    }

    return {
      layout_index: mapping.layout_index,
      layout_name: mapping.layout_name,
      mapped_type: mapping.mapped_type,
      description: mapping.description,
      recommended_usage: mapping.recommended_usage,
      max_bullets: maxBullets,
      max_chars_per_bullet: maxCharsPerBullet,
      title_max_chars: titleMaxChars,
    };
  }
}
