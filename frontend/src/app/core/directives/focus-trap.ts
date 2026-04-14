import { Directive, ElementRef, AfterViewInit, OnDestroy } from '@angular/core';

@Directive({
  selector: '[appFocusTrap]',
})
export class FocusTrap implements AfterViewInit, OnDestroy {
  private keydownHandler = (e: KeyboardEvent) => this.onKeydown(e);

  constructor(private el: ElementRef<HTMLElement>) {}

  ngAfterViewInit(): void {
    this.el.nativeElement.addEventListener('keydown', this.keydownHandler);
    const first = this.getFocusableElements()[0];
    first?.focus();
  }

  ngOnDestroy(): void {
    this.el.nativeElement.removeEventListener('keydown', this.keydownHandler);
  }

  private onKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Tab') return;

    const focusable = this.getFocusableElements();
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

  private getFocusableElements(): HTMLElement[] {
    return Array.from(
      this.el.nativeElement.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    );
  }
}
