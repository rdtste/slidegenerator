import { Injectable, signal, computed } from '@angular/core';
import { ChatMessage, SlideContent, TemplateInfo } from '../models';

@Injectable({ providedIn: 'root' })
export class ChatState {
  readonly messages = signal<ChatMessage[]>([
    { role: 'system', content: 'Beschreibe deine Präsentation. Zum Beispiel: "Erstelle eine 10-seitige Präsentation über unsere Q1-Ergebnisse 2026."' },
  ]);
  readonly markdown = signal('');
  readonly slides = signal<SlideContent[]>([]);
  readonly loading = signal(false);
  readonly templates = signal<TemplateInfo[]>([]);
  readonly selectedTemplateId = signal('default');
  readonly previewHtml = signal('');
  readonly selectedSlideIndex = signal(0);

  readonly slideCount = computed(() => this.slides().length);
  readonly hasMarkdown = computed(() => this.markdown().trim().length > 0);

  addMessage(msg: ChatMessage): void {
    this.messages.update((msgs) => [...msgs, msg]);
  }

  updateMarkdown(md: string): void {
    this.markdown.set(md);
  }
}
