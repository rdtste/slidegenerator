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
  readonly clarifying = signal(false);
  private pendingPrompt = '';
  private pendingFiles: File[] = [];

  send(): void {
    const text = this.prompt().trim();
    if (!text || this.state.loading()) return;

    if (this.clarifying()) {
      this.handleClarificationAnswer(text);
      return;
    }

    const files = this.attachedFiles();
    const fileNames = files.map((f) => f.name);
    const msgText = fileNames.length
      ? `${text}\n\n📎 ${fileNames.join(', ')}`
      : text;

    this.state.addMessage({ role: 'user', content: msgText });
    this.prompt.set('');
    this.attachedFiles.set([]);
    this.state.loading.set(true);

    this.pendingPrompt = text;
    this.pendingFiles = files;

    this.api.clarify(text, files.length ? files : undefined).subscribe({
      next: (res) => {
        if (res.needsClarification) {
          this.state.addMessage({ role: 'assistant', content: res.questions });
          this.clarifying.set(true);
          this.state.loading.set(false);
        } else {
          this.generateSlides(text, files);
        }
      },
      error: () => {
        this.generateSlides(text, files);
      },
    });
  }

  skipClarification(): void {
    if (this.state.loading()) return;
    this.clarifying.set(false);
    this.state.addMessage({ role: 'user', content: '⏭ Übersprungen — direkt generieren' });
    this.state.loading.set(true);
    this.generateSlides(this.pendingPrompt, this.pendingFiles);
  }

  private handleClarificationAnswer(answer: string): void {
    this.state.addMessage({ role: 'user', content: answer });
    this.prompt.set('');
    this.clarifying.set(false);
    this.state.loading.set(true);

    const enrichedPrompt = `${this.pendingPrompt}\n\nZUSÄTZLICHE ANGABEN DES NUTZERS:\n${answer}`;
    this.generateSlides(enrichedPrompt, this.pendingFiles);
  }

  private generateSlides(prompt: string, files: File[]): void {
    const templateId = this.state.selectedTemplateId();
    const audience = this.state.audience();
    const imageStyle = this.state.imageStyle();
    this.api.chat(prompt, files.length ? files : undefined, templateId !== 'default' ? templateId : undefined, audience, imageStyle).subscribe({
      next: (res) => {
        this.state.markdown.set(res.markdown);
        this.state.slides.set(res.slides);
        this.state.addMessage({
          role: 'assistant',
          content: `${res.slides.length} Folien generiert. Prüfe das Markdown und exportiere.`,
        });
        this.state.loading.set(false);
        this.pendingPrompt = '';
        this.pendingFiles = [];
        this.refreshPreview(res.markdown);
        this.state.currentStep.set(3);
      },
      error: (err) => {
        const detail = err.error?.detail ?? err.message ?? 'Unbekannter Fehler';
        this.state.addMessage({ role: 'error', content: `Fehler: ${detail}` });
        this.state.loading.set(false);
        this.pendingPrompt = '';
        this.pendingFiles = [];
      },
    });
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
