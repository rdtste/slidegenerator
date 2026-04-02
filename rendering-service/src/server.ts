/**
 * Rendering Service — high-fidelity PPTX generation.
 *
 * Design Mode: PptxGenJS (creation from scratch, pixel-perfect control)
 * Template Mode: pptx-automizer (manipulate existing .pptx templates)
 */

import express from 'express';
import { renderRoutes } from './routes/render.js';
import { healthRoutes } from './routes/health.js';
import { logger } from './utils/logger.js';

const app = express();
const PORT = parseInt(process.env.PORT || '8001', 10);

app.use(express.json({ limit: '50mb' }));

// Routes
app.use('/api/v1', renderRoutes);
app.use('/', healthRoutes);

app.listen(PORT, () => {
  logger.info(`Rendering service listening on :${PORT}`);
});

export { app };
