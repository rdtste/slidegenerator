import { Injectable, signal, computed } from '@angular/core';
import { ChatMessage, SlideContent, TemplateInfo, Audience, ImageStyle } from '../models';

function generateSessionId(): string {
  return `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

@Injectable({ providedIn: 'root' })
export class ChatState {
  readonly sessionId = generateSessionId();
  readonly currentStep = signal(1);
  readonly audience = signal<Audience>('management');
  readonly imageStyle = signal<ImageStyle>('photo');
  readonly messages = signal<ChatMessage[]>([
    { role: 'system', content: 'Beschreibe deine Präsentation. Zum Beispiel: "Erstelle eine 10-seitige Präsentation über unsere Q1-Ergebnisse 2026."' },
  ]);
  readonly markdown = signal('');
  readonly slides = signal<SlideContent[]>([]);
  readonly loading = signal(false);
  readonly templates = signal<TemplateInfo[]>([]);
  readonly selectedTemplateId = signal('default');
  readonly customColor = signal('#2563eb');
  readonly customFont = signal('Inter');
  readonly previewHtml = signal('');
  readonly selectedSlideIndex = signal(0);
  readonly slidePreviewHtml = signal('');

  readonly slideCount = computed(() => this.slides().length);
  readonly hasMarkdown = computed(() => this.markdown().trim().length > 0);

  readonly slideMarkdowns = computed(() => {
    const md = this.markdown();
    if (!md.trim()) return [];
    // Strip Marp frontmatter (---\n...\n---) before splitting on slide separators
    const withoutFrontmatter = md.replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, '');
    return withoutFrontmatter.split(/^\s*---\s*$/m).filter((s) => s.trim());
  });

  readonly currentSlideMarkdown = computed(() => {
    const chunks = this.slideMarkdowns();
    const idx = this.selectedSlideIndex();
    return chunks[idx] ?? '';
  });

  addMessage(msg: ChatMessage): void {
    this.messages.update((msgs) => [...msgs, msg]);
  }

  updateMarkdown(md: string): void {
    this.markdown.set(md);
  }

  reset(): void {
    this.currentStep.set(1);
    this.audience.set('management');
    this.imageStyle.set('photo');
    this.messages.set([
      { role: 'system', content: 'Beschreibe deine Präsentation. Zum Beispiel: "Erstelle eine 10-seitige Präsentation über unsere Q1-Ergebnisse 2026."' },
    ]);
    this.markdown.set('');
    this.slides.set([]);
    this.loading.set(false);
    this.selectedTemplateId.set('default');
    this.customColor.set('#2563eb');
    this.customFont.set('Inter');
    this.previewHtml.set('');
    this.selectedSlideIndex.set(0);
    this.slidePreviewHtml.set('');
  }
}
