import { Controller, Post, Get, Body, Param, Res, Sse, HttpException, HttpStatus } from '@nestjs/common';
import { Observable } from 'rxjs';
import type { Response } from 'express';
import { ExportService } from './export.service';
import { ExportRequestDto } from './export.dto';

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

    const jobId = await this.exportService.startPptxJob(dto.markdown, templateId);
    return { jobId };
  }

  @Sse('progress/:jobId')
  progress(@Param('jobId') jobId: string): Observable<MessageEvent> {
    return this.exportService.getJobProgress(jobId);
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
      const message = error instanceof Error ? error.message : 'Unknown error';
      throw new HttpException(
        { detail: `Export-Fehler: ${message}` },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }
}
