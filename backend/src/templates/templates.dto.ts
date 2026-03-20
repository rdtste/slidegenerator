export type TemplateScope = 'global' | 'session';

export class TemplateInfoDto {
  id!: string;
  name!: string;
  description!: string;
  layouts!: string[];
  scope!: TemplateScope;
  sessionId?: string;
}
