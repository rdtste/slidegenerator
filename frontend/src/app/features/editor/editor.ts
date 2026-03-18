import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ChatState } from '../../core/services/chat';
import { ApiService } from '../../core/services/api';

@Component({
  selector: 'app-editor',
  imports: [FormsModule],
  templateUrl: './editor.html',
  styleUrl: './editor.scss',
})
export class Editor {
  readonly state = inject(ChatState);
  private readonly api = inject(ApiService);
  readonly isEditing = signal(false);
  readonly editValue = signal('');

  toggleEdit(): void {
    if (this.isEditing()) {
      this.state.updateMarkdown(this.editValue());
      this.isEditing.set(false);
      this.refreshPreview();
    } else {
      this.editValue.set(this.state.markdown());
      this.isEditing.set(true);
    }
  }

  private refreshPreview(): void {
    const md = this.state.markdown();
    if (!md) return;
    this.api.preview(md).subscribe({
      next: (html) => this.state.previewHtml.set(html),
      error: () => {},
    });
  }
}
