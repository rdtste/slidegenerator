import { Component, inject, OnInit, OnDestroy, signal, effect, computed, untracked, ElementRef, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { Chat } from './features/chat/chat';
import { ExportPanel } from './features/export-panel/export-panel';
import { TemplateManagement } from './features/template-management/template-management';
import { Settings } from './features/settings/settings';
import { ChatState } from './core/services/chat';
import { ApiService } from './core/services/api';
import { Audience, ImageStyle, TemplateProfile } from './core/models';

@Component({
  selector: 'app-root',
  imports: [FormsModule, Chat, ExportPanel, TemplateManagement, Settings],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit, OnDestroy {
  readonly state = inject(ChatState);
  private readonly api = inject(ApiService);
  private readonly sanitizer = inject(DomSanitizer);
  private slideBlobUrl: string | null = null;

  readonly editingSlide = signal(false);
  readonly slideEditValue = signal('');
  readonly copied = signal(false);
  readonly showTemplateManager = signal(false);
  readonly templateProfile = signal<TemplateProfile | undefined>(undefined);
  readonly templatePreviewLoading = signal(false);

  readonly slideIframeSrc = signal<SafeResourceUrl | undefined>(undefined);

  readonly audienceOptions: Array<{ id: Audience; icon: string; title: string; desc: string }> = [
    { id: 'team', icon: '👥', title: 'Team', desc: 'Intern, pragmatisch, handlungsorientiert' },
    { id: 'management', icon: '📊', title: 'Management', desc: 'Strategisch, KPI-fokussiert, entscheidungsorientiert' },
    { id: 'casual', icon: '💬', title: 'Casual', desc: 'Locker, visuell, für Meetings & Workshops' },
  ];

  readonly imageStyleOptions: Array<{ id: ImageStyle; icon: string; title: string; desc: string }> = [
    { id: 'photo', icon: '📸', title: 'Fotografie', desc: 'Realistische Fotos und Aufnahmen' },
    { id: 'illustration', icon: '🎨', title: 'Illustration', desc: 'Grafiken, Diagramme und Zeichnungen' },
    { id: 'minimal', icon: '◻️', title: 'Minimal', desc: 'Icons und abstrakte Formen' },
    { id: 'none', icon: '🚫', title: 'Keine Bilder', desc: 'Nur Text, keine Bildfolien' },
  ];

  constructor() {
    // Template sneak preview: fetch profile data when template selection changes
    effect(() => {
      const templateId = this.state.selectedTemplateId();
      if (templateId === 'default') {
        this.templateProfile.set(undefined);
        return;
      }
      this.templatePreviewLoading.set(true);
      untracked(() => {
        this.api.getTemplateProfile(templateId).subscribe({
          next: (profile) => {
            this.templateProfile.set(profile);
            this.templatePreviewLoading.set(false);
          },
          error: () => {
            this.templateProfile.set(undefined);
            this.templatePreviewLoading.set(false);
          },
        });
      });
    });

    effect(() => {
      const step = this.state.currentStep();
      this.state.selectedSlideIndex();
      const md = this.state.currentSlideMarkdown();
      if (step === 3 && md) {
        const slideMd = md.includes('marp:') ? md : `---\nmarp: true\n---\n\n${md}`;
        const tid = untracked(() => {
          const t = this.state.selectedTemplateId();
          return t !== 'default' ? t : undefined;
        });
        this.api.preview(slideMd, tid).subscribe({
          next: (html) => this.state.slidePreviewHtml.set(html),
          error: (err) => console.error('[SlidePreview] Fehler:', err),
        });
      }
    });

    // Create blob URL for slide preview iframe
    effect(() => {
      const html = this.state.slidePreviewHtml();
      if (this.slideBlobUrl) {
        URL.revokeObjectURL(this.slideBlobUrl);
        this.slideBlobUrl = null;
      }
      if (!html) {
        this.slideIframeSrc.set(undefined);
        return;
      }
      const blob = new Blob([html], { type: 'text/html' });
      this.slideBlobUrl = URL.createObjectURL(blob);
      this.slideIframeSrc.set(
        this.sanitizer.bypassSecurityTrustResourceUrl(this.slideBlobUrl),
      );
    });
  }

  ngOnInit(): void {
    this.loadTemplates();
  }

  loadTemplates(): void {
    this.api.getTemplates().subscribe({
      next: (templates) => this.state.templates.set(templates),
    });
  }

  goToStep(step: number): void {
    if (step >= 3 && !this.state.hasMarkdown()) return;
    this.state.currentStep.set(step);
    if (step === 3) {
      this.editingSlide.set(false);
    }
  }

  prevSlide(): void {
    const idx = this.state.selectedSlideIndex();
    if (idx > 0) {
      this.commitSlideEdit();
      this.state.selectedSlideIndex.set(idx - 1);
    }
  }

  nextSlide(): void {
    const idx = this.state.selectedSlideIndex();
    if (idx < this.state.slideCount() - 1) {
      this.commitSlideEdit();
      this.state.selectedSlideIndex.set(idx + 1);
    }
  }

  goToSlide(idx: number): void {
    this.commitSlideEdit();
    this.state.selectedSlideIndex.set(idx);
  }

  startSlideEdit(): void {
    this.slideEditValue.set(this.state.currentSlideMarkdown());
    this.editingSlide.set(true);
  }

  saveSlideEdit(): void {
    const chunks = [...this.state.slideMarkdowns()];
    const idx = this.state.selectedSlideIndex();
    chunks[idx] = this.slideEditValue();
    this.state.updateMarkdown(chunks.join('\n\n---\n\n'));
    this.editingSlide.set(false);
    // Re-parse slides from updated markdown
    this.refreshFullPreview();
  }

  cancelSlideEdit(): void {
    this.editingSlide.set(false);
  }

  copyAllMarkdown(): void {
    navigator.clipboard.writeText(this.state.markdown()).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    });
  }

  startNew(): void {
    if (this.state.hasMarkdown() && !confirm('Aktuelle Präsentation verwerfen und neu starten?')) {
      return;
    }
    this.state.reset();
    this.templateProfile.set(undefined);
  }

  openTemplateManager(): void {
    this.showTemplateManager.set(true);
  }

  closeTemplateManager(): void {
    this.showTemplateManager.set(false);
  }

  private commitSlideEdit(): void {
    if (this.editingSlide()) {
      this.saveSlideEdit();
    }
  }

  ngOnDestroy(): void {
    if (this.slideBlobUrl) {
      URL.revokeObjectURL(this.slideBlobUrl);
    }
  }

  private refreshFullPreview(): void {
    const md = this.state.markdown();
    if (!md) return;
    const templateId = this.state.selectedTemplateId();
    const tid = templateId !== 'default' ? templateId : undefined;
    this.api.preview(md, tid).subscribe({
      next: (html) => this.state.previewHtml.set(html),
    });
  }
}
