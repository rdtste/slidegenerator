import { Controller, Post, Get, Body, Param, Res, Sse, HttpException, HttpStatus } from '@nestjs/common';
import { Observable, merge, interval, map, takeUntil, Subject } from 'rxjs';
import type { Response } from 'express';
import { ExportService } from './export.service';
import { ExportRequestDto, ExportV2RequestDto, GenerateDeckRequestDto, PregenerateV2RequestDto } from './export.dto';

const CONTENT_TYPES: Record<string, string> = {
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  pdf: 'application/pdf',
};

const EXTENSIONS: Record<string, string> = {
  pptx: '.pptx',
  pdf: '.pdf',
};

@Controller('export')
export class ExportController {
  constructor(private readonly exportService: ExportService) {}

  @Post('pregenerate-v2')
  async pregenerateV2(@Body() dto: PregenerateV2RequestDto): Promise<{ key: string }> {
    const key = this.exportService.buildPregenKey(
      dto.prompt, dto.audience, dto.imageStyle, dto.accentColor, dto.fontFamily, dto.templateId,
    );
    this.exportService.pregenerateV2(
      key, dto.prompt, dto.audience, dto.imageStyle, dto.accentColor, dto.fontFamily, dto.templateId,
    ).catch(() => { /* fire-and-forget */ });
    return { key };
  }

  @Get('pregenerate-v2/:key')
  getPregenStatus(@Param('key') key: string): { status: string; jobId?: string } {
    return this.exportService.getPregenStatus(key);
  }

  @Get('pregenerate-v2/:key/download')
  async downloadPregen(
    @Param('key') key: string,
    @Res() res: Response,
  ): Promise<void> {
    const result = this.exportService.consumePregen(key);
    if (!result) {
      throw new HttpException({ detail: 'Vorgeniertes PPTX nicht verfügbar' }, HttpStatus.NOT_FOUND);
    }
    res.set({
      'Content-Type': CONTENT_TYPES['pptx'],
      'Content-Disposition': `attachment; filename="${result.filename}"`,
      'Content-Length': result.buffer.length.toString(),
    });
    res.send(result.buffer);
  }

  @Post('start-v2')
  async startV2Export(@Body() dto: ExportV2RequestDto): Promise<{ jobId: string }> {
    const jobId = await this.exportService.startV2Job(
      dto.prompt,
      dto.documentText,
      dto.audience,
      dto.imageStyle,
      dto.accentColor,
      dto.fontFamily,
      dto.templateId,
      dto.mode,
    );
    return { jobId };
  }

  @Post('start')
  async startExport(@Body() dto: ExportRequestDto): Promise<{ jobId: string }> {
    const format = dto.format ?? 'pptx';
    const templateId = dto.templateId ?? 'default';

    if (format !== 'pptx') {
      throw new HttpException(
        { detail: 'Streaming-Export nur für PPTX verfügbar' },
        HttpStatus.BAD_REQUEST,
      );
    }

    const jobId = await this.exportService.startPptxJob(dto.markdown, templateId, dto.customColor, dto.customFont);
    return { jobId };
  }

  @Sse('progress/:jobId')
  progress(@Param('jobId') jobId: string): Observable<MessageEvent> {
    const jobProgress$ = this.exportService.getJobProgress(jobId);
    const done$ = new Subject<void>();

    // Heartbeat every 15s to keep Cloud Run connection alive
    const heartbeat$ = interval(15_000).pipe(
      takeUntil(done$),
      map(() => ({ data: { step: 'heartbeat' }, type: 'heartbeat' } as MessageEvent)),
    );

    return new Observable<MessageEvent>((subscriber) => {
      const merged = merge(jobProgress$, heartbeat$);
      const sub = merged.subscribe({
        next: (event) => subscriber.next(event),
        error: (err) => { done$.next(); subscriber.error(err); },
        complete: () => { done$.next(); subscriber.complete(); },
      });
      return () => { done$.next(); sub.unsubscribe(); };
    });
  }

  @Get('download/:jobId')
  async downloadJob(
    @Param('jobId') jobId: string,
    @Res() res: Response,
  ): Promise<void> {
    const { buffer, filename } = this.exportService.getJobFile(jobId);
    res.set({
      'Content-Type': CONTENT_TYPES['pptx'],
      'Content-Disposition': `attachment; filename="${filename}"`,
      'Content-Length': buffer.length.toString(),
    });
    res.send(buffer);
  }

  // ── Generate-Deck API (external, async + polling) ──────────────────

  @Post('generate-deck')
  async generateDeck(@Body() dto: GenerateDeckRequestDto): Promise<{
    jobId: string;
    statusUrl: string;
    message: string;
  }> {
    const jobId = await this.exportService.startV2Job(
      dto.topic,
      undefined,
      dto.audience,
      dto.imageStyle,
      dto.accentColor,
      dto.fontFamily,
      dto.templateId,
      dto.mode,
    );
    return {
      jobId,
      statusUrl: `/api/v1/export/generate-deck/${jobId}`,
      message: 'Deck-Generierung gestartet. Abfrage des Status über statusUrl.',
    };
  }

  @Get('generate-deck/:jobId')
  async getDeckStatus(@Param('jobId') jobId: string): Promise<{
    jobId: string;
    status: string;
    progress: number;
    downloadUrl?: string;
    error?: string;
  }> {
    const info = this.exportService.getJobInfo(jobId);
    const result: {
      jobId: string;
      status: string;
      progress: number;
      downloadUrl?: string;
      error?: string;
    } = {
      jobId,
      status: info.status,
      progress: info.progress,
    };
    if (info.status === 'complete') {
      result.downloadUrl = `/api/v1/export/generate-deck/${jobId}/file`;
    }
    if (info.error) {
      result.error = info.error;
    }
    return result;
  }

  @Get('generate-deck/:jobId/file')
  async downloadDeck(
    @Param('jobId') jobId: string,
    @Res() res: Response,
  ): Promise<void> {
    const { buffer, filename } = this.exportService.getJobFile(jobId);
    res.set({
      'Content-Type': CONTENT_TYPES['pptx'],
      'Content-Disposition': `attachment; filename="${filename}"`,
      'Content-Length': buffer.length.toString(),
    });
    res.send(buffer);
  }

  @Post()
  async export(@Body() dto: ExportRequestDto, @Res() res: Response): Promise<void> {
    const format = dto.format ?? 'pptx';
    const templateId = dto.templateId ?? 'default';

    try {
      let buffer: Buffer;

      switch (format) {
        case 'pptx':
          buffer = await this.exportService.generatePptx(dto.markdown, templateId);
          break;
        case 'pdf':
          buffer = await this.exportService.generatePdf(dto.markdown);
          break;
        default:
          throw new HttpException({ detail: `Unbekanntes Format: ${format}` }, HttpStatus.BAD_REQUEST);
      }

      const filename = `presentation${EXTENSIONS[format]}`;
      res.set({
        'Content-Type': CONTENT_TYPES[format],
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Content-Length': buffer.length.toString(),
      });
      res.send(buffer);
    } catch (error: unknown) {
      if (error instanceof HttpException) throw error;
      
      let message: string;
      if (error instanceof Error) {
        message = error.message;
      } else if (typeof error === 'object' && error !== null && 'detail' in error) {
        message = String((error as Record<string, unknown>).detail);
      } else if (typeof error === 'string') {
        message = error;
      } else {
        message = String(error) || 'Unknown error';
      }
      
      throw new HttpException(
        { detail: `Export-Fehler: ${message}` },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }
}
