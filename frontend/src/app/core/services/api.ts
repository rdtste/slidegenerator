import { Injectable } from '@angular/core';
import { HttpClient, HttpResponse } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ChatResponse, TemplateInfo, LlmSettings } from '../models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseUrl = environment.apiUrl;

  constructor(private readonly http: HttpClient) {}

  chat(prompt: string, files?: File[], templateId?: string): Observable<ChatResponse> {
    const formData = new FormData();
    formData.append('prompt', prompt);
    if (templateId) {
      formData.append('templateId', templateId);
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
    return this.http.get<TemplateInfo[]>(`${this.baseUrl}/templates`);
  }

  uploadTemplate(file: File): Observable<TemplateInfo> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<TemplateInfo>(`${this.baseUrl}/templates`, formData);
  }

  deleteTemplate(id: string): Observable<unknown> {
    return this.http.delete(`${this.baseUrl}/templates/${id}`);
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
