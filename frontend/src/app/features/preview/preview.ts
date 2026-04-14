import { Component, inject, computed } from '@angular/core';
import { ChatState } from '../../core/services/chat';

@Component({
  selector: 'app-preview',
  imports: [],
  templateUrl: './preview.html',
  styleUrl: './preview.scss',
})
export class Preview {
  readonly state = inject(ChatState);

  readonly hasContent = computed(() => this.state.slides().length > 0);

  readonly accentColor = computed(() => {
    return this.state.customColor() || '#7BA7D9';
  });

  selectSlide(index: number, event: Event): void {
    event.preventDefault();
    this.state.selectedSlideIndex.set(index);
  }

  onListKeydown(event: KeyboardEvent): void {
    const slides = this.state.slides();
    if (!slides.length) return;
    const idx = this.state.selectedSlideIndex();
    let next = idx;
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
      next = Math.min(idx + 1, slides.length - 1);
    } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
      next = Math.max(idx - 1, 0);
    } else if (event.key === 'Home') {
      next = 0;
    } else if (event.key === 'End') {
      next = slides.length - 1;
    } else {
      return;
    }
    event.preventDefault();
    this.state.selectedSlideIndex.set(next);
    // Move focus to newly selected option
    const container = event.currentTarget as HTMLElement;
    const options = container.querySelectorAll('[role="option"]');
    (options[next] as HTMLElement)?.focus();
  }
}
