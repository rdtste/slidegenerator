import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { SettingsService } from '../settings/settings.service';
import OpenAI from 'openai';
import * as fs from 'fs';
import * as path from 'path';

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

const ANALYSIS_PROMPT = `Du bist ein PowerPoint-Template-Experte. Klassifiziere die Layouts eines Folienmasters.

Eingabe: Pro Layout: idx (Index), name, phs (Platzhalter: type, w=Breite cm, h=Höhe cm, fonts=pt).
Typen: TITLE=Titel, BODY=Text, OBJECT=Inhalt, PICTURE=Bild.

Wähle GENAU EIN bestes Layout pro Typ:
- title: Titelfolie (großer Text für Präsentationstitel)
- section: Abschnittstrenner (kurzer Titel)
- content: Inhaltsfolie (Titel + Bullet Points im OBJECT-Platzhalter)
- two_column: Zwei-Spalten (zwei gleich große OBJECT-Platzhalter)
- image: Bild + Text (PICTURE-Platzhalter + Textbereich)
- closing: Abschluss (Kontakt, Danke)

Antworte NUR mit kompaktem JSON, KEINE Codeblöcke, KEINE Erklärungen:
{"description":"Template-Beschreibung","layout_mappings":[{"layout_index":1,"layout_name":"Name","mapped_type":"title","description":"Kurz","recommended_usage":"Kurz"}],"guidelines":"Texthinweise"}

WICHTIG: Gib NUR die 6 besten Layouts zurück (eins pro Typ). Kein "unused". Halte Beschreibungen sehr kurz (max 15 Wörter). KEINE Kapazitätsangaben — die werden automatisch berechnet.`;

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

  async getAnalysis(templateId: string): Promise<TemplateAnalysis | null> {
    if (!templateId || templateId === 'default') return null;

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

  async analyzeTemplate(templateId: string): Promise<TemplateAnalysis | null> {
    this.logger.log(`Starting AI analysis for template: ${templateId}`);

    // 1. Fetch raw structure from pptx-service
    const structure = await this.fetchStructure(templateId);
    if (!structure) {
      this.logger.warn(`Could not fetch structure for ${templateId}`);
      return null;
    }

    // 2. Send to Gemini for classification
    const analysis = await this.classifyWithAi(templateId, structure);
    if (!analysis) {
      this.logger.warn(`AI classification failed for ${templateId}`);
      return null;
    }

    // 3. Store as JSON sidecar file
    const filePath = this.analysisPath(templateId);
    fs.writeFileSync(filePath, JSON.stringify(analysis, null, 2), 'utf-8');
    this.logger.log(
      `Analysis saved for ${templateId}: ${analysis.layout_mappings.length} mappings`,
    );

    return analysis;
  }

  deleteAnalysis(templateId: string): void {
    const filePath = this.analysisPath(templateId);
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
      this.logger.log(`Analysis deleted for ${templateId}`);
    }
  }

  private async fetchStructure(templateId: string): Promise<unknown> {
    try {
      const response = await fetch(
        `${this.pptxServiceUrl}/api/v1/templates/${encodeURIComponent(templateId)}/structure`,
      );
      if (!response.ok) return null;
      return await response.json();
    } catch (err) {
      this.logger.warn(`Failed to fetch structure for ${templateId}: ${err}`);
      return null;
    }
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
          { role: 'system', content: ANALYSIS_PROMPT },
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
