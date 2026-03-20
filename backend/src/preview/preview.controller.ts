import { Controller, Post, Body, Res, Header } from '@nestjs/common';
import { Response } from 'express';
import { PreviewService } from './preview.service';
import { PreviewRequestDto } from './preview.dto';
import { TemplatesService } from '../templates/templates.service';

@Controller('preview')
export class PreviewController {
  constructor(
    private readonly previewService: PreviewService,
    private readonly templatesService: TemplatesService,
  ) {}

  @Post()
  @Header('Content-Type', 'text/html; charset=utf-8')
  async preview(@Body() dto: PreviewRequestDto): Promise<string> {
    let themeCss: string | undefined;
    let slideWidth: number | undefined;
    let slideHeight: number | undefined;
    if (dto.templateId && dto.templateId !== 'default') {
      const theme = await this.templatesService.getTheme(dto.templateId);
      if (theme) {
        themeCss = theme.css;
        slideWidth = theme.slide_width_cm;
        slideHeight = theme.slide_height_cm;
      }
    }
    return this.previewService.renderHtml(dto.markdown, themeCss, slideWidth, slideHeight);
  }
}
