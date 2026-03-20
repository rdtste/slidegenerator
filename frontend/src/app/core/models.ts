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
  needsClarification: boolean;
  questions: string;
}

export type TemplateScope = 'global' | 'session';

export type Audience = 'team' | 'management' | 'casual';

export type ImageStyle = 'photo' | 'illustration' | 'minimal' | 'none';

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
}

export interface SelectOption {
  id: string;
  name: string;
}
