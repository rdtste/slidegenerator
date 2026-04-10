export interface SlideContent {
  layout: string;
  title: string;
  subtitle: string;
  body: string;
  bullets: string[];
  notes: string;
  imageDescription: string;
  leftColumn: string;
  rightColumn: string;
}

export interface ChatResponse {
  markdown: string;
  slides: SlideContent[];
}

export interface ClarifyResponse {
  readyToGenerate: boolean;
  message: string;
  conversation: Array<{ role: string; content: string }>;
  briefing?: string;
}

export type TemplateScope = 'global' | 'session';

export type Audience = 'team' | 'management' | 'customer' | 'workshop';

export type ImageStyle = 'photo' | 'illustration' | 'minimal' | 'data_visual' | 'none';

export interface TemplateInfo {
  id: string;
  name: string;
  description: string;
  layouts: string[];
  scope: TemplateScope;
  sessionId?: string;
}

export interface LearnResult {
  learned: boolean;
  layouts_classified: number;
  supported_types: string[];
  design_personality: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'error';
  content: string;
}

export interface LlmSettings {
  gcpProjectId: string;
  gcpRegion: string;
  model: string;
  availableRegions: SelectOption[];
  availableModels: SelectOption[];
  presentationCount: number;
}

export interface SelectOption {
  id: string;
  name: string;
}

export interface KeyPoint {
  point: string;
  status: 'covered' | 'partial' | 'missing';
  slideIndices: number[];
  explanation: string;
}

export interface NotesCoverage {
  keyPoints: KeyPoint[];
  coveredCount: number;
  totalCount: number;
}

export interface TemplateColorDna {
  primary: string;
  accent1: string;
  accent2: string;
  accent3: string;
  accent4: string;
  accent5: string;
  accent6: string;
  background: string;
  text: string;
  heading: string;
  chart_colors: string[];
}

export interface TemplateTypographyDna {
  heading_font: string;
  body_font: string;
  heading_sizes_pt: number[];
  body_sizes_pt: number[];
}

export interface TemplateLayoutCatalogEntry {
  layout_index: number;
  layout_name: string;
  mapped_type: string;
  description: string;
  recommended_usage: string;
  max_bullets: number;
  max_chars_per_bullet: number;
  title_max_chars: number;
}

export interface TemplateProfile {
  template_id: string;
  template_name: string;
  description: string;
  design_personality: string;
  slide_width_cm: number;
  slide_height_cm: number;
  color_dna: TemplateColorDna;
  typography_dna: TemplateTypographyDna;
  layout_catalog: TemplateLayoutCatalogEntry[];
  supported_layout_types: string[];
  guidelines: string;
  learned_at: string;
}
