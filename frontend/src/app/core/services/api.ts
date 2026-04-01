import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpResponse, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ChatResponse, ClarifyResponse, TemplateInfo, TemplateProfile, LearnResult, LlmSettings } from '../models';
import { ChatState } from './chat';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseUrl = this.getApiUrl();
  private readonly state = inject(ChatState);

  constructor(private readonly http: HttpClient) {}

  /**
   * Determine API URL dynamically based on current deployment context.
   * - Local dev (port 4200 with separate backend on 3000): use direct URL
   * - Docker Compose (nginx reverse proxy): use relative path
   * - Cloud Run (custom domain): derive backend URL from frontend hostname
   */
  private getApiUrl(): string {
    const { protocol, hostname, port } = window.location;

    // Local development: frontend on 4200, backend on 3000
    if (hostname === 'localhost' && port === '4200') {
      return `http://localhost:3000/api/v1`;
    }

    // Custom domain (internal or external): slidegenerator.xxx → slidegenerator-backend.xxx
    if (hostname.startsWith('slidegenerator.')) {
      const backendHost = hostname.replace('slidegenerator.', 'slidegenerator-backend.');
      return `${protocol}//${backendHost}/api/v1`;
    }

    // Docker Compose / fallback: nginx reverse proxies /api/* → backend:3000
    return '/api/v1';
  }

  private sessionHeaders(): HttpHeaders {
    return new HttpHeaders({ 'x-session-id': this.state.sessionId });
  }

  clarify(
    prompt: string,
    files?: File[],
    conversation?: Array<{ role: string; content: string }>,
  ): Observable<ClarifyResponse> {
    const formData = new FormData();
    formData.append('prompt', prompt);
    if (conversation?.length) {
      formData.append('conversation', JSON.stringify(conversation));
    }
    if (files?.length) {
      for (const file of files) {
        formData.append('files', file);
      }
    }
    return this.http.post<ClarifyResponse>(`${this.baseUrl}/chat/clarify`, formData);
  }

  chat(prompt: string, files?: File[], templateId?: string, audience?: string, imageStyle?: string, customColor?: string, customFont?: string): Observable<ChatResponse> {
    const formData = new FormData();
    formData.append('prompt', prompt);
    if (templateId) {
      formData.append('templateId', templateId);
    }
    if (audience) {
      formData.append('audience', audience);
    }
    if (imageStyle) {
      formData.append('imageStyle', imageStyle);
    }
    if (customColor) {
      formData.append('customColor', customColor);
    }
    if (customFont) {
      formData.append('customFont', customFont);
    }
    if (files?.length) {
      for (const file of files) {
        formData.append('files', file);
      }
    }
    return this.http.post<ChatResponse>(`${this.baseUrl}/chat`, formData);
  }

  preview(markdown: string, templateId?: string, customColor?: string, customFont?: string): Observable<string> {
    return this.http.post(`${this.baseUrl}/preview`, { markdown, templateId, customColor, customFont }, { responseType: 'text' });
  }

  getTemplates(): Observable<TemplateInfo[]> {
    return this.http.get<TemplateInfo[]>(`${this.baseUrl}/templates`, {
      headers: this.sessionHeaders(),
    });
  }

  uploadTemplate(file: File): Observable<TemplateInfo & { learned: boolean; profileSummary?: { layouts_classified: number; supported_types: string[]; design_personality: string } }> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<TemplateInfo & { learned: boolean; profileSummary?: { layouts_classified: number; supported_types: string[]; design_personality: string } }>(`${this.baseUrl}/templates`, formData, {
      headers: this.sessionHeaders(),
    });
  }

  setTemplateScope(id: string, scope: 'global' | 'session'): Observable<TemplateInfo> {
    return this.http.patch<TemplateInfo>(`${this.baseUrl}/templates/${id}/scope`, { scope }, {
      headers: this.sessionHeaders(),
    });
  }

  deleteTemplate(id: string): Observable<unknown> {
    return this.http.delete(`${this.baseUrl}/templates/${id}`);
  }

  learnTemplate(id: string): Observable<LearnResult> {
    return this.http.post<LearnResult>(`${this.baseUrl}/templates/${id}/learn`, {});
  }

  getTemplateProfile(id: string): Observable<TemplateProfile> {
    return this.http.get<TemplateProfile>(`${this.baseUrl}/templates/${id}/profile`);
  }

  exportPresentation(markdown: string, templateId: string, format: string): Observable<HttpResponse<Blob>> {
    return this.http.post(`${this.baseUrl}/export`,
      { markdown, templateId, format },
      { responseType: 'blob', observe: 'response' },
    );
  }

  pregenerateV2(
    prompt: string,
    audience: string,
    imageStyle: string,
    accentColor?: string,
    fontFamily?: string,
    templateId?: string,
  ): Observable<{ key: string }> {
    return this.http.post<{ key: string }>(`${this.baseUrl}/export/pregenerate-v2`, {
      prompt,
      audience,
      imageStyle,
      accentColor,
      fontFamily,
      templateId,
    });
  }

  getPregenStatus(key: string): Observable<{ status: string; jobId?: string }> {
    return this.http.get<{ status: string; jobId?: string }>(`${this.baseUrl}/export/pregenerate-v2/${encodeURIComponent(key)}`);
  }

  downloadPregen(key: string): Observable<HttpResponse<Blob>> {
    return this.http.get(`${this.baseUrl}/export/pregenerate-v2/${encodeURIComponent(key)}/download`, {
      responseType: 'blob',
      observe: 'response',
    });
  }

  startV2Export(
    prompt: string,
    audience: string,
    imageStyle: string,
    accentColor?: string,
    fontFamily?: string,
    templateId?: string,
    documentText?: string,
    mode?: string,
  ): Observable<{ jobId: string }> {
    return this.http.post<{ jobId: string }>(`${this.baseUrl}/export/start-v2`, {
      prompt,
      mode: mode || 'design',
      documentText: documentText || '',
      audience,
      imageStyle,
      accentColor: accentColor || '#2563EB',
      fontFamily: fontFamily || 'Calibri',
      templateId,
    });
  }

  downloadExport(jobId: string): Observable<HttpResponse<Blob>> {
    return this.http.get(`${this.baseUrl}/export/download/${encodeURIComponent(jobId)}`, {
      responseType: 'blob',
      observe: 'response',
    });
  }

  getExportProgressUrl(jobId: string): string {
    return `${this.baseUrl}/export/progress/${encodeURIComponent(jobId)}`;
  }

  getSettings(): Observable<LlmSettings> {
    return this.http.get<LlmSettings>(`${this.baseUrl}/settings`);
  }

  updateSettings(settings: Partial<Pick<LlmSettings, 'gcpProjectId' | 'gcpRegion' | 'model'>>): Observable<LlmSettings> {
    return this.http.put<LlmSettings>(`${this.baseUrl}/settings`, settings);
  }
}
