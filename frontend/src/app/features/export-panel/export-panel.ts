import { Component, inject, signal, computed, OnDestroy, ChangeDetectorRef } from '@angular/core';
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
  readonly retryAvailable = computed(() => {
    const status = this.exportStatus();
    return !this.exporting() && (status.startsWith('Fehler') || status.includes('verloren'));
  });

  private eventSource: EventSource | null = null;
  private currentActiveKey = '';
  private reconnectAttempts = 0;
  private currentJobId = '';

  downloadV2(): void {
    const briefing = this.state.briefing();
    if (!briefing) {
      this.exportStatus.set('Fehler: Kein Briefing vorhanden. Bitte zuerst eine Praesentation generieren.');
      return;
    }

    // Check if pre-generated PPTX is available and slides weren't edited
    const pregenKey = this.state.pregenKey();
    if (pregenKey && !this.state.slidesEdited()) {
      this.tryPregenDownload(pregenKey, briefing);
      return;
    }

    this.startFreshV2Export(briefing);
  }

  private tryPregenDownload(key: string, briefing: string): void {
    this.exporting.set(true);
    this.exportProgress.set(50);
    this.exportMessage.set('Vorbereitete Praesentation wird geladen…');
    this.exportStatus.set('');

    this.api.getPregenStatus(key).subscribe({
      next: (status) => {
        if (status.status === 'complete') {
          // Pre-gen ready — download directly
          this.exportProgress.set(90);
          this.exportMessage.set('Download wird vorbereitet…');
          this.api.downloadPregen(key).subscribe({
            next: (response) => {
              const blob = response.body;
              if (!blob) {
                this.startFreshV2Export(briefing);
                return;
              }
              this.triggerDownload(blob, 'presentation_v2.pptx');
              this.exportProgress.set(100);
              this.exportStatus.set('PPTX heruntergeladen (vorberechnet).');
              this.exporting.set(false);
            },
            error: () => this.startFreshV2Export(briefing),
          });
        } else if (status.status === 'processing' && status.jobId) {
          // Pre-gen still running — connect to its progress stream
          this.exportProgress.set(0);
          this.exportMessage.set('V2 AI-Pipeline laeuft bereits…');
          this.progressEntries.set([]);
          this.currentActiveKey = '';
          this.reconnectAttempts = 0;
          this.currentJobId = status.jobId;
          this.connectProgress(status.jobId);
        } else {
          // Pre-gen failed or missing — start fresh
          this.startFreshV2Export(briefing);
        }
      },
      error: () => this.startFreshV2Export(briefing),
    });
  }

  private startFreshV2Export(briefing: string): void {
    this.exporting.set(true);
    this.exportProgress.set(0);
    this.exportMessage.set('V2 AI-Pipeline wird gestartet…');
    this.exportStatus.set('');
    this.currentActiveKey = '';
    this.progressEntries.set([]);
    this.reconnectAttempts = 0;

    const templateId = this.state.selectedTemplateId();
    const isDefault = templateId === 'default';

    this.api.startV2Export(
      briefing,
      this.state.audience(),
      this.state.imageStyle(),
      isDefault ? this.state.customColor() : undefined,
      isDefault ? this.state.customFont() : undefined,
      isDefault ? undefined : templateId,
    ).subscribe({
      next: ({ jobId }) => {
        this.currentJobId = jobId;
        this.connectProgress(jobId);
      },
      error: (err) => {
        this.exportStatus.set(`Fehler: ${err.error?.detail ?? err.message}`);
        this.exporting.set(false);
      },
    });
  }

  download(format: string): void {
    if (format === 'pdf') {
      this.downloadDirect(format);
    }
  }

  getTemplateName(): string {
    const id = this.state.selectedTemplateId();
    if (id === 'default') return 'Standard-Design';
    return this.state.templates().find(t => t.id === id)?.name ?? id;
  }

  isSuccess(): boolean {
    const s = this.exportStatus();
    return s.includes('heruntergeladen') && !s.includes('Warnung') && !s.includes('Fehler');
  }

  isWarning(): boolean {
    return this.exportStatus().includes('Warnung');
  }

  isError(): boolean {
    return this.exportStatus().startsWith('Fehler');
  }

  ngOnDestroy(): void {
    this.closeEventSource();
  }

  private connectProgress(jobId: string): void {
    this.closeEventSource();
    // On reconnect, reset progress UI to avoid duplicate entries from ReplaySubject
    if (this.reconnectAttempts > 0) {
      this.progressEntries.set([]);
      this.currentActiveKey = '';
    }
    const url = this.api.getExportProgressUrl(jobId);
    const source = new EventSource(url);
    this.eventSource = source;

    source.addEventListener('heartbeat', () => {
      // Keep-alive from server, ignore
    });

    source.addEventListener('progress', (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      if (data.step === 'heartbeat') return;
      if (data.progress != null && data.progress >= 0) {
        this.exportProgress.set(data.progress);
      }
      this.handleProgressEvent(data.step, data.message ?? '');
      if (data.step === 'warning' && data.message) {
        this.exportStatus.set(`Warnung: ${data.message}`);
      }
      this.cdr.markForCheck();
    });

    source.addEventListener('qa_result', (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      const status = data.status === 'passed' ? 'done' : 'active';
      const icon = data.status === 'passed' ? '\u2705' : '\u26A0\uFE0F';
      const label = data.message || 'QA abgeschlossen';
      const entries = this.progressEntries().map(entry =>
        entry.status === 'active' ? { ...entry, status: 'done' as const } : entry,
      );
      entries.push({ icon, label, status: status === 'done' ? 'done' : 'active' });
      this.progressEntries.set(entries);
      this.exportMessage.set(label);
      this.cdr.markForCheck();
    });

    source.addEventListener('generation_warnings', (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      const count = typeof data.count === 'number' ? data.count : 0;
      const detail = typeof data.detail === 'string' ? data.detail : 'Es wurden Warnungen erkannt.';
      this.handleProgressEvent('warning', detail);
      if (count > 0) {
        this.exportStatus.set(`Warnung: ${count} Problem(e) bei Bildgenerierung.`);
      }
      this.cdr.markForCheck();
    });

    source.addEventListener('complete', (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      const warningCount = typeof data.warning_count === 'number' ? data.warning_count : 0;
      this.exportProgress.set(100);
      this.finishAllEntries();
      this.exportMessage.set('Präsentation ist fertig — Download startet…');
      source.close();
      this.eventSource = null;

      this.cdr.markForCheck();
      this.api.downloadExport(jobId).subscribe({
        next: (response) => {
          const blob = response.body;
          if (!blob) return;
          this.triggerDownload(blob, data.filename || 'presentation.pptx');
          if (warningCount > 0) {
            this.exportStatus.set(`PPTX heruntergeladen (${warningCount} Warnung(en) bei Bild/Layout-Generierung).`);
          } else {
            this.exportStatus.set('PPTX heruntergeladen.');
          }
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
      source.close();
      this.eventSource = null;
      if (this.exporting() && this.reconnectAttempts < 3) {
        this.reconnectAttempts++;
        this.exportMessage.set(`Verbindung unterbrochen — Wiederverbindung (${this.reconnectAttempts}/3)…`);
        this.cdr.markForCheck();
        setTimeout(() => {
          if (this.exporting()) {
            this.connectProgress(this.currentJobId);
          }
        }, 2000);
      } else if (this.exporting()) {
        this.exportStatus.set('Verbindung zum Server verloren. Bitte erneut versuchen.');
        this.exporting.set(false);
        this.cdr.markForCheck();
      }
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
      case 'validating': return '🔍';
      case 'parsing': case 'parsed': return '📄';
      case 'template': case 'template_check': return '🎨';
      case 'slide': return '📑';
      case 'image': return '🖼️';
      case 'warning': return '⚠️';
      case 'chart': return '📊';
      case 'saving': return '💾';
      case 'qa_start': case 'qa_convert': return '🔍';
      case 'qa_check': return '🔎';
      case 'qa_fixing': return '🔧';
      case 'qa_pass': return '✅';
      case 'qa_done': case 'qa_skipped': return '📋';
      // V2 pipeline stages
      case 'stage_1': return '🔍';
      case 'stage_2': return '📖';
      case 'stage_3': return '📐';
      case 'stage_4': return '✅';
      case 'stage_5': return '✍️';
      case 'stage_6': return '📏';
      case 'stage_7': case 'rendering': return '🎨';
      case 'stage_8': return '🔎';
      case 'quality': return '📊';
      case 'done': return '🎉';
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
    this.exportProgress.set(0);
    this.progressEntries.set([{ icon: '📄', label: `${format.toUpperCase()} wird erstellt…`, status: 'active' }]);
    this.exportStatus.set(`${format.toUpperCase()} wird aus ${this.state.slides().length} Folien erstellt…`);

    this.api.exportPresentation(markdown, this.state.selectedTemplateId(), format).subscribe({
      next: (response) => {
        const blob = response.body;
        if (!blob) return;
        const ext = format === 'pptx' ? '.pptx' : '.pdf';
        this.triggerDownload(blob, `presentation${ext}`);
        this.exportProgress.set(100);
        this.finishAllEntries();
        this.exportStatus.set(`${format.toUpperCase()} heruntergeladen.`);
        this.exporting.set(false);
      },
      error: (err) => {
        this.progressEntries.set([]);
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
