import { Component, inject, signal, output, OnInit, OnDestroy, DestroyRef } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription } from 'rxjs';
import { ApiService } from '../../core/services/api';
import { ChatState } from '../../core/services/chat';
import { ConfirmService } from '../../core/services/confirm';
import { FocusTrap } from '../../core/directives/focus-trap';

@Component({
  selector: 'app-template-management',
  imports: [FocusTrap],
  templateUrl: './template-management.html',
  styleUrl: './template-management.scss',
})
export class TemplateManagement implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly confirmService = inject(ConfirmService);
  readonly state = inject(ChatState);

  private uploadSub?: Subscription;

  readonly status = signal('');
  readonly learning = signal(false);
  readonly learnResult = signal('');
  readonly closed = output<void>();

  ngOnInit(): void {
    this.loadTemplates();
  }

  loadTemplates(): void {
    this.api.getTemplates().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
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

    this.api.learnTemplate(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
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

  async deleteTemplate(id: string, event: Event): Promise<void> {
    event.stopPropagation();
    const template = this.state.templates().find(t => t.id === id);
    const name = template?.name ?? id;
    const ok = await this.confirmService.confirm({
      message: `Template "${name}" wirklich löschen?`,
      confirmLabel: 'Löschen',
    });
    if (!ok) return;
    this.api.deleteTemplate(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
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
    this.api.setTemplateScope(id, newScope).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
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

  ngOnDestroy(): void {
    this.uploadSub?.unsubscribe();
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      this.close();
    }
  }
}
