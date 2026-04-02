/**
 * Shared PresentationSpec Domain Model (TypeScript mirror).
 *
 * This MUST stay in sync with shared/domain/presentation_spec.py.
 * The Python pipeline produces PresentationSpec, the TS render-service consumes it.
 */

import { z } from 'zod';

// ── Enums ────────────────────────────────────────────────────────────────────

export const RenderMode = z.enum(['design', 'template']);
export type RenderMode = z.infer<typeof RenderMode>;

export const SlideIntent = z.enum([
  'hero', 'section', 'statement', 'bullets', 'cards', 'kpi',
  'split', 'compare', 'timeline', 'process', 'chart',
  'visual_hero', 'agenda', 'closing',
]);
export type SlideIntent = z.infer<typeof SlideIntent>;

export const VisualAssetType = z.enum([
  'none', 'photo', 'illustration', 'icon', 'chart', 'diagram',
]);

export const VisualAssetRole = z.enum([
  'none', 'hero', 'supporting', 'evidence',
]);

export const ChartType = z.enum([
  'bar', 'line', 'pie', 'donut', 'stacked_bar', 'horizontal_bar',
]);

export const ContentBlockType = z.enum([
  'text', 'bullets', 'card', 'kpi', 'quote',
  'comparison_column', 'timeline_entry', 'process_step',
]);

// ── Content Blocks ───────────────────────────────────────────────────────────

export const BulletItemSchema = z.object({
  bold_prefix: z.string().default(''),
  text: z.string(),
});

export const ContentBlockSchema = z.object({
  block_type: ContentBlockType,
  text: z.string().default(''),
  items: z.array(BulletItemSchema).default([]),
  title: z.string().default(''),
  body: z.string().default(''),
  icon_emoji: z.string().default(''),
  label: z.string().default(''),
  value: z.string().default(''),
  trend: z.string().default(''),
  delta: z.string().default(''),
  attribution: z.string().default(''),
  column_label: z.string().default(''),
  column_items: z.array(z.string()).default([]),
  date: z.string().default(''),
  description: z.string().default(''),
  step_number: z.number().default(0),
});

// ── Visual Asset ─────────────────────────────────────────────────────────────

export const ChartSpecSchema = z.object({
  chart_type: ChartType,
  title: z.string().default(''),
  labels: z.array(z.string()).default([]),
  datasets: z.array(z.record(z.any())).default([]),
});

export const VisualAssetSchema = z.object({
  asset_type: VisualAssetType.default('none'),
  role: VisualAssetRole.default('none'),
  generation_prompt: z.string().default(''),
  image_url: z.string().default(''),
  chart_spec: ChartSpecSchema.nullable().default(null),
});

// ── Slide Spec ───────────────────────────────────────────────────────────────

export const SlideSpecSchema = z.object({
  position: z.number(),
  intent: SlideIntent,
  render_mode: RenderMode.default('design'),
  headline: z.string().default(''),
  subheadline: z.string().default(''),
  core_message: z.string().default(''),
  speaker_notes: z.string().default(''),
  content_blocks: z.array(ContentBlockSchema).default([]),
  visual: VisualAssetSchema.default({}),
  transition_hint: z.string().default(''),
});

// ── Quality Score ────────────────────────────────────────────────────────────

export const QualityDimensionSchema = z.object({
  name: z.string(),
  score: z.number(),
  details: z.string().default(''),
});

export const QualityScoreSchema = z.object({
  total: z.number().default(0),
  passed: z.boolean().default(false),
  dimensions: z.array(QualityDimensionSchema).default([]),
});

// ── Template Descriptor ──────────────────────────────────────────────────────

export const PlaceholderSlotSchema = z.object({
  slot_id: z.string(),
  slot_type: z.string(),
  x_cm: z.number().default(0),
  y_cm: z.number().default(0),
  width_cm: z.number().default(0),
  height_cm: z.number().default(0),
});

export const TemplateLayoutSchema = z.object({
  layout_index: z.number(),
  layout_name: z.string(),
  supported_intents: z.array(SlideIntent).default([]),
  placeholders: z.array(PlaceholderSlotSchema).default([]),
});

export const TemplateDescriptorSchema = z.object({
  template_id: z.string(),
  filename: z.string(),
  layouts: z.array(TemplateLayoutSchema).default([]),
  color_scheme: z.record(z.string()).default({}),
  font_scheme: z.record(z.string()).default({}),
});

// ── Presentation Spec (top-level) ────────────────────────────────────────────

export const PresentationSpecSchema = z.object({
  title: z.string().default(''),
  render_mode: RenderMode.default('design'),
  template_id: z.string().nullable().default(null),
  accent_color: z.string().default('#2563EB'),
  font_family: z.string().default('Calibri'),
  slides: z.array(SlideSpecSchema).default([]),
  quality: QualityScoreSchema.default({}),
  template: TemplateDescriptorSchema.nullable().default(null),
});

export type PresentationSpec = z.infer<typeof PresentationSpecSchema>;
export type SlideSpec = z.infer<typeof SlideSpecSchema>;
export type ContentBlock = z.infer<typeof ContentBlockSchema>;
export type VisualAsset = z.infer<typeof VisualAssetSchema>;
export type ChartSpec = z.infer<typeof ChartSpecSchema>;
export type QualityScore = z.infer<typeof QualityScoreSchema>;
export type TemplateDescriptor = z.infer<typeof TemplateDescriptorSchema>;
