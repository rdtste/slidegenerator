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

    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'k8marp-'));
    const mdPath = path.join(tmpDir, 'slides.md');
    const pdfPath = path.join(tmpDir, 'slides.pdf');

    try {
      fs.writeFileSync(mdPath, markdown, 'utf-8');

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
   * Generate standalone HTML via marp-cli.
   */
  async generateHtml(markdown: string): Promise<Buffer> {
    this.logger.log('Generating HTML via marp-cli');

    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'k8marp-'));
    const mdPath = path.join(tmpDir, 'slides.md');
    const htmlPath = path.join(tmpDir, 'slides.html');

    try {
      fs.writeFileSync(mdPath, markdown, 'utf-8');

      const { marpCli } = await (Function('return import("@marp-team/marp-cli")')() as Promise<typeof import('@marp-team/marp-cli')>);

      const exitCode = await marpCli([mdPath, '-o', htmlPath]);

      if (exitCode !== 0) {
        throw new Error(`marp-cli exited with code ${exitCode}`);
      }

      return fs.readFileSync(htmlPath);
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  }
}
