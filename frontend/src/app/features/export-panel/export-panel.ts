import { Component, inject, signal } from '@angular/core';
import { ApiService } from '../../core/services/api';
import { ChatState } from '../../core/services/chat';

@Component({
  selector: 'app-export-panel',
  templateUrl: './export-panel.html',
  styleUrl: './export-panel.scss',
})
export class ExportPanel {
  private readonly api = inject(ApiService);
  readonly state = inject(ChatState);
  readonly exportStatus = signal('');
  readonly exporting = signal(false);

  download(format: string): void {
    const markdown = this.state.markdown();
    if (!markdown) return;

    this.exporting.set(true);
    this.exportStatus.set(`${format.toUpperCase()} wird generiert...`);

    this.api.exportPresentation(markdown, this.state.selectedTemplateId(), format).subscribe({
      next: (response) => {
        const blob = response.body;
        if (!blob) return;

        const ext = format === 'pptx' ? '.pptx' : '.pdf';
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
