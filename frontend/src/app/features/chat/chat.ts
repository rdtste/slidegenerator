import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api';
import { ChatState } from '../../core/services/chat';

@Component({
  selector: 'app-chat',
  imports: [FormsModule],
  templateUrl: './chat.html',
  styleUrl: './chat.scss',
})
export class Chat {
  private readonly api = inject(ApiService);
  readonly state = inject(ChatState);
  readonly prompt = signal('');
  readonly attachedFiles = signal<File[]>([]);
  readonly conversing = signal(false);

  private llmConversation: Array<{ role: string; content: string }> = [];
  private firstMessageFiles: File[] = [];

  send(): void {
    const text = this.prompt().trim();
    if (!text || this.state.loading()) return;

    const isFirstMessage = !this.conversing();
    const files = isFirstMessage ? this.attachedFiles() : [];
    const fileNames = files.map((f) => f.name);
    const msgText = fileNames.length ? `${text}\n\n📎 ${fileNames.join(', ')}` : text;

    this.state.addMessage({ role: 'user', content: msgText });
    this.prompt.set('');
    this.state.loading.set(true);

    if (isFirstMessage) {
      this.attachedFiles.set([]);
      this.firstMessageFiles = files;
    }

    this.api
      .clarify(
        text,
        isFirstMessage && files.length ? files : undefined,
        this.llmConversation.length ? this.llmConversation : undefined,
      )
      .subscribe({
        next: (res) => {
          this.llmConversation = res.conversation;

          if (res.readyToGenerate) {
            if (res.message) {
              this.state.addMessage({ role: 'assistant', content: res.message });
            }
            this.conversing.set(false);
            this.generateSlides(res.briefing ?? text);
          } else {
            this.state.addMessage({ role: 'assistant', content: res.message });
            this.conversing.set(true);
            this.state.loading.set(false);
          }
        },
        error: () => {
          if (isFirstMessage) {
            this.generateSlides(text, files);
          } else {
            this.state.addMessage({
              role: 'error',
              content: 'Fehler bei der Beratung. Versuche es erneut.',
            });
            this.state.loading.set(false);
          }
        },
      });
  }

  skipConversation(): void {
    if (this.state.loading()) return;
    this.conversing.set(false);
    this.state.addMessage({ role: 'user', content: '⏭ Direkt generieren' });
    this.state.loading.set(true);

    const firstUserMsg = this.llmConversation.find((m) => m.role === 'user')?.content ?? '';
    this.generateSlides(firstUserMsg || this.prompt(), this.firstMessageFiles);
  }

  private generateSlides(briefing: string, files?: File[]): void {
    const templateId = this.state.selectedTemplateId();
    const audience = this.state.audience();
    const imageStyle = this.state.imageStyle();
    this.api
      .chat(
        briefing,
        files?.length ? files : undefined,
        templateId !== 'default' ? templateId : undefined,
        audience,
        imageStyle,
      )
      .subscribe({
        next: (res) => {
          this.state.markdown.set(res.markdown);
          this.state.slides.set(res.slides);
          this.state.addMessage({
            role: 'assistant',
            content: `✅ Deine Präsentation mit ${res.slides.length} Folien ist fertig! Du kannst sie jetzt prüfen und bearbeiten.`,
          });
          this.state.loading.set(false);
          this.resetConversation();
          this.refreshPreview(res.markdown);
          this.state.currentStep.set(3);
        },
        error: (err) => {
          const detail = err.error?.detail ?? err.message ?? 'Unbekannter Fehler';
          this.state.addMessage({ role: 'error', content: `Fehler: ${detail}` });
          this.state.loading.set(false);
          this.resetConversation();
        },
      });
  }

  private resetConversation(): void {
    this.llmConversation = [];
    this.firstMessageFiles = [];
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  onFileSelect(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    if (files.length) {
      this.attachedFiles.update((prev) => [...prev, ...files]);
    }
    input.value = '';
  }

  removeFile(index: number): void {
    this.attachedFiles.update((prev) => prev.filter((_, i) => i !== index));
  }

  private refreshPreview(markdown: string): void {
    const templateId = this.state.selectedTemplateId();
    this.api.preview(markdown, templateId !== 'default' ? templateId : undefined).subscribe({
      next: (html) => {
        this.state.previewHtml.set(html);
      },
      error: (err) => {
        console.error('[Preview] Fehler:', err);
        this.state.addMessage({ role: 'error', content: `Vorschau-Fehler: ${err.message}` });
      },
    });
  }
}
