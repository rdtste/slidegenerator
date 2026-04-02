import { Router, Request, Response } from 'express';
import { v4 as uuidv4 } from 'uuid';
import { RenderRequestSchema } from '../types.js';
import { DesignModeRenderer } from '../renderers/design-mode.js';
import { TemplateModeRenderer } from '../renderers/template-mode.js';
import { logger } from '../utils/logger.js';
import path from 'path';
import fs from 'fs';
import os from 'os';

export const renderRoutes = Router();

renderRoutes.post('/render', async (req: Request, res: Response) => {
  const parsed = RenderRequestSchema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid request', details: parsed.error.issues });
    return;
  }

  const request = parsed.data;
  const outputDir = path.join(os.tmpdir(), 'rendering-service', uuidv4());
  fs.mkdirSync(outputDir, { recursive: true });
  const outputPath = path.join(outputDir, 'presentation.pptx');

  try {
    const startTime = Date.now();

    if (request.mode === 'template' && request.template_path) {
      const renderer = new TemplateModeRenderer(request.template_path);
      await renderer.render(request.instructions, outputPath);
    } else {
      const renderer = new DesignModeRenderer(
        request.accent_color,
        request.font_family,
      );
      await renderer.render(request.instructions, outputPath);
    }

    const elapsed = Date.now() - startTime;
    logger.info(`Rendered ${request.instructions.length} slides in ${elapsed}ms (${request.mode} mode)`);

    res.download(outputPath, 'presentation.pptx', (err) => {
      if (err) {
        logger.error('Download error:', err);
      }
      // Cleanup
      fs.rmSync(outputDir, { recursive: true, force: true });
    });
  } catch (err) {
    logger.error('Render error:', err);
    fs.rmSync(outputDir, { recursive: true, force: true });
    res.status(500).json({ error: 'Rendering failed', message: String(err) });
  }
});
