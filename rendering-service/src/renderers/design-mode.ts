/**
 * Design Mode Renderer — creates PPTX from scratch using PptxGenJS.
 *
 * Used when no corporate template is involved. Full control over every element.
 * PptxGenJS provides: slide masters, text boxes, shapes, images, charts, tables.
 */

import PptxGenJS from 'pptxgenjs';
import type { RenderInstruction, RenderElement, ElementStyle } from '../types.js';
import { logger } from '../utils/logger.js';

/** Convert cm to inches (PptxGenJS uses inches). */
const cmToInch = (cm: number): number => cm / 2.54;

export class DesignModeRenderer {
  private accentColor: string;
  private fontFamily: string;

  constructor(accentColor: string = '#2563EB', fontFamily: string = 'Calibri') {
    this.accentColor = accentColor;
    this.fontFamily = fontFamily;
  }

  async render(instructions: RenderInstruction[], outputPath: string): Promise<void> {
    const pptx = new PptxGenJS();
    pptx.layout = 'LAYOUT_WIDE'; // 13.33" x 7.5" (16:9)

    for (const instruction of instructions) {
      this.renderSlide(pptx, instruction);
    }

    await pptx.writeFile({ fileName: outputPath });
    logger.info(`Design mode: wrote ${instructions.length} slides to ${outputPath}`);
  }

  private renderSlide(pptx: PptxGenJS, instruction: RenderInstruction): void {
    const slide = pptx.addSlide();

    // Set background
    if (instruction.background_color !== '#FFFFFF') {
      slide.background = { color: this.resolveColor(instruction.background_color) };
    }

    // Render each element
    for (const element of instruction.elements) {
      this.renderElement(slide, element);
    }
  }

  private renderElement(slide: PptxGenJS.Slide, element: RenderElement): void {
    const { position: pos, style } = element;
    const x = cmToInch(pos.left_cm);
    const y = cmToInch(pos.top_cm);
    const w = cmToInch(pos.width_cm);
    const h = cmToInch(pos.height_cm);

    if (element.element_type === 'shape') {
      this.renderShape(slide, element, x, y, w, h);
    } else if (element.element_type === 'bullets') {
      this.renderBullets(slide, element, x, y, w, h);
    } else if (element.element_type === 'image') {
      // Image rendering placeholder — requires image data or URL
      this.renderImagePlaceholder(slide, element, x, y, w, h);
    } else if (element.element_type === 'chart') {
      // Chart rendering placeholder — PptxGenJS has native chart support
      this.renderChartPlaceholder(slide, element, x, y, w, h);
    } else {
      // Text element (headline, body, card_title, etc.)
      this.renderText(slide, element, x, y, w, h);
    }
  }

  private renderText(
    slide: PptxGenJS.Slide,
    element: RenderElement,
    x: number, y: number, w: number, h: number,
  ): void {
    const style = element.style;
    const text = typeof element.content === 'string' ? element.content : '';

    slide.addText(text, {
      x, y, w, h,
      fontSize: style?.font_size_pt || 18,
      fontFace: style?.font_family || this.fontFamily,
      color: this.resolveColor(style?.font_color || '#333333'),
      bold: style?.bold || false,
      align: (style?.alignment as PptxGenJS.HAlign) || 'left',
      valign: this.mapValign(style?.vertical_alignment),
      lineSpacingMultiple: style?.line_spacing || 1.15,
      wrap: true,
    });
  }

  private renderBullets(
    slide: PptxGenJS.Slide,
    element: RenderElement,
    x: number, y: number, w: number, h: number,
  ): void {
    const style = element.style;
    const items = Array.isArray(element.content) ? element.content : [];

    const textObjects: PptxGenJS.TextProps[] = items.map((item) => ({
      text: item,
      options: {
        fontSize: style?.font_size_pt || 16,
        fontFace: style?.font_family || this.fontFamily,
        color: this.resolveColor(style?.font_color || '#374151'),
        bullet: true,
        lineSpacingMultiple: style?.line_spacing || 1.4,
      },
    }));

    if (textObjects.length > 0) {
      slide.addText(textObjects, { x, y, w, h, wrap: true });
    }
  }

  private renderShape(
    slide: PptxGenJS.Slide,
    element: RenderElement,
    x: number, y: number, w: number, h: number,
  ): void {
    const content = element.content as Record<string, unknown>;
    const fill = this.resolveColor(String(content.fill || '#f3f4f6'));
    const radius = Number(content.corner_radius_cm || 0);

    slide.addShape(pptxShapeType(radius), {
      x, y, w, h,
      fill: { color: fill },
      rectRadius: radius > 0 ? cmToInch(radius) : undefined,
    });
  }

  private renderImagePlaceholder(
    slide: PptxGenJS.Slide,
    element: RenderElement,
    x: number, y: number, w: number, h: number,
  ): void {
    // Placeholder — actual implementation will receive image data/URL
    const content = element.content as Record<string, unknown>;
    const desc = String(content.description || 'Image');

    slide.addShape('rect', {
      x, y, w, h,
      fill: { color: 'F0F0F0' },
    });
    slide.addText(`[Image: ${desc.substring(0, 60)}]`, {
      x, y, w, h,
      fontSize: 10,
      color: '999999',
      align: 'center',
      valign: 'middle',
    });
  }

  private renderChartPlaceholder(
    slide: PptxGenJS.Slide,
    element: RenderElement,
    x: number, y: number, w: number, h: number,
  ): void {
    // Placeholder — PptxGenJS supports bar, line, pie, doughnut, area, scatter
    slide.addShape('rect', {
      x, y, w, h,
      fill: { color: 'FAFAFA' },
      line: { color: 'DDDDDD', width: 1 },
    });
    slide.addText('[Chart]', {
      x, y, w, h,
      fontSize: 12,
      color: '999999',
      align: 'center',
      valign: 'middle',
    });
  }

  private resolveColor(color: string): string {
    // Strip # prefix for PptxGenJS
    const resolved = color === 'accent' ? this.accentColor : color;
    return resolved.replace(/^#/, '');
  }

  private mapValign(va?: string): 'top' | 'middle' | 'bottom' {
    if (va === 'middle') return 'middle';
    if (va === 'bottom') return 'bottom';
    return 'top';
  }
}

function pptxShapeType(cornerRadius: number): string {
  return cornerRadius > 0 ? 'roundRect' : 'rect';
}
