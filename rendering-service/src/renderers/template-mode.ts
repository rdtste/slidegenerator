/**
 * Template Mode Renderer — manipulates existing .pptx templates using pptx-automizer.
 *
 * Used when a corporate template is provided. pptx-automizer can:
 * - Open an existing .pptx file
 * - Replace text in placeholders
 * - Replace chart data
 * - Copy/modify slides
 * - Preserve all template formatting and branding
 *
 * pptx-automizer wraps PptxGenJS internally for new element creation.
 */

import Automizer from 'pptx-automizer';
import type { RenderInstruction } from '../types.js';
import { logger } from '../utils/logger.js';

export class TemplateModeRenderer {
  private templatePath: string;

  constructor(templatePath: string) {
    this.templatePath = templatePath;
  }

  async render(instructions: RenderInstruction[], outputPath: string): Promise<void> {
    logger.info(
      `Template mode: rendering ${instructions.length} slides ` +
      `from template ${this.templatePath}`,
    );

    const automizer = new Automizer({
      templateDir: '',
      outputDir: '',
    });

    const pptx = automizer.loadRoot(this.templatePath);

    // TODO: Implement template slot mapping
    // For each instruction:
    // 1. Find matching layout in template
    // 2. Map content to placeholder slots
    // 3. Replace text, chart data, images

    for (const instruction of instructions) {
      await this.renderSlide(pptx, instruction);
    }

    await pptx.write(outputPath);
    logger.info(`Template mode: wrote ${instructions.length} slides to ${outputPath}`);
  }

  private async renderSlide(
    pptx: ReturnType<InstanceType<typeof Automizer>['loadRoot']>,
    instruction: RenderInstruction,
  ): Promise<void> {
    // Placeholder implementation — will be fleshed out with
    // template analysis and slot mapping logic
    logger.debug(`Template mode: slide ${instruction.slide_index} (${instruction.slide_type})`);
  }
}
