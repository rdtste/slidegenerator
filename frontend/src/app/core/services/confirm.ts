import { Injectable, signal } from '@angular/core';

export interface ConfirmRequest {
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
}

@Injectable({ providedIn: 'root' })
export class ConfirmService {
  readonly visible = signal(false);
  readonly message = signal('');
  readonly confirmLabel = signal('Ja');
  readonly cancelLabel = signal('Abbrechen');

  private resolver?: (result: boolean) => void;

  confirm(request: ConfirmRequest): Promise<boolean> {
    this.message.set(request.message);
    this.confirmLabel.set(request.confirmLabel ?? 'Ja');
    this.cancelLabel.set(request.cancelLabel ?? 'Abbrechen');
    this.visible.set(true);
    return new Promise<boolean>((resolve) => {
      this.resolver = resolve;
    });
  }

  accept(): void {
    this.visible.set(false);
    this.resolver?.(true);
    this.resolver = undefined;
  }

  decline(): void {
    this.visible.set(false);
    this.resolver?.(false);
    this.resolver = undefined;
  }
}
