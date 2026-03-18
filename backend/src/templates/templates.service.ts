import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { TemplateInfoDto } from './templates.dto';
import * as fs from 'fs';
import * as path from 'path';

export interface PlaceholderConstraint {
  role: string;
  width_cm: number;
  height_cm: number;
  font_size_pt: number;
  max_lines: number;
  max_chars_per_line: number;
}

export interface LayoutConstraint {
  layout_name: string;
  layout_type: string;
  placeholders: PlaceholderConstraint[];
  max_bullets: number;
  max_chars_per_bullet: number;
  title_max_chars: number;
}

export interface TemplateTheme {
  template_id: string;
  template_name: string;
  heading_font: string;
  body_font: string;
  bg_color: string;
  text_color: string;
  accent_color: string;
  accent2_color: string;
  heading_color: string;
  layouts: string[];
  css: string;
  slide_width_cm: number;
  slide_height_cm: number;
  layout_constraints: LayoutConstraint[];
}

@Injectable()
export class TemplatesService {
  private readonly logger = new Logger(TemplatesService.name);
  private readonly templatesDir: string;

  constructor(private readonly config: ConfigService) {
    this.templatesDir = this.config.get<string>(
      'TEMPLATES_DIR',
      path.resolve(__dirname, '../../templates'),
    );
    this.pptxServiceUrl = this.config.get<string>(
      'PPTX_SERVICE_URL',
      'http://localhost:8000',
    );
    fs.mkdirSync(this.templatesDir, { recursive: true });
  }

  private readonly pptxServiceUrl: string;
  private themeCache = new Map<string, { theme: TemplateTheme; ts: number }>();

  listTemplates(): TemplateInfoDto[] {
    const files = fs.readdirSync(this.templatesDir)
      .filter((f) => f.endsWith('.pptx') || f.endsWith('.potx'))
      .sort();

    const templates = files.map((f) => this.inspectTemplate(f)).filter(Boolean) as TemplateInfoDto[];

    if (templates.length === 0) {
      templates.push({
        id: 'default',
        name: 'Standard (Blank)',
        description: 'Standard-PowerPoint-Template ohne Branding',
        layouts: [],
      });
    }

    return templates;
  }

  saveTemplate(filename: string, buffer: Buffer): TemplateInfoDto {
    const safeName = filename.replace(/[^a-zA-Z0-9._\- ]/g, '_');
    const dest = path.join(this.templatesDir, safeName);
    fs.writeFileSync(dest, buffer);
    this.logger.log(`Template saved: ${safeName}`);

    return this.inspectTemplate(safeName) ?? {
      id: path.parse(safeName).name,
      name: path.parse(safeName).name,
      description: '',
      layouts: [],
    };
  }

  getTemplatePath(templateId: string): string | null {
    for (const ext of ['.pptx', '.potx']) {
      const filePath = path.join(this.templatesDir, `${templateId}${ext}`);
      if (fs.existsSync(filePath)) return filePath;
    }
    return null;
  }

  deleteTemplate(templateId: string): boolean {
    const filePath = this.getTemplatePath(templateId);
    if (!filePath) return false;
    fs.unlinkSync(filePath);
    this.themeCache.delete(templateId);
    this.logger.log(`Template deleted: ${templateId}`);
    return true;
  }

  async getTheme(templateId: string): Promise<TemplateTheme | null> {
    if (!templateId || templateId === 'default') return null;

    const cached = this.themeCache.get(templateId);
    if (cached && Date.now() - cached.ts < 300_000) {
      return cached.theme;
    }

    try {
      const response = await fetch(
        `${this.pptxServiceUrl}/api/v1/templates/${encodeURIComponent(templateId)}/theme`,
      );
      if (!response.ok) return null;
      const theme = (await response.json()) as TemplateTheme;
      this.themeCache.set(templateId, { theme, ts: Date.now() });
      return theme;
    } catch (err) {
      this.logger.warn(`Failed to fetch theme for ${templateId}: ${err}`);
      return null;
    }
  }

  private inspectTemplate(filename: string): TemplateInfoDto | null {
    try {
      const id = path.parse(filename).name;
      return {
        id,
        name: id.replace(/[_-]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        description: `Template: ${filename}`,
        layouts: [],
      };
    } catch {
      return null;
    }
  }
}
