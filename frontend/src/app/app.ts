import { Component, inject, OnInit, OnDestroy, signal, effect, untracked, ElementRef, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
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

  readonly editingSlide = signal(false);
  readonly slideEditValue = signal('');
  readonly copied = signal(false);
  readonly showTemplateManager = signal(false);
  readonly templateProfile = signal<TemplateProfile | undefined>(undefined);
  readonly templatePreviewLoading = signal(false);
  readonly previewLoading = signal(false);
  readonly previewError = signal('');

  @ViewChild('slideIframe') private slideIframeRef?: ElementRef<HTMLIFrameElement>;
  private previewSub?: Subscription;

  readonly audienceOptions: Array<{ id: Audience; icon: string; title: string; desc: string }> = [
    { id: 'team', icon: '👥', title: 'Team', desc: 'Intern, klar, handlungsorientiert' },
    { id: 'management', icon: '📊', title: 'Management', desc: 'Executive, verdichtet, entscheidungsorientiert' },
    { id: 'customer', icon: '🤝', title: 'Kunde / Extern', desc: 'Hochwertig, überzeugend, professionell' },
    { id: 'workshop', icon: '💡', title: 'Workshop', desc: 'Offen, visuell, kollaborativ' },
  ];

  readonly fontOptions = [
    'Arial', 'Calibri', 'Helvetica', 'Georgia', 'Verdana', 'Roboto', 'Open Sans',
  ];

  readonly colorPresets: Array<{ name: string; color: string }> = [
    { name: 'Blau', color: '#7BA7D9' },
    { name: 'Grün', color: '#8CC5A2' },
    { name: 'Korall', color: '#E8998D' },
    { name: 'Lila', color: '#B8A9D4' },
    { name: 'Gold', color: '#D4C07A' },
    { name: 'Türkis', color: '#7EC8C8' },
    { name: 'Rose', color: '#D4A0B9' },
    { name: 'Grau', color: '#A0ADB8' },
  ];

  readonly showCustomColor = signal(false);

  readonly imageStyleOptions: Array<{ id: ImageStyle; icon: string; title: string; desc: string }> = [
    { id: 'photo', icon: '📸', title: 'Fotografie', desc: 'Realistisch, hochwertig, emotional' },
    { id: 'illustration', icon: '🎨', title: 'Illustration', desc: 'Erklärend, konzeptionell, editorial' },
    { id: 'minimal', icon: '◻️', title: 'Minimal', desc: 'Reduzierte Formen, Icons, typografisch' },
    { id: 'data_visual', icon: '📊', title: 'Data Visual', desc: 'Diagramme, KPI, Timeline, Prozesse' },
    { id: 'none', icon: '🚫', title: 'Keine Bilder', desc: 'Reine Typografie und Layoutstruktur' },
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

    // Trigger slide preview when step 3 is active (handles direct signal writes from chat component)
    effect(() => {
      const step = this.state.currentStep();
      // Track slide index so preview refreshes when navigating slides
      this.state.selectedSlideIndex();
      const md = this.state.currentSlideMarkdown();
      if (step === 3 && md) {
        untracked(() => this.loadSlidePreview());
      }
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
    // Effect will trigger loadSlidePreview since currentSlideMarkdown changed
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
    this.previewSub?.unsubscribe();
  }

  loadSlidePreview(): void {
    const md = this.state.currentSlideMarkdown();
    if (!md) return;

    const slideMd = md.includes('marp:') ? md : `---\nmarp: true\n---\n\n${md}`;
    const templateId = this.state.selectedTemplateId();
    const isDefault = templateId === 'default';

    this.previewLoading.set(true);
    this.previewError.set('');
    this.previewSub?.unsubscribe();

    this.previewSub = this.api.preview(
      slideMd,
      isDefault ? undefined : templateId,
      isDefault ? this.state.customColor() : undefined,
      isDefault ? this.state.customFont() : undefined,
    ).subscribe({
      next: (html) => {
        this.previewLoading.set(false);
        this.writeToIframe(html);
      },
      error: (err) => {
        this.previewLoading.set(false);
        this.previewError.set(`Vorschau-Fehler: ${err.message || 'Unbekannt'}`);
        console.error('[SlidePreview] Fehler:', err);
      },
    });
  }

  private writeToIframe(html: string): void {
    // Use requestAnimationFrame to ensure the iframe element exists in the DOM
    requestAnimationFrame(() => {
      const iframe = this.slideIframeRef?.nativeElement;
      if (!iframe) {
        // Retry once more after another frame (iframe may not be rendered yet)
        requestAnimationFrame(() => {
          const retryIframe = this.slideIframeRef?.nativeElement;
          if (retryIframe) {
            this.setIframeContent(retryIframe, html);
          }
        });
        return;
      }
      this.setIframeContent(iframe, html);
    });
  }

  private setIframeContent(iframe: HTMLIFrameElement, html: string): void {
    const doc = iframe.contentDocument ?? iframe.contentWindow?.document;
    if (doc) {
      doc.open();
      doc.write(html);
      doc.close();
    }
  }
}
