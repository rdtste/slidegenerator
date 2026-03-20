import { Component, inject, signal, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { ApiService } from '../../core/services/api';
import { ChatState } from '../../core/services/chat';

interface ProgressEntry {
  icon: string;
  label: string;
  status: 'pending' | 'active' | 'done';
}

@Component({
  selector: 'app-export-panel',
  templateUrl: './export-panel.html',
  styleUrl: './export-panel.scss',
})
export class ExportPanel implements OnDestroy {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);
  readonly state = inject(ChatState);
  readonly exportStatus = signal('');
  readonly exporting = signal(false);
  readonly exportProgress = signal(0);
  readonly exportMessage = signal('');
  readonly progressEntries = signal<ProgressEntry[]>([]);

  private eventSource: EventSource | null = null;
  private currentActiveKey = '';

  download(format: string): void {
    const markdown = this.state.markdown();
    if (!markdown) return;

    if (format === 'pdf') {
      this.downloadDirect(format);
      return;
    }

    this.exporting.set(true);
    this.exportProgress.set(0);
    this.exportMessage.set('Export wird gestartet...');
    this.exportStatus.set('');
    this.currentActiveKey = '';
    this.progressEntries.set([
      { icon: '📄', label: 'Verbindung wird hergestellt...', status: 'active' },
    ]);

    this.api.startExport(markdown, this.state.selectedTemplateId(), format).subscribe({
      next: ({ jobId }) => this.connectProgress(jobId),
      error: (err) => {
        this.exportStatus.set(`Fehler: ${err.error?.detail ?? err.message}`);
        this.exporting.set(false);
      },
    });
  }

  selectSlide(index: number): void {
    this.state.selectedSlideIndex.set(index);
  }

  ngOnDestroy(): void {
    this.closeEventSource();
  }

  private connectProgress(jobId: string): void {
    this.closeEventSource();
    const url = this.api.getExportProgressUrl(jobId);
    const source = new EventSource(url);
    this.eventSource = source;

    source.addEventListener('progress', (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      if (data.progress != null && data.progress >= 0) {
        this.exportProgress.set(data.progress);
      }
      this.handleProgressEvent(data.step, data.message ?? '');
      this.cdr.markForCheck();
    });

    source.addEventListener('complete', (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      this.exportProgress.set(100);
      this.finishAllEntries();
      this.exportMessage.set('Download wird vorbereitet...');
      source.close();
      this.eventSource = null;

      this.cdr.markForCheck();
      this.api.downloadExport(jobId).subscribe({
        next: (response) => {
          const blob = response.body;
          if (!blob) return;
          this.triggerDownload(blob, data.filename || 'presentation.pptx');
          this.exportStatus.set('PPTX heruntergeladen.');
          this.exporting.set(false);
        },
        error: () => {
          this.exportStatus.set('Fehler beim Herunterladen der Datei.');
          this.exporting.set(false);
        },
      });
    });

    source.addEventListener('fail', (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      this.exportStatus.set(`Fehler: ${data.detail ?? 'Unbekannter Fehler'}`);
      this.exporting.set(false);
      source.close();
      this.eventSource = null;
      this.cdr.markForCheck();
    });

    source.onerror = () => {
      if (this.exporting()) {
        this.exportStatus.set('Verbindung zum Server verloren.');
        this.exporting.set(false);
      }
      source.close();
      this.eventSource = null;
      this.cdr.markForCheck();
    };
  }

  private handleProgressEvent(step: string, message: string): void {
    const key = `${step}:${message}`;
    if (key === this.currentActiveKey) return;

    const icon = this.iconForStep(step);
    const label = message || step;

    // Mark previous active entry as done
    const entries = this.progressEntries().map(e =>
      e.status === 'active' ? { ...e, status: 'done' as const } : e,
    );

    // Add new entry or update last if same step category
    entries.push({ icon, label, status: 'active' });
    this.currentActiveKey = key;
    this.exportMessage.set(label);
    this.progressEntries.set(entries);
  }

  private iconForStep(step: string): string {
    switch (step) {
      case 'parsing': case 'parsed': return '📄';
      case 'template': return '🎨';
      case 'slide': return '📑';
      case 'image': return '🖼️';
      case 'chart': return '📊';
      case 'saving': return '💾';
      default: return '⚙️';
    }
  }

  private finishAllEntries(): void {
    this.progressEntries.set(
      this.progressEntries().map(e => ({ ...e, status: 'done' as const })),
    );
  }

  private downloadDirect(format: string): void {
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

  private closeEventSource(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
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
