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

  send(): void {
    const text = this.prompt().trim();
    if (!text || this.state.loading()) return;

    const files = this.attachedFiles();
    const fileNames = files.map((f) => f.name);
    const msgText = fileNames.length
      ? `${text}\n\n📎 ${fileNames.join(', ')}`
      : text;

    this.state.addMessage({ role: 'user', content: msgText });
    this.prompt.set('');
    this.attachedFiles.set([]);
    this.state.loading.set(true);

    const templateId = this.state.selectedTemplateId();
    this.api.chat(text, files, templateId !== 'default' ? templateId : undefined).subscribe({
      next: (res) => {
        this.state.markdown.set(res.markdown);
        this.state.slides.set(res.slides);
        this.state.addMessage({
          role: 'assistant',
          content: `${res.slides.length} Folien generiert. Prüfe das Markdown und exportiere.`,
        });
        this.state.loading.set(false);
        this.refreshPreview(res.markdown);
      },
      error: (err) => {
        const detail = err.error?.detail ?? err.message ?? 'Unbekannter Fehler';
        this.state.addMessage({ role: 'error', content: `Fehler: ${detail}` });
        this.state.loading.set(false);
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
