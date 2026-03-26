import { Component, inject, computed } from '@angular/core';
import { SlicePipe } from '@angular/common';
import { ChatState } from '../../core/services/chat';

@Component({
  selector: 'app-preview',
  imports: [SlicePipe],
  templateUrl: './preview.html',
  styleUrl: './preview.scss',
})
export class Preview {
  readonly state = inject(ChatState);

  readonly hasContent = computed(() => this.state.slides().length > 0);

  readonly accentColor = computed(() => {
    return this.state.customColor() || '#7BA7D9';
  });
}
