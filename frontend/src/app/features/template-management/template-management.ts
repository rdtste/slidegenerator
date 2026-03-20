import { Component, inject, signal, output, OnInit } from '@angular/core';
import { ApiService } from '../../core/services/api';
import { ChatState } from '../../core/services/chat';

@Component({
  selector: 'app-template-management',
  templateUrl: './template-management.html',
  styleUrl: './template-management.scss',
})
export class TemplateManagement implements OnInit {
  private readonly api = inject(ApiService);
  readonly state = inject(ChatState);

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

    this.status.set('Template wird hochgeladen...');
    this.api.uploadTemplate(file).subscribe({
      next: (template) => {
        this.status.set(`"${template.name}" hochgeladen. Wird automatisch gelernt...`);
        this.loadTemplates();
        this.state.selectedTemplateId.set(template.id);
      },
      error: (err) => {
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

  deleteTemplate(id: string, event: Event): void {
    event.stopPropagation();
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
}
