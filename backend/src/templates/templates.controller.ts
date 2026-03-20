import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Param,
  Body,
  Headers,
  UploadedFile,
  UseInterceptors,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { TemplatesService } from './templates.service';
import { TemplateAnalysisService } from './template-analysis.service';
import { TemplateInfoDto, TemplateScope } from './templates.dto';

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

@Controller('templates')
export class TemplatesController {
  private readonly logger = new Logger(TemplatesController.name);

  constructor(
    private readonly templatesService: TemplatesService,
    private readonly analysisService: TemplateAnalysisService,
  ) {}

  @Get()
  list(@Headers('x-session-id') sessionId?: string): TemplateInfoDto[] {
    return this.templatesService.listTemplates(sessionId);
  }

  @Post()
  @UseInterceptors(FileInterceptor('file'))
  upload(
    @UploadedFile() file: Express.Multer.File,
    @Headers('x-session-id') sessionId?: string,
  ): TemplateInfoDto {
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

    const info = this.templatesService.saveTemplate(file.originalname, file.buffer, sessionId);

    // Fire-and-forget deep learning (replaces simple analysis)
    this.analysisService.learnTemplate(info.id).catch((err) =>
      this.logger.warn(`Background learning failed for ${info.id}: ${err}`),
    );

    return info;
  }

  @Patch(':id/scope')
  setScope(
    @Param('id') id: string,
    @Body('scope') scope: string,
  ): TemplateInfoDto {
    if (scope !== 'global' && scope !== 'session') {
      throw new HttpException(
        { detail: 'Scope muss "global" oder "session" sein' },
        HttpStatus.BAD_REQUEST,
      );
    }
    const result = this.templatesService.setScope(id, scope as TemplateScope);
    if (!result) {
      throw new HttpException(
        { detail: 'Template nicht gefunden' },
        HttpStatus.NOT_FOUND,
      );
    }
    return result;
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

  @Post(':id/learn')
  async learn(@Param('id') id: string) {
    const profile = await this.analysisService.learnTemplate(id);
    if (!profile) {
      throw new HttpException(
        { detail: 'Template-Learning fehlgeschlagen' },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
    return {
      learned: true,
      layouts_classified: profile.layout_catalog.length,
      supported_types: profile.supported_layout_types,
      design_personality: profile.design_personality,
    };
  }

  @Get(':id/analysis')
  async getAnalysis(@Param('id') id: string) {
    const analysis = await this.analysisService.getAnalysis(id);
    if (!analysis) {
      throw new HttpException(
        { detail: 'Keine Analyse vorhanden. POST /templates/:id/learn aufrufen.' },
        HttpStatus.NOT_FOUND,
      );
    }
    return analysis;
  }

  @Get(':id/profile')
  getProfile(@Param('id') id: string) {
    const profile = this.analysisService.getProfile(id);
    if (!profile) {
      throw new HttpException(
        { detail: 'Kein Profil vorhanden. POST /templates/:id/learn aufrufen.' },
        HttpStatus.NOT_FOUND,
      );
    }
    return profile;
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
