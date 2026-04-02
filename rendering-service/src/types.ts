/**
 * Shared types for the rendering service.
 * These mirror the Python RenderInstruction schema from the pptx-service.
 */

import { z } from 'zod';

export const ElementPositionSchema = z.object({
  left_cm: z.number(),
  top_cm: z.number(),
  width_cm: z.number(),
  height_cm: z.number(),
});

export const ElementStyleSchema = z.object({
  font_family: z.string().default('Calibri'),
  font_size_pt: z.number().default(18),
  font_color: z.string().default('#333333'),
  bold: z.boolean().default(false),
  italic: z.boolean().default(false),
  alignment: z.enum(['left', 'center', 'right']).default('left'),
  vertical_alignment: z.enum(['top', 'middle', 'bottom']).default('top'),
  line_spacing: z.number().default(1.15),
});

export const RenderElementSchema = z.object({
  element_type: z.string(),
  content: z.union([z.string(), z.array(z.string()), z.record(z.any())]),
  position: ElementPositionSchema,
  style: ElementStyleSchema.optional(),
});

export const RenderInstructionSchema = z.object({
  slide_index: z.number(),
  slide_type: z.string(),
  layout_id: z.string(),
  accent_color: z.string().default('#2563EB'),
  background_color: z.string().default('#FFFFFF'),
  elements: z.array(RenderElementSchema),
});

export const RenderRequestSchema = z.object({
  mode: z.enum(['design', 'template']).default('design'),
  instructions: z.array(RenderInstructionSchema),
  template_path: z.string().optional(),
  accent_color: z.string().default('#2563EB'),
  font_family: z.string().default('Calibri'),
});

export type ElementPosition = z.infer<typeof ElementPositionSchema>;
export type ElementStyle = z.infer<typeof ElementStyleSchema>;
export type RenderElement = z.infer<typeof RenderElementSchema>;
export type RenderInstruction = z.infer<typeof RenderInstructionSchema>;
export type RenderRequest = z.infer<typeof RenderRequestSchema>;
