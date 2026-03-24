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
  async upload(
    @UploadedFile() file: Express.Multer.File,
    @Headers('x-session-id') sessionId?: string,
  ): Promise<TemplateInfoDto & { learned: boolean; profileSummary?: { layouts_classified: number; supported_types: string[]; design_personality: string } }> {
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

    // Sync template file to pptx-service (required on Cloud Run where filesystems are separate)
    await this.templatesService.syncTemplateToPptxService(file.originalname, file.buffer);

    // Deep learning runs synchronously — templates are few but must be perfectly understood
    try {
      const profile = await this.analysisService.learnTemplate(info.id);
      if (profile) {
        this.logger.log(`Template ${info.id} uploaded and learned: ${profile.layout_catalog.length} layouts`);
        return {
          ...info,
          learned: true,
          profileSummary: {
            layouts_classified: profile.layout_catalog.length,
            supported_types: profile.supported_layout_types,
            design_personality: profile.design_personality,
          },
        };
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.logger.warn(`Learning failed for ${info.id}: ${message}`);
    }

    return { ...info, learned: false };
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
    try {
      const profile = await this.analysisService.learnTemplate(id);
      return {
        learned: true,
        layouts_classified: profile.layout_catalog.length,
        supported_types: profile.supported_layout_types,
        design_personality: profile.design_personality,
      };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.logger.error(`Template learning failed for ${id}: ${message}`);
      throw new HttpException(
        { detail: `Template-Learning fehlgeschlagen: ${message}` },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
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
  async delete(@Param('id') id: string): Promise<{ deleted: boolean }> {
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
    await this.templatesService.deleteTemplateFromPptxService(id);
    return { deleted: true };
  }
}
