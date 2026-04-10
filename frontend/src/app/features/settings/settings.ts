import { Component, inject, signal, OnInit, OnDestroy, ElementRef, HostListener } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api';
import { SelectOption } from '../../core/models';

@Component({
  selector: 'app-settings',
  imports: [FormsModule],
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
})
export class Settings implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly el = inject(ElementRef);

  readonly open = signal(false);
  readonly saving = signal(false);
  readonly saved = signal(false);
  readonly status = signal('');

  readonly gcpProjectId = signal('');
  readonly gcpRegion = signal('');
  readonly model = signal('');
  readonly availableRegions = signal<SelectOption[]>([]);
  readonly availableModels = signal<SelectOption[]>([]);
  readonly presentationCount = signal(0);

  private clickOutsideHandler = (e: MouseEvent) => {
    if (this.open() && !this.el.nativeElement.contains(e.target)) {
      this.open.set(false);
    }
  };

  ngOnInit(): void {
    this.loadSettings();
    document.addEventListener('click', this.clickOutsideHandler, true);
  }

  ngOnDestroy(): void {
    document.removeEventListener('click', this.clickOutsideHandler, true);
  }

  @HostListener('keydown.escape')
  onEscape(): void {
    if (this.open()) this.open.set(false);
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
        this.presentationCount.set(settings.presentationCount ?? 0);
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
        this.saving.set(false);
        this.saved.set(true);
        this.status.set('');
        setTimeout(() => this.saved.set(false), 2000);
      },
      error: (err) => {
        this.status.set(`Fehler: ${err.error?.detail ?? err.message}`);
        this.saving.set(false);
      },
    });
  }
}
