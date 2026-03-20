import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpResponse, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ChatResponse, ClarifyResponse, TemplateInfo, LearnResult, LlmSettings } from '../models';
import { ChatState } from './chat';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseUrl = environment.apiUrl;
  private readonly state = inject(ChatState);

  constructor(private readonly http: HttpClient) {}

  private sessionHeaders(): HttpHeaders {
    return new HttpHeaders({ 'x-session-id': this.state.sessionId });
  }

  clarify(prompt: string, files?: File[]): Observable<ClarifyResponse> {
    const formData = new FormData();
    formData.append('prompt', prompt);
    if (files?.length) {
      for (const file of files) {
        formData.append('files', file);
      }
    }
    return this.http.post<ClarifyResponse>(`${this.baseUrl}/chat/clarify`, formData);
  }

  chat(prompt: string, files?: File[], templateId?: string, audience?: string, imageStyle?: string): Observable<ChatResponse> {
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
    if (files?.length) {
      for (const file of files) {
        formData.append('files', file);
      }
    }
    return this.http.post<ChatResponse>(`${this.baseUrl}/chat`, formData);
  }

  preview(markdown: string, templateId?: string): Observable<string> {
    return this.http.post(`${this.baseUrl}/preview`, { markdown, templateId }, { responseType: 'text' });
  }

  getTemplates(): Observable<TemplateInfo[]> {
    return this.http.get<TemplateInfo[]>(`${this.baseUrl}/templates`, {
      headers: this.sessionHeaders(),
    });
  }

  uploadTemplate(file: File): Observable<TemplateInfo> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<TemplateInfo>(`${this.baseUrl}/templates`, formData, {
      headers: this.sessionHeaders(),
    });
  }

  setTemplateScope(id: string, scope: 'global' | 'session'): Observable<TemplateInfo> {
    return this.http.patch<TemplateInfo>(`${this.baseUrl}/templates/${id}/scope`, { scope });
  }

  deleteTemplate(id: string): Observable<unknown> {
    return this.http.delete(`${this.baseUrl}/templates/${id}`);
  }

  learnTemplate(id: string): Observable<LearnResult> {
    return this.http.post<LearnResult>(`${this.baseUrl}/templates/${id}/learn`, {});
  }

  exportPresentation(markdown: string, templateId: string, format: string): Observable<HttpResponse<Blob>> {
    return this.http.post(`${this.baseUrl}/export`,
      { markdown, templateId, format },
      { responseType: 'blob', observe: 'response' },
    );
  }

  getSettings(): Observable<LlmSettings> {
    return this.http.get<LlmSettings>(`${this.baseUrl}/settings`);
  }

  updateSettings(settings: Partial<Pick<LlmSettings, 'gcpProjectId' | 'gcpRegion' | 'model'>>): Observable<LlmSettings> {
    return this.http.put<LlmSettings>(`${this.baseUrl}/settings`, settings);
  }
}
