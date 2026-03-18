import { Component, inject, computed, effect, OnDestroy, ViewChild, ElementRef } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ChatState } from '../../core/services/chat';
import { ApiService } from '../../core/services/api';

@Component({
  selector: 'app-preview',
  imports: [],
  templateUrl: './preview.html',
  styleUrl: './preview.scss',
})
export class Preview implements OnDestroy {
  private readonly state = inject(ChatState);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly api = inject(ApiService);
  private blobUrl: string | null = null;
  private lastTemplateId: string | undefined;

  @ViewChild('previewFrame') previewFrame!: ElementRef<HTMLIFrameElement>;

  readonly hasContent = computed(() => this.state.previewHtml().length > 0);

  readonly iframeSrc = computed<SafeResourceUrl | undefined>(() => {
    const html = this.state.previewHtml();
    if (!html) return undefined;

    if (this.blobUrl) {
      URL.revokeObjectURL(this.blobUrl);
    }
    const blob = new Blob([html], { type: 'text/html' });
    this.blobUrl = URL.createObjectURL(blob);
    return this.sanitizer.bypassSecurityTrustResourceUrl(this.blobUrl);
  });

  constructor() {
    effect(() => {
      const idx = this.state.selectedSlideIndex();
      this.scrollToSlide(idx);
    });

    // Re-render preview when template changes and markdown exists
    effect(() => {
      const templateId = this.state.selectedTemplateId();
      const markdown = this.state.markdown();
      if (!markdown) {
        this.lastTemplateId = templateId;
        return;
      }
      // Skip initial run / only react to actual template changes
      if (this.lastTemplateId === undefined) {
        this.lastTemplateId = templateId;
        return;
      }
      if (templateId === this.lastTemplateId) return;
      this.lastTemplateId = templateId;
      this.refreshPreviewForTemplate(markdown, templateId);
    });
  }

  private refreshPreviewForTemplate(markdown: string, templateId: string): void {
    const tid = templateId !== 'default' ? templateId : undefined;
    this.api.preview(markdown, tid).subscribe({
      next: (html) => this.state.previewHtml.set(html),
      error: (err) => console.error('[Preview] Template-Wechsel Fehler:', err),
    });
  }

  private scrollToSlide(index: number): void {
    const iframe = this.previewFrame?.nativeElement;
    if (iframe?.contentWindow) {
      iframe.contentWindow.postMessage({ slideIndex: index }, '*');
    }
  }

  ngOnDestroy(): void {
    if (this.blobUrl) {
      URL.revokeObjectURL(this.blobUrl);
    }
  }
}
