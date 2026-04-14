import { Component, inject } from '@angular/core';
import { ConfirmService } from '../services/confirm';
import { FocusTrap } from '../directives/focus-trap';

@Component({
  selector: 'app-confirm-dialog',
  imports: [FocusTrap],
  template: `
    @if (confirm.visible()) {
      <div class="confirm-overlay" (click)="confirm.decline()" (keydown.escape)="confirm.decline()">
        <div class="confirm-dialog" role="alertdialog" aria-modal="true" [attr.aria-label]="confirm.message()" appFocusTrap (click)="$event.stopPropagation()">
          <p class="confirm-message">{{ confirm.message() }}</p>
          <div class="confirm-actions">
            <button class="confirm-cancel" (click)="confirm.decline()">{{ confirm.cancelLabel() }}</button>
            <button class="confirm-accept" (click)="confirm.accept()">{{ confirm.confirmLabel() }}</button>
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .confirm-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 2000;
    }
    .confirm-dialog {
      background: var(--surface, #1e1e2e);
      border: 1px solid var(--border, #333);
      border-radius: 12px;
      padding: 24px;
      max-width: 400px;
      width: 90%;
    }
    .confirm-message {
      margin: 0 0 20px;
      font-size: 0.95rem;
      color: var(--text, #e0e0e0);
      line-height: 1.5;
    }
    .confirm-actions {
      display: flex;
      gap: 10px;
      justify-content: flex-end;
    }
    .confirm-cancel,
    .confirm-accept {
      border: none;
      border-radius: 8px;
      padding: 10px 20px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
    }
    .confirm-cancel {
      background: var(--surface-hover, #2a2a3e);
      color: var(--text-muted, #999);
      &:hover { background: var(--border, #333); }
    }
    .confirm-accept {
      background: var(--primary, #818cf8);
      color: white;
      &:hover { background: var(--primary-hover, #a5b4fc); }
    }
  `],
})
export class ConfirmDialog {
  readonly confirm = inject(ConfirmService);
}
