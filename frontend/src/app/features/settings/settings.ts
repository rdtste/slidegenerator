import { Component, inject, signal, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api';
import { SelectOption } from '../../core/models';

@Component({
  selector: 'app-settings',
  imports: [FormsModule],
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
})
export class Settings implements OnInit {
  private readonly api = inject(ApiService);

  readonly open = signal(false);
  readonly saving = signal(false);
  readonly status = signal('');

  readonly gcpProjectId = signal('');
  readonly gcpRegion = signal('');
  readonly model = signal('');
  readonly availableRegions = signal<SelectOption[]>([]);
  readonly availableModels = signal<SelectOption[]>([]);

  ngOnInit(): void {
    this.loadSettings();
  }

  toggle(): void {
    this.open.update((v) => !v);
    if (this.open()) {
      this.loadSettings();
    }
  }

  loadSettings(): void {
    this.api.getSettings().subscribe({
      next: (settings) => {
        this.gcpProjectId.set(settings.gcpProjectId);
        this.gcpRegion.set(settings.gcpRegion);
        this.model.set(settings.model);
        this.availableRegions.set(settings.availableRegions);
        this.availableModels.set(settings.availableModels);
      },
      error: () => this.status.set('Einstellungen konnten nicht geladen werden.'),
    });
  }

  save(): void {
    this.saving.set(true);
    this.status.set('');
    this.api.updateSettings({
      gcpProjectId: this.gcpProjectId(),
      gcpRegion: this.gcpRegion(),
      model: this.model(),
    }).subscribe({
      next: () => {
        this.status.set('Gespeichert.');
        this.saving.set(false);
        setTimeout(() => this.status.set(''), 2000);
      },
      error: (err) => {
        this.status.set(`Fehler: ${err.error?.detail ?? err.message}`);
        this.saving.set(false);
      },
    });
  }
}
