import { Injectable, Logger, HttpException, HttpStatus } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { ReplaySubject, Observable } from 'rxjs';
import { randomUUID } from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

interface ProgressEvent {
  step: string;
  message: string;
  progress?: number | null;
  [key: string]: unknown;
}

interface ExportJob {
  status: 'processing' | 'complete' | 'error';
  subject: ReplaySubject<MessageEvent>;
  buffer?: Buffer;
  filename: string;
  createdAt: number;
}

@Injectable()
export class ExportService {
  private readonly logger = new Logger(ExportService.name);
  private readonly pptxServiceUrl: string;
  private readonly jobs = new Map<string, ExportJob>();

  constructor(private readonly config: ConfigService) {
    this.pptxServiceUrl = this.config.get<string>(
      'PPTX_SERVICE_URL',
      'http://localhost:8000',
    );
  }

  async startV2Job(
    prompt: string,
    documentText?: string,
    audience?: string,
    imageStyle?: string,
    accentColor?: string,
    fontFamily?: string,
    templateId?: string,
  ): Promise<string> {
    const jobId = randomUUID();
    const job: ExportJob = {
      status: 'processing',
      subject: new ReplaySubject<MessageEvent>(),
      filename: 'presentation_v2.pptx',
      createdAt: Date.now(),
    };
    this.jobs.set(jobId, job);

    this.processV2Job(jobId, prompt, documentText, audience, imageStyle, accentColor, fontFamily, templateId).catch((err) => {
      let message: string;
      if (err instanceof Error) {
        message = err.message;
      } else if (typeof err === 'object' && err !== null && 'detail' in err) {
        message = String((err as Record<string, unknown>).detail);
      } else {
        message = String(err) || 'Unknown error';
      }
      this.logger.error(`V2 Job ${jobId} failed: ${message}`);
      if (job.status === 'processing') {
        job.status = 'error';
        job.subject.next({ data: { step: 'error', detail: message, message }, type: 'fail' } as MessageEvent);
        job.subject.complete();
      }
    });

    return jobId;
  }

  private async processV2Job(
    jobId: string,
    prompt: string,
    documentText?: string,
    audience?: string,
    imageStyle?: string,
    accentColor?: string,
    fontFamily?: string,
    templateId?: string,
  ): Promise<void> {
    const job = this.jobs.get(jobId);
    if (!job) return;

    this.logger.log(`Starting V2 pipeline generation for job ${jobId}`);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 540_000);

    let response: Response;
    try {
      response = await fetch(
        `${this.pptxServiceUrl}/api/v1/generate-v2`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt,
            document_text: documentText || '',
            audience: audience || 'management',
            image_style: imageStyle || 'minimal',
            accent_color: accentColor || '#2563EB',
            font_family: fontFamily || 'Calibri',
            template_id: templateId || null,
          }),
          signal: controller.signal,
        },
      );
    } catch (fetchErr: unknown) {
      clearTimeout(timeout);
      const msg = fetchErr instanceof Error ? fetchErr.message : String(fetchErr);
      throw new Error(`PPTX-Service V2 nicht erreichbar: ${msg}`);
    }

    if (!response.ok || !response.body) {
      clearTimeout(timeout);
      const body = await response.text().catch(() => 'unknown');
      throw new Error(`PPTX service V2 returned ${response.status}: ${body}`);
    }

    // Process SSE stream — same structure as V1
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop()!;

      for (const part of parts) {
        if (!part.trim()) continue;

        let eventType = 'message';
        let data = '';

        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) eventType = line.slice(7);
          else if (line.startsWith('data: ')) data = line.slice(6);
        }
        if (!data) continue;

        let parsed: Record<string, unknown>;
        try {
          parsed = JSON.parse(data);
        } catch {
          continue;
        }

        if (eventType === 'complete') {
          const fileId = parsed['fileId'] as string;
          job.filename = (parsed['filename'] as string) || 'presentation_v2.pptx';

          const fileResponse = await fetch(
            `${this.pptxServiceUrl}/api/v1/download-v2/${fileId}`,
          );
          if (!fileResponse.ok) {
            throw new Error('Failed to download V2 generated file from pptx-service');
          }
          job.buffer = Buffer.from(await fileResponse.arrayBuffer());
          job.status = 'complete';
          job.subject.next({ data: parsed, type: 'complete' } as MessageEvent);
          job.subject.complete();
          this.logger.log(`V2 Job ${jobId} complete: ${job.filename}`);
        } else if (eventType === 'fail') {
          job.status = 'error';
          job.subject.next({ data: parsed, type: 'fail' } as MessageEvent);
          job.subject.complete();
          this.logger.warn(`V2 Job ${jobId} failed: ${parsed['detail']}`);
        } else {
          job.subject.next({ data: parsed, type: eventType || 'progress' } as MessageEvent);
        }
      }
    }

    clearTimeout(timeout);

    if (job.status === 'processing') {
      job.status = 'error';
      job.subject.next({
        data: { step: 'error', detail: 'V2 Pipeline Verbindung unterbrochen', message: 'V2 Pipeline Verbindung unterbrochen' },
        type: 'fail',
      } as MessageEvent);
      job.subject.complete();
    }
  }

  async startPptxJob(markdown: string, templateId: string, customColor?: string, customFont?: string): Promise<string> {
    const jobId = randomUUID();
    const job: ExportJob = {
      status: 'processing',
      subject: new ReplaySubject<MessageEvent>(),
      filename: 'presentation.pptx',
      createdAt: Date.now(),
    };
    this.jobs.set(jobId, job);

    this.processPptxJob(jobId, markdown, templateId, customColor, customFont).catch((err) => {
      let message: string;
      if (err instanceof Error) {
        message = err.message;
      } else if (typeof err === 'object' && err !== null && 'detail' in err) {
        message = String((err as Record<string, unknown>).detail);
      } else if (typeof err === 'string') {
        message = err;
      } else {
        message = String(err) || 'Unknown error';
      }
      this.logger.error(`Job ${jobId} failed: ${message}`);
      if (job.status === 'processing') {
        job.status = 'error';
        job.subject.next({ data: { step: 'error', detail: message, message }, type: 'fail' } as MessageEvent);
        job.subject.complete();
      }
    });

    return jobId;
  }

  private async processPptxJob(
    jobId: string,
    markdown: string,
    templateId: string,
    customColor?: string,
    customFont?: string,
  ): Promise<void> {
    const job = this.jobs.get(jobId);
    if (!job) return;

    this.logger.log(`Starting streaming PPTX generation for job ${jobId}`);
    this.logger.log(`PPTX service URL: ${this.pptxServiceUrl}/api/v1/generate-stream`);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 540_000); // 9 min timeout

    let response: Response;
    try {
      response = await fetch(
        `${this.pptxServiceUrl}/api/v1/generate-stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
          markdown,
          template_id: templateId,
          custom_color: customColor || undefined,
          custom_font: customFont || undefined,
        }),
          signal: controller.signal,
        },
      );
    } catch (fetchErr: unknown) {
      clearTimeout(timeout);
      const msg = fetchErr instanceof Error ? fetchErr.message : String(fetchErr);
      const cause = fetchErr instanceof Error && (fetchErr as NodeJS.ErrnoException).cause
        ? String((fetchErr as NodeJS.ErrnoException).cause)
        : '';
      this.logger.error(`Failed to connect to pptx-service: ${msg} | cause: ${cause}`);
      throw new Error(`PPTX-Service nicht erreichbar: ${msg}${cause ? ` (${cause})` : ''}`);
    }

    if (!response.ok || !response.body) {
      clearTimeout(timeout);
      const body = await response.text().catch(() => 'unknown');
      throw new Error(`PPTX service returned ${response.status}: ${body}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fileId: string | undefined;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop()!;

      for (const part of parts) {
        if (!part.trim()) continue;

        let eventType = 'message';
        let data = '';

        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) eventType = line.slice(7);
          else if (line.startsWith('data: ')) data = line.slice(6);
        }
        if (!data) continue;

        let parsed: Record<string, unknown>;
        try {
          parsed = JSON.parse(data);
        } catch {
          continue;
        }

        if (eventType === 'complete') {
          fileId = parsed['fileId'] as string;
          job.filename = (parsed['filename'] as string) || 'presentation.pptx';

          const fileResponse = await fetch(
            `${this.pptxServiceUrl}/api/v1/download/${fileId}`,
          );
          if (!fileResponse.ok) {
            throw new Error('Failed to download generated file from pptx-service');
          }
          job.buffer = Buffer.from(await fileResponse.arrayBuffer());
          job.status = 'complete';
          job.subject.next({ data: parsed, type: 'complete' } as MessageEvent);
          job.subject.complete();
          this.logger.log(`Job ${jobId} complete: ${job.filename}`);
        } else if (eventType === 'qa_result') {
          job.subject.next({ data: parsed, type: 'qa_result' } as MessageEvent);
        } else if (eventType === 'fail') {
          job.status = 'error';
          job.subject.next({ data: parsed, type: 'fail' } as MessageEvent);
          job.subject.complete();
          this.logger.warn(`Job ${jobId} failed: ${parsed['detail']}`);
        } else if (eventType.endsWith('_failed')) {
          const detail =
            typeof parsed['detail'] === 'string'
              ? parsed['detail']
              : `Export fehlgeschlagen (${eventType})`;
          job.status = 'error';
          job.subject.next({ data: { ...parsed, detail }, type: 'fail' } as MessageEvent);
          job.subject.complete();
          this.logger.warn(`Job ${jobId} failed (${eventType}): ${detail}`);
        } else {
          const forwardedType = eventType || 'progress';
          job.subject.next({ data: parsed, type: forwardedType } as MessageEvent);
        }
      }
    }

    clearTimeout(timeout);

    if (job.status === 'processing') {
      job.status = 'error';
      job.subject.next({
        data: {
          step: 'error',
          detail: 'Verbindung zum Generierungs-Service unterbrochen',
          message: 'Verbindung zum Generierungs-Service unterbrochen'
        },
        type: 'fail',
      } as MessageEvent);
      job.subject.complete();
    }
  }

  getJobProgress(jobId: string): Observable<MessageEvent> {
    const job = this.jobs.get(jobId);
    if (!job) {
      throw new HttpException({ detail: 'Job nicht gefunden' }, HttpStatus.NOT_FOUND);
    }
    return job.subject.asObservable();
  }

  getJobFile(jobId: string): { buffer: Buffer; filename: string } {
    const job = this.jobs.get(jobId);
    if (!job || job.status !== 'complete' || !job.buffer) {
      throw new HttpException({ detail: 'Datei nicht verfügbar' }, HttpStatus.NOT_FOUND);
    }
    const { buffer, filename } = job;
    this.jobs.delete(jobId);
    return { buffer, filename };
  }

  /**
   * Generate PPTX by proxying to the Python pptx-service (blocking, no progress).
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

      // Import marp-cli dynamically
      let marpCli: (args: string[]) => Promise<number>;
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const { marpCli: marpCliFunc } = require('@marp-team/marp-cli');
        marpCli = marpCliFunc;
      } catch (importErr) {
        this.logger.error(`Failed to import marp-cli: ${importErr}`);
        throw new Error('marp-cli not available. PDF export is not supported in Docker builds. Please use PPTX export instead.');
      }

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
