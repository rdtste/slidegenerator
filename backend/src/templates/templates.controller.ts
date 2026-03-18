import {
  Controller,
  Get,
  Post,
  Delete,
  Param,
  UploadedFile,
  UseInterceptors,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { TemplatesService } from './templates.service';
import { TemplateAnalysisService } from './template-analysis.service';
import { TemplateInfoDto } from './templates.dto';

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

@Controller('templates')
export class TemplatesController {
  private readonly logger = new Logger(TemplatesController.name);

  constructor(
    private readonly templatesService: TemplatesService,
    private readonly analysisService: TemplateAnalysisService,
  ) {}

  @Get()
  list(): TemplateInfoDto[] {
    return this.templatesService.listTemplates();
  }

  @Post()
  @UseInterceptors(FileInterceptor('file'))
  upload(@UploadedFile() file: Express.Multer.File): TemplateInfoDto {
    const ext = file?.originalname?.toLowerCase();
    if (!file || (!ext?.endsWith('.pptx') && !ext?.endsWith('.potx'))) {
      throw new HttpException(
        { detail: 'Nur .pptx- oder .potx-Dateien erlaubt' },
        HttpStatus.BAD_REQUEST,
      );
    }
    if (file.size > MAX_FILE_SIZE) {
      throw new HttpException(
        { detail: 'Datei zu groß (max 50 MB)' },
        HttpStatus.BAD_REQUEST,
      );
    }

    const info = this.templatesService.saveTemplate(file.originalname, file.buffer);

    // Fire-and-forget AI analysis
    this.analysisService.analyzeTemplate(info.id).catch((err) =>
      this.logger.warn(`Background analysis failed for ${info.id}: ${err}`),
    );

    return info;
  }

  @Post(':id/analyze')
  async analyze(@Param('id') id: string): Promise<{ analyzed: boolean }> {
    const result = await this.analysisService.analyzeTemplate(id);
    if (!result) {
      throw new HttpException(
        { detail: 'Analyse fehlgeschlagen' },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
    return { analyzed: true };
  }

  @Get(':id/analysis')
  async getAnalysis(@Param('id') id: string) {
    const analysis = await this.analysisService.getAnalysis(id);
    if (!analysis) {
      throw new HttpException(
        { detail: 'Keine Analyse vorhanden. POST /templates/:id/analyze aufrufen.' },
        HttpStatus.NOT_FOUND,
      );
    }
    return analysis;
  }

  @Delete(':id')
  delete(@Param('id') id: string): { deleted: boolean } {
    if (id === 'default') {
      throw new HttpException(
        { detail: 'Das Standard-Template kann nicht gelöscht werden' },
        HttpStatus.BAD_REQUEST,
      );
    }
    const deleted = this.templatesService.deleteTemplate(id);
    if (!deleted) {
      throw new HttpException(
        { detail: 'Template nicht gefunden' },
        HttpStatus.NOT_FOUND,
      );
    }
    this.analysisService.deleteAnalysis(id);
    return { deleted: true };
  }
}
