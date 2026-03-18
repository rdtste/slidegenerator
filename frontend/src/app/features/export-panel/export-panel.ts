import { Component, inject, signal, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api';
import { ChatState } from '../../core/services/chat';

@Component({
  selector: 'app-export-panel',
  imports: [FormsModule],
  templateUrl: './export-panel.html',
  styleUrl: './export-panel.scss',
})
export class ExportPanel implements OnInit {
  private readonly api = inject(ApiService);
  readonly state = inject(ChatState);
  readonly exportStatus = signal('');
  readonly exporting = signal(false);

  ngOnInit(): void {
    this.loadTemplates();
  }

  loadTemplates(): void {
    this.api.getTemplates().subscribe({
      next: (templates) => this.state.templates.set(templates),
      error: () => this.exportStatus.set('Templates konnten nicht geladen werden.'),
    });
  }

  onTemplateUpload(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.exportStatus.set('Template wird hochgeladen...');
    this.api.uploadTemplate(file).subscribe({
      next: (template) => {
        this.exportStatus.set(`Template "${template.name}" hochgeladen.`);
        this.loadTemplates();
        this.state.selectedTemplateId.set(template.id);
      },
      error: (err) => {
        this.exportStatus.set(`Upload-Fehler: ${err.error?.detail ?? err.message}`);
      },
    });
    input.value = '';
  }

  selectTemplate(id: string): void {
    this.state.selectedTemplateId.set(id);
  }

  deleteTemplate(id: string, event: Event): void {
    event.stopPropagation();
    this.api.deleteTemplate(id).subscribe({
      next: () => {
        if (this.state.selectedTemplateId() === id) {
          this.state.selectedTemplateId.set('default');
        }
        this.loadTemplates();
        this.exportStatus.set('Template gel\u00f6scht.');
      },
      error: (err) => {
        this.exportStatus.set(`L\u00f6sch-Fehler: ${err.error?.detail ?? err.message}`);
      },
    });
  }

  download(format: string): void {
    const markdown = this.state.markdown();
    if (!markdown) return;

    this.exporting.set(true);
    this.exportStatus.set(`${format.toUpperCase()} wird generiert...`);

    this.api.exportPresentation(markdown, this.state.selectedTemplateId(), format).subscribe({
      next: (response) => {
        const blob = response.body;
        if (!blob) return;

        const ext = format === 'pptx' ? '.pptx' : format === 'pdf' ? '.pdf' : '.html';
        this.triggerDownload(blob, `presentation${ext}`);
        this.exportStatus.set(`${format.toUpperCase()} heruntergeladen.`);
        this.exporting.set(false);
      },
      error: (err) => {
        this.exportStatus.set(`Fehler: ${err.error?.detail ?? err.message}`);
        this.exporting.set(false);
      },
    });
  }

  selectSlide(index: number): void {
    this.state.selectedSlideIndex.set(index);
  }

  private triggerDownload(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }
}
