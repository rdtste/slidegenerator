import { Component, inject, signal, output, OnInit, OnDestroy, AfterViewInit, ElementRef, ViewChild } from '@angular/core';
import { Subscription } from 'rxjs';
import { ApiService } from '../../core/services/api';
import { ChatState } from '../../core/services/chat';

@Component({
  selector: 'app-template-management',
  templateUrl: './template-management.html',
  styleUrl: './template-management.scss',
})
export class TemplateManagement implements OnInit, OnDestroy, AfterViewInit {
  private readonly api = inject(ApiService);
  readonly state = inject(ChatState);

  @ViewChild('tmPanel') private tmPanel!: ElementRef<HTMLElement>;
  private uploadSub?: Subscription;

  readonly status = signal('');
  readonly learning = signal(false);
  readonly learnResult = signal('');
  readonly closed = output<void>();

  ngOnInit(): void {
    this.loadTemplates();
  }

  loadTemplates(): void {
    this.api.getTemplates().subscribe({
      next: (templates) => this.state.templates.set(templates),
      error: () => this.status.set('Templates konnten nicht geladen werden.'),
    });
  }

  onUpload(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.status.set('Template wird hochgeladen und analysiert…');
    this.learning.set(true);
    this.uploadSub = this.api.uploadTemplate(file).subscribe({
      next: (result) => {
        this.learning.set(false);
        if (result.learned) {
          this.status.set(`✅ "${result.name}" hochgeladen und vollständig analysiert.`);
          if (result.profileSummary) {
            this.learnResult.set(
              `${result.profileSummary.layouts_classified} Layouts klassifiziert. ` +
              `Typen: ${result.profileSummary.supported_types.join(', ')}`,
            );
          }
        } else {
          this.status.set(`"${result.name}" hochgeladen. Analyse konnte nicht abgeschlossen werden.`);
        }
        this.loadTemplates();
        this.state.selectedTemplateId.set(result.id);
      },
      error: (err) => {
        this.learning.set(false);
        this.status.set(`Upload-Fehler: ${err.error?.detail ?? err.message}`);
      },
    });
    input.value = '';
  }

  learn(id: string, event: Event): void {
    event.stopPropagation();
    this.learning.set(true);
    this.learnResult.set('');
    this.status.set('Template wird gelernt...');

    this.api.learnTemplate(id).subscribe({
      next: (result) => {
        this.learning.set(false);
        this.learnResult.set(
          `${result.layouts_classified} Layouts klassifiziert. Typen: ${result.supported_types.join(', ')}`,
        );
        this.status.set('Template erfolgreich gelernt!');
      },
      error: (err) => {
        this.learning.set(false);
        this.learnResult.set('');
        this.status.set(`Lern-Fehler: ${err.error?.detail ?? err.message}`);
      },
    });
  }

  cancelUpload(): void {
    this.uploadSub?.unsubscribe();
    this.uploadSub = undefined;
    this.learning.set(false);
    this.status.set('Upload abgebrochen.');
  }

  deleteTemplate(id: string, event: Event): void {
    event.stopPropagation();
    const template = this.state.templates().find(t => t.id === id);
    const name = template?.name ?? id;
    if (!confirm(`Template "${name}" wirklich löschen?`)) return;
    this.api.deleteTemplate(id).subscribe({
      next: () => {
        if (this.state.selectedTemplateId() === id) {
          this.state.selectedTemplateId.set('default');
        }
        this.loadTemplates();
        this.status.set('Template gelöscht.');
      },
      error: (err) => {
        this.status.set(`Lösch-Fehler: ${err.error?.detail ?? err.message}`);
      },
    });
  }

  toggleScope(id: string, currentScope: string, event: Event): void {
    event.stopPropagation();
    const newScope = currentScope === 'global' ? 'session' : 'global';
    this.api.setTemplateScope(id, newScope).subscribe({
      next: () => {
        this.loadTemplates();
        this.status.set(
          newScope === 'global'
            ? 'Template für alle Nutzer freigegeben.'
            : 'Template auf aktuelle Session beschränkt.',
        );
      },
      error: (err) => {
        this.status.set(`Scope-Fehler: ${err.error?.detail ?? err.message}`);
      },
    });
  }

  selectTemplate(id: string): void {
    this.state.selectedTemplateId.set(id);
    this.learnResult.set('');
  }

  close(): void {
    this.closed.emit();
  }

  ngAfterViewInit(): void {
    const closeBtn = this.tmPanel?.nativeElement?.querySelector<HTMLElement>('.tm-close');
    closeBtn?.focus();
  }

  ngOnDestroy(): void {
    this.uploadSub?.unsubscribe();
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      this.close();
      return;
    }

    if (event.key === 'Tab') {
      const panel = this.tmPanel?.nativeElement;
      if (!panel) return;

      const focusable = panel.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }
}
