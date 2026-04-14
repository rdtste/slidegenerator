import { Component, inject, OnInit, signal, computed, effect, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject, Subscription } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

import { Chat } from './features/chat/chat';
import { Preview } from './features/preview/preview';
import { ExportPanel } from './features/export-panel/export-panel';
import { TemplateManagement } from './features/template-management/template-management';
import { Settings } from './features/settings/settings';
import { FocusTrap } from './core/directives/focus-trap';
import { ConfirmDialog } from './core/components/confirm-dialog';
import { ChatState } from './core/services/chat';
import { ApiService } from './core/services/api';
import { ConfirmService } from './core/services/confirm';
import { Audience, ImageStyle, KeyPoint, NotesCoverage, SlideContent, TemplateProfile } from './core/models';

@Component({
  selector: 'app-root',
  imports: [FormsModule, Chat, Preview, ExportPanel, TemplateManagement, Settings, FocusTrap, ConfirmDialog],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit {
  readonly state = inject(ChatState);
  private readonly api = inject(ApiService);
  private readonly confirmService = inject(ConfirmService);

  readonly editingSlide = signal(false);
  readonly slideEditValue = signal('');
  readonly copied = signal(false);
  readonly showTemplateManager = signal(false);
  readonly showMarkdownImport = signal(false);
  readonly markdownImportValue = signal('');
  readonly pimpImportValue = signal('');
  readonly showNotesImport = signal(false);
  readonly notesImportValue = signal('');
  readonly generatingFromNotes = signal(false);
  readonly pimping = signal(false);
  readonly refining = signal(false);
  readonly refineInstruction = signal('');
  readonly notesCoverage = signal<NotesCoverage | undefined>(undefined);
  readonly coverageLoading = signal(false);
  readonly templateProfile = signal<TemplateProfile | undefined>(undefined);
  readonly templatePreviewLoading = signal(false);
  readonly coverageOpen = signal(false);
  readonly errorStatus = signal('');
  readonly successStatus = signal('');
  readonly templatesLoading = signal(false);
  private readonly profileCache = new Map<string, TemplateProfile>();
  private profileSub?: Subscription;
  private readonly cancelOps$ = new Subject<void>();

  readonly colorValid = computed(() => /^#[0-9A-Fa-f]{6}$/.test(this.state.customColor()));

  private readonly layoutNames: Record<string, string> = {
    title_hero: 'Titelfolie',
    section_divider: 'Abschnitt',
    key_statement: 'Kernaussage',
    bullets_focused: 'Aufzählung',
    three_cards: 'Drei Karten',
    kpi_dashboard: 'KPI-Dashboard',
    image_text_split: 'Bild & Text',
    comparison: 'Vergleich',
    timeline: 'Zeitstrahl',
    process_flow: 'Prozessfluss',
    chart_insight: 'Diagramm',
    image_fullbleed: 'Vollbild',
    agenda: 'Agenda',
    closing: 'Abschluss',
    content: 'Inhalt',
  };

  layoutDisplayName(layout: string): string {
    return this.layoutNames[layout] ?? layout;
  }

  readonly selectedSlide = computed<SlideContent | undefined>(() => {
    const slides = this.state.slides();
    const idx = this.state.selectedSlideIndex();
    return slides[idx];
  });

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
      // Check cache first
      const cached = this.profileCache.get(templateId);
      if (cached) {
        this.templateProfile.set(cached);
        return;
      }
      this.templatePreviewLoading.set(true);
      untracked(() => {
        this.profileSub?.unsubscribe();
        this.profileSub = this.api.getTemplateProfile(templateId).subscribe({
          next: (profile) => {
            this.profileCache.set(templateId, profile);
            this.templateProfile.set(profile);
            this.templatePreviewLoading.set(false);
          },
          error: () => {
            this.templateProfile.set(undefined);
            this.templatePreviewLoading.set(false);
            this.showError('Template-Vorschau konnte nicht geladen werden.');
          },
        });
      });
    });

  }

  private showError(message: string): void {
    this.errorStatus.set(message);
    setTimeout(() => {
      if (this.errorStatus() === message) {
        this.errorStatus.set('');
      }
    }, 6000);
  }

  private showSuccess(message: string): void {
    this.successStatus.set(message);
    setTimeout(() => {
      if (this.successStatus() === message) {
        this.successStatus.set('');
      }
    }, 4000);
  }

  ngOnInit(): void {
    this.loadTemplates();
  }

  private templateRetryCount = 0;

  loadTemplates(): void {
    this.templatesLoading.set(true);
    this.api.getTemplates().subscribe({
      next: (templates) => {
        this.templatesLoading.set(false);
        const hasRealTemplates = templates.some((t) => t.id !== 'default');
        const currentHasReal = this.state.templates().some((t) => t.id !== 'default');

        // Never overwrite a good template list with one that lost templates
        if (hasRealTemplates || !currentHasReal) {
          this.state.templates.set(templates);
        }

        // Preload profiles for all real templates so selection feels instant
        if (hasRealTemplates) {
          for (const t of templates) {
            if (t.id !== 'default' && !this.profileCache.has(t.id)) {
              this.api.getTemplateProfile(t.id).subscribe({
                next: (profile) => this.profileCache.set(t.id, profile),
                error: () => {},
              });
            }
          }
        }

        // GCS FUSE may not be ready yet — retry up to 5 times with increasing delay
        if (!hasRealTemplates && this.templateRetryCount < 5) {
          this.templateRetryCount++;
          const delay = this.templateRetryCount * 2000;
          setTimeout(() => this.loadTemplates(), delay);
        }
      },
      error: () => {
        this.templatesLoading.set(false);
        if (this.templateRetryCount < 5) {
          this.templateRetryCount++;
          setTimeout(() => this.loadTemplates(), 2000);
        }
      },
    });
  }

  goToStep(step: number): void {
    if (step >= 3 && !this.state.hasMarkdown()) return;
    this.state.currentStep.set(step);
    if (step === 3) {
      this.editingSlide.set(false);
    }
    const main = document.getElementById('main-content');
    main?.scrollTo(0, 0);
    main?.focus();
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
    }).catch(() => {
      this.showError('Kopieren fehlgeschlagen. Bitte manuell kopieren.');
    });
  }

  async startNew(): Promise<void> {
    if (this.state.hasMarkdown()) {
      const ok = await this.confirmService.confirm({
        message: 'Aktuelle Präsentation verwerfen und neu starten?',
        confirmLabel: 'Neu starten',
      });
      if (!ok) return;
    }
    // Cancel any in-flight LLM operations
    this.cancelOps$.next();
    this.pimping.set(false);
    this.refining.set(false);
    this.generatingFromNotes.set(false);
    this.state.reset();
    this.templateProfile.set(undefined);
    this.notesCoverage.set(undefined);
    this.coverageOpen.set(false);
    this.refineInstruction.set('');
  }

  importMarkdown(): void {
    const md = this.markdownImportValue().trim();
    if (!md) return;

    this.state.updateMarkdown(md);

    // Parse slides from markdown
    const withoutFrontmatter = md.replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, '');
    const chunks = withoutFrontmatter.split(/^\s*---\s*$/m).filter((s: string) => s.trim());
    const slides = chunks.map((chunk: string) => {
      const lines = chunk.trim().split('\n');
      const titleLine = lines.find((l: string) => l.startsWith('# '));
      const title = titleLine ? titleLine.replace(/^#+\s*/, '') : 'Folie';
      const bullets = lines
        .filter((l: string) => l.startsWith('- '))
        .map((l: string) => l.replace(/^-\s*/, ''));
      const body = lines
        .filter((l: string) => !l.startsWith('#') && !l.startsWith('-') && !l.startsWith('<!--') && l.trim())
        .join(' ')
        .trim();
      return {
        layout: 'content',
        title,
        subtitle: '',
        body,
        bullets,
        notes: '',
        imageDescription: '',
        chartData: '',
        leftColumn: '',
        rightColumn: '',
      };
    });

    this.state.slides.set(slides);

    // Extract topic from slide titles for V2 export briefing
    const titles = slides.map((s) => s.title).filter((t) => t);
    this.state.briefing.set(`Erstelle eine Präsentation mit ${slides.length} Folien zu: ${titles.join(', ')}`);
    this.showMarkdownImport.set(false);
    this.markdownImportValue.set('');
    this.state.currentStep.set(3);
  }

  generateFromNotes(): void {
    const notes = this.notesImportValue().trim();
    if (!notes) return;
    this.generatingFromNotes.set(true);

    const templateId = this.state.selectedTemplateId();
    const audience = this.state.audience();
    const imageStyle = this.state.imageStyle();
    const customColor = templateId === 'default' ? this.state.customColor() : undefined;
    const customFont = templateId === 'default' ? this.state.customFont() : undefined;

    const prompt = `Erstelle eine professionelle Präsentation aus den folgenden Notizen. Extrahiere die Kernaussagen, strukturiere sie logisch und wandle sie in visuell ansprechende Folien um.\n\n${notes}`;

    this.api.chat(
      prompt,
      undefined,
      templateId !== 'default' ? templateId : undefined,
      audience,
      imageStyle,
      customColor,
      customFont,
    ).pipe(takeUntil(this.cancelOps$)).subscribe({
      next: (result) => {
        this.state.updateMarkdown(result.markdown);
        this.state.slides.set(result.slides);
        this.state.selectedSlideIndex.set(0);
        this.state.briefing.set(prompt);
        this.state.sourceNotes.set(notes);
        this.generatingFromNotes.set(false);
        this.showNotesImport.set(false);
        this.notesImportValue.set('');
        this.state.currentStep.set(3);
        this.state.slidesEdited.set(false);
        this.loadNotesCoverage(notes, result.markdown);
        this.triggerPregeneration(prompt);
      },
      error: () => {
        this.generatingFromNotes.set(false);
        this.showError('Slides konnten nicht generiert werden. Bitte erneut versuchen.');
      },
    });
  }

  importPimpAsRaw(): void {
    const md = this.pimpImportValue().trim();
    if (!md) return;
    this.state.updateMarkdown(md);
    const withoutFrontmatter = md.replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, '');
    const chunks = withoutFrontmatter.split(/^\s*---\s*$/m).filter((s: string) => s.trim());
    const slides = chunks.map((chunk: string) => {
      const lines = chunk.trim().split('\n');
      const titleLine = lines.find((l: string) => l.startsWith('# '));
      const title = titleLine ? titleLine.replace(/^#+\s*/, '') : 'Folie';
      const bullets = lines
        .filter((l: string) => l.startsWith('- '))
        .map((l: string) => l.replace(/^-\s*/, ''));
      const body = lines
        .filter((l: string) => !l.startsWith('#') && !l.startsWith('-') && !l.startsWith('<!--') && l.trim())
        .join(' ')
        .trim();
      return { layout: 'content', title, subtitle: '', body, bullets, notes: '', imageDescription: '', chartData: '', leftColumn: '', rightColumn: '' };
    });
    this.state.slides.set(slides);
    const titles = slides.map((s) => s.title).filter((t) => t);
    this.state.briefing.set(`Erstelle eine Präsentation mit ${slides.length} Folien zu: ${titles.join(', ')}`);
    this.showMarkdownImport.set(false);
    this.pimpImportValue.set('');
    this.state.currentStep.set(3);
  }

  importAndPimp(): void {
    const md = this.pimpImportValue().trim();
    if (!md) return;

    // First import the markdown
    this.state.updateMarkdown(md);
    const withoutFrontmatter = md.replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, '');
    const chunks = withoutFrontmatter.split(/^\s*---\s*$/m).filter((s: string) => s.trim());
    const slides = chunks.map((chunk: string) => {
      const lines = chunk.trim().split('\n');
      const titleLine = lines.find((l: string) => l.startsWith('# '));
      const title = titleLine ? titleLine.replace(/^#+\s*/, '') : 'Folie';
      const bullets = lines
        .filter((l: string) => l.startsWith('- '))
        .map((l: string) => l.replace(/^-\s*/, ''));
      return {
        layout: 'content', title, subtitle: '', body: '', bullets,
        notes: '', imageDescription: '', chartData: '', leftColumn: '', rightColumn: '',
      };
    });
    this.state.slides.set(slides);
    this.pimpImportValue.set('');

    // Then immediately pimp
    this.pimping.set(true);

    const templateId = this.state.selectedTemplateId();
    const audience = this.state.audience();
    const imageStyle = this.state.imageStyle();
    const customColor = templateId === 'default' ? this.state.customColor() : undefined;
    const customFont = templateId === 'default' ? this.state.customFont() : undefined;

    this.api.pimpSlides(
      md,
      templateId !== 'default' ? templateId : undefined,
      audience,
      imageStyle,
      customColor,
      customFont,
    ).pipe(takeUntil(this.cancelOps$)).subscribe({
      next: (result) => {
        this.state.updateMarkdown(result.markdown);
        this.state.slides.set(result.slides);
        this.state.selectedSlideIndex.set(0);
        const titles = result.slides.map((s: { title: string }) => s.title).filter((t: string) => t);
        this.state.briefing.set(`Erstelle eine Präsentation mit ${result.slides.length} Folien zu: ${titles.join(', ')}`);
        this.pimping.set(false);
        this.showMarkdownImport.set(false);
        this.state.currentStep.set(3);
      },
      error: () => {
        this.pimping.set(false);
        // Still go to Step 3 with the raw import
        const titles = slides.map((s) => s.title).filter((t) => t);
        this.state.briefing.set(`Erstelle eine Präsentation mit ${slides.length} Folien zu: ${titles.join(', ')}`);
        this.showMarkdownImport.set(false);
        this.state.currentStep.set(3);
        this.showError('KI-Optimierung fehlgeschlagen. Roher Import wurde übernommen.');
      },
    });
  }

  async pimpSlides(): Promise<void> {
    const md = this.state.markdown();
    if (!md) return;
    const ok = await this.confirmService.confirm({
      message: 'Folien mit KI optimieren? Die aktuellen Folien werden dabei ersetzt.',
      confirmLabel: 'Optimieren',
    });
    if (!ok) return;
    this.pimping.set(true);

    const templateId = this.state.selectedTemplateId();
    const audience = this.state.audience();
    const imageStyle = this.state.imageStyle();
    const customColor = templateId === 'default' ? this.state.customColor() : undefined;
    const customFont = templateId === 'default' ? this.state.customFont() : undefined;

    this.api.pimpSlides(
      md,
      templateId !== 'default' ? templateId : undefined,
      audience,
      imageStyle,
      customColor,
      customFont,
    ).pipe(takeUntil(this.cancelOps$)).subscribe({
      next: (result) => {
        this.state.updateMarkdown(result.markdown);
        this.state.slides.set(result.slides);
        this.state.selectedSlideIndex.set(0);
        const titles = result.slides.map((s: { title: string }) => s.title).filter((t: string) => t);
        this.state.briefing.set(`Erstelle eine Präsentation mit ${result.slides.length} Folien zu: ${titles.join(', ')}`);
        this.pimping.set(false);
        this.showSuccess('Folien wurden erfolgreich optimiert.');
      },
      error: () => {
        this.pimping.set(false);
        this.showError('Folien-Optimierung fehlgeschlagen. Bitte erneut versuchen.');
      },
    });
  }

  loadNotesCoverage(notes: string, markdown: string): void {
    this.coverageLoading.set(true);
    this.notesCoverage.set(undefined);
    this.api.notesCoverage(notes, markdown).subscribe({
      next: (coverage) => {
        this.notesCoverage.set(coverage);
        this.coverageOpen.set(true);
        this.coverageLoading.set(false);
      },
      error: () => {
        this.coverageLoading.set(false);
      },
    });
  }

  refineSlides(): void {
    const instruction = this.refineInstruction().trim();
    const md = this.state.markdown();
    if (!instruction || !md) return;
    this.refining.set(true);

    const templateId = this.state.selectedTemplateId();
    const audience = this.state.audience();
    const imageStyle = this.state.imageStyle();
    const customColor = templateId === 'default' ? this.state.customColor() : undefined;
    const customFont = templateId === 'default' ? this.state.customFont() : undefined;

    this.api.refineSlides(
      md,
      instruction,
      templateId !== 'default' ? templateId : undefined,
      audience,
      imageStyle,
      customColor,
      customFont,
    ).pipe(takeUntil(this.cancelOps$)).subscribe({
      next: (result) => {
        this.state.updateMarkdown(result.markdown);
        this.state.slides.set(result.slides);
        this.state.selectedSlideIndex.set(0);
        const titles = result.slides.map((s) => s.title).filter((t) => t);
        this.state.briefing.set(`Erstelle eine Präsentation mit ${result.slides.length} Folien zu: ${titles.join(', ')}`);
        this.refining.set(false);
        this.refineInstruction.set('');
        this.showSuccess('Folien wurden angepasst.');
        // Re-run coverage if we have source notes
        const notes = this.state.sourceNotes();
        if (notes) {
          this.loadNotesCoverage(notes, result.markdown);
        }
      },
      error: () => {
        this.refining.set(false);
        this.showError('Folien konnten nicht angepasst werden. Bitte erneut versuchen.');
      },
    });
  }

  refineFromCoverage(kp: KeyPoint): void {
    const instruction = kp.status === 'missing'
      ? `Integriere den fehlenden Punkt "${kp.point}" als neue Folie an passender Stelle in die Präsentation.`
      : `Stelle den Punkt "${kp.point}" prominenter und vollständiger dar (aktuell nur teilweise in Folie ${kp.slideIndices.join(', ')}).`;
    this.refineInstruction.set(instruction);
    this.refineSlides();
  }

  goToSlideFromCoverage(slideIndex: number): void {
    this.commitSlideEdit();
    // Coverage uses 1-based indices, internal state is 0-based
    const idx = Math.max(0, Math.min(slideIndex - 1, this.state.slideCount() - 1));
    this.state.selectedSlideIndex.set(idx);
  }

  openTemplateManager(): void {
    this.showTemplateManager.set(true);
  }

  closeTemplateManager(): void {
    this.showTemplateManager.set(false);
    this.templateRetryCount = 0;
    this.loadTemplates();
  }

  private commitSlideEdit(): void {
    if (this.editingSlide()) {
      this.saveSlideEdit();
    }
  }

  private triggerPregeneration(briefing: string): void {
    const templateId = this.state.selectedTemplateId();
    const isDefault = templateId === 'default';
    this.api.pregenerateV2(
      briefing,
      this.state.audience(),
      this.state.imageStyle(),
      isDefault ? this.state.customColor() : undefined,
      isDefault ? this.state.customFont() : undefined,
      isDefault ? undefined : templateId,
    ).subscribe({
      next: ({ key }) => this.state.pregenKey.set(key),
      error: () => {},
    });
  }

}
