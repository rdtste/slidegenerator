import { Injectable, Logger, HttpException, HttpStatus } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

@Injectable()
export class ExportService {
  private readonly logger = new Logger(ExportService.name);
  private readonly pptxServiceUrl: string;

  constructor(private readonly config: ConfigService) {
    this.pptxServiceUrl = this.config.get<string>(
      'PPTX_SERVICE_URL',
      'http://localhost:8000',
    );
  }

  /**
   * Generate PPTX by proxying to the Python pptx-service.
   */
  async generatePptx(
    markdown: string,
    templateId: string,
  ): Promise<Buffer> {
    this.logger.log(`Generating PPTX via pptx-service (template: ${templateId})`);

    const response = await fetch(`${this.pptxServiceUrl}/api/v1/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ markdown, template_id: templateId }),
    });

    if (!response.ok) {
      const body = await response.text();
      this.logger.error(`PPTX service error: ${response.status} ${body}`);
      throw new HttpException(
        { detail: `PPTX-Service Fehler: ${body}` },
        HttpStatus.BAD_GATEWAY,
      );
    }

    const arrayBuffer = await response.arrayBuffer();
    return Buffer.from(arrayBuffer);
  }

  /**
   * Generate PDF via marp-cli.
   */
  async generatePdf(markdown: string): Promise<Buffer> {
    this.logger.log('Generating PDF via marp-cli');

    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'slidegen-'));
    const mdPath = path.join(tmpDir, 'slides.md');
    const pdfPath = path.join(tmpDir, 'slides.pdf');

    try {
      const prepared = this.prepareMarpMarkdown(markdown);
      fs.writeFileSync(mdPath, prepared, 'utf-8');

      const { marpCli } = await (Function('return import("@marp-team/marp-cli")')() as Promise<typeof import('@marp-team/marp-cli')>);

      const exitCode = await marpCli([mdPath, '--pdf', '-o', pdfPath, '--allow-local-files']);

      if (exitCode !== 0) {
        throw new Error(`marp-cli exited with code ${exitCode}`);
      }

      return fs.readFileSync(pdfPath);
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  }

  /**
   * Ensure markdown has marp frontmatter and replace placeholder images.
   */
  private prepareMarpMarkdown(markdown: string): string {
    let md = markdown;

    // Replace ![desc](placeholder) with inline SVG data URIs
    md = md.replace(
      /!\[([^\]]*)\]\(placeholder\)/g,
      (_match: string, alt: string) => {
        const escaped = alt
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;');
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450">`
          + `<rect width="800" height="450" rx="12" fill="#23272f"/>`
          + `<text x="400" y="200" text-anchor="middle" font-family="sans-serif" font-size="20" fill="#9ca3af">Bild-Platzhalter</text>`
          + `<text x="400" y="240" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#6b7280">${escaped}</text>`
          + `</svg>`;
        const dataUri = `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;
        return `![${alt}](${dataUri})`;
      },
    );

    // Ensure marp frontmatter exists
    if (md.match(/^---\s*\n[\s\S]*?marp:\s*true/)) {
      return md;
    }
    if (md.startsWith('---')) {
      // Has frontmatter but no marp: true — inject it
      return md.replace(/^---\n/, '---\nmarp: true\n');
    }
    // No frontmatter at all — prepend
    return `---\nmarp: true\n---\n\n${md}`;
  }
}
