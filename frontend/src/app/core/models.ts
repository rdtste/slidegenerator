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

export interface TemplateInfo {
  id: string;
  name: string;
  description: string;
  layouts: string[];
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
