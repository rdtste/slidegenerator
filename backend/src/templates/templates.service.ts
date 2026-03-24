import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { TemplateInfoDto, TemplateScope } from './templates.dto';
import * as fs from 'fs';
import * as path from 'path';

interface TemplateMeta {
  scope: TemplateScope;
  sessionId?: string;
  uploadedAt: string;
}

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

  /**
   * Sync a template file to the pptx-service via HTTP upload.
   * Required on Cloud Run where services have separate filesystems.
   */
  async syncTemplateToPptxService(filename: string, buffer: Buffer): Promise<void> {
    try {
      const formData = new FormData();
      formData.append('file', new Blob([new Uint8Array(buffer)]), filename);
      const response = await fetch(`${this.pptxServiceUrl}/api/v1/templates`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const text = await response.text();
        this.logger.warn(`Failed to sync template to pptx-service: ${response.status} ${text}`);
      } else {
        this.logger.log(`Template synced to pptx-service: ${filename}`);
      }
    } catch (err) {
      this.logger.warn(`Could not sync template to pptx-service: ${err}`);
    }
  }

  /**
   * Delete a template from the pptx-service.
   */
  async deleteTemplateFromPptxService(templateId: string): Promise<void> {
    try {
      const response = await fetch(
        `${this.pptxServiceUrl}/api/v1/templates/${encodeURIComponent(templateId)}`,
        { method: 'DELETE' },
      );
      if (response.ok) {
        this.logger.log(`Template deleted from pptx-service: ${templateId}`);
      }
    } catch (err) {
      this.logger.warn(`Could not delete template from pptx-service: ${err}`);
    }
  }

  listTemplates(sessionId?: string): TemplateInfoDto[] {
    const files = fs.readdirSync(this.templatesDir)
      .filter((f) => f.endsWith('.pptx') || f.endsWith('.potx'))
      .sort();

    const all = files.map((f) => this.inspectTemplate(f)).filter(Boolean) as TemplateInfoDto[];

    // Filter: show global templates + session templates matching the caller's sessionId
    const templates = all.filter((t) =>
      t.scope === 'global' || (sessionId && t.sessionId === sessionId),
    );

    if (templates.length === 0) {
      templates.push({
        id: 'default',
        name: 'Standard (Blank)',
        description: 'Standard-PowerPoint-Template ohne Branding',
        layouts: [],
        scope: 'global',
      });
    }

    return templates;
  }

  saveTemplate(filename: string, buffer: Buffer, sessionId?: string): TemplateInfoDto {
    const safeName = filename.replace(/[^a-zA-Z0-9._\- ]/g, '_');
    const dest = path.join(this.templatesDir, safeName);
    fs.writeFileSync(dest, buffer);

    const id = path.parse(safeName).name;
    const meta: TemplateMeta = {
      scope: 'session',
      sessionId,
      uploadedAt: new Date().toISOString(),
    };
    this.saveMeta(id, meta);
    this.logger.log(`Template saved: ${safeName} (scope=${meta.scope}, session=${sessionId ?? 'none'})`);

    return this.inspectTemplate(safeName) ?? {
      id,
      name: id,
      description: '',
      layouts: [],
      scope: 'session',
      sessionId,
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
    this.deleteMeta(templateId);
    this.themeCache.delete(templateId);
    this.logger.log(`Template deleted: ${templateId}`);
    return true;
  }

  setScope(templateId: string, scope: TemplateScope): TemplateInfoDto | null {
    const filePath = this.getTemplatePath(templateId);
    if (!filePath) return null;

    const meta = this.loadMeta(templateId);
    meta.scope = scope;
    if (scope === 'global') {
      delete meta.sessionId;
    }
    this.saveMeta(templateId, meta);
    this.logger.log(`Template scope changed: ${templateId} → ${scope}`);

    const filename = path.basename(filePath);
    return this.inspectTemplate(filename);
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
      const meta = this.loadMeta(id);
      return {
        id,
        name: id.replace(/[_-]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        description: `Template: ${filename}`,
        layouts: [],
        scope: meta.scope,
        sessionId: meta.sessionId,
      };
    } catch {
      return null;
    }
  }

  // ── Meta persistence ──────────────────────────────────────────

  private metaPath(templateId: string): string {
    return path.join(this.templatesDir, `${templateId}.meta.json`);
  }

  private loadMeta(templateId: string): TemplateMeta {
    const p = this.metaPath(templateId);
    if (fs.existsSync(p)) {
      try {
        return JSON.parse(fs.readFileSync(p, 'utf-8')) as TemplateMeta;
      } catch {
        this.logger.warn(`Corrupt meta for ${templateId}, treating as global`);
      }
    }
    // Templates without meta (pre-existing) default to global
    return { scope: 'global', uploadedAt: '' };
  }

  private saveMeta(templateId: string, meta: TemplateMeta): void {
    fs.writeFileSync(this.metaPath(templateId), JSON.stringify(meta, null, 2));
  }

  private deleteMeta(templateId: string): void {
    const p = this.metaPath(templateId);
    if (fs.existsSync(p)) {
      fs.unlinkSync(p);
    }
  }
}
