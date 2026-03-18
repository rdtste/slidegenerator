import { Module } from '@nestjs/common';
import { TemplatesController } from './templates.controller';
import { TemplatesService } from './templates.service';
import { TemplateAnalysisService } from './template-analysis.service';

@Module({
  controllers: [TemplatesController],
  providers: [TemplatesService, TemplateAnalysisService],
  exports: [TemplatesService, TemplateAnalysisService],
})
export class TemplatesModule {}
