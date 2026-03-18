import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { GoogleAuth } from 'google-auth-library';
import {
  SettingsResponseDto,
  RegionOption,
  ModelOption,
} from './settings.dto';

const REGIONS: RegionOption[] = [
  { id: 'europe-west3', name: 'Europe West 3 (Frankfurt)' },
  { id: 'europe-west1', name: 'Europe West 1 (Belgium)' },
  { id: 'europe-west4', name: 'Europe West 4 (Netherlands)' },
  { id: 'europe-west9', name: 'Europe West 9 (Paris)' },
  { id: 'us-central1', name: 'US Central 1 (Iowa)' },
  { id: 'us-east4', name: 'US East 4 (Virginia)' },
  { id: 'asia-southeast1', name: 'Asia Southeast 1 (Singapore)' },
  { id: 'asia-northeast1', name: 'Asia Northeast 1 (Tokyo)' },
];

const MODELS: ModelOption[] = [
  { id: 'google/gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
  { id: 'google/gemini-2.5-pro', name: 'Gemini 2.5 Pro' },
  { id: 'google/gemini-2.0-flash', name: 'Gemini 2.0 Flash' },
  { id: 'google/gemini-2.0-pro', name: 'Gemini 2.0 Pro' },
  { id: 'google/gemini-1.5-pro', name: 'Gemini 1.5 Pro' },
  { id: 'google/gemini-1.5-flash', name: 'Gemini 1.5 Flash' },
];

@Injectable()
export class SettingsService {
  private readonly logger = new Logger(SettingsService.name);
  private readonly auth: GoogleAuth;

  private gcpProjectId: string;
  private gcpRegion: string;
  private model: string;

  constructor(private readonly config: ConfigService) {
    this.gcpProjectId = this.config.get<string>(
      'GCP_PROJECT_ID',
      'rd-cmpd-prod513-psl-mate-dev',
    );
    this.gcpRegion = this.config.get<string>('GCP_REGION', 'europe-west3');
    this.model = this.config.get<string>('GCP_MODEL', 'gemini-2.5-flash');

    this.auth = new GoogleAuth({
      scopes: ['https://www.googleapis.com/auth/cloud-platform'],
    });
  }

  getSettings(): SettingsResponseDto {
    return {
      gcpProjectId: this.gcpProjectId,
      gcpRegion: this.gcpRegion,
      model: this.model,
      availableRegions: REGIONS,
      availableModels: MODELS,
    };
  }

  updateSettings(partial: {
    gcpProjectId?: string;
    gcpRegion?: string;
    model?: string;
  }): SettingsResponseDto {
    if (partial.gcpProjectId !== undefined) {
      this.gcpProjectId = partial.gcpProjectId;
    }
    if (partial.gcpRegion !== undefined) {
      this.gcpRegion = partial.gcpRegion;
    }
    if (partial.model !== undefined) {
      this.model = partial.model;
    }
    this.logger.log(
      `Settings updated: project=${this.gcpProjectId}, region=${this.gcpRegion}, model=${this.model}`,
    );
    return this.getSettings();
  }

  async getAccessToken(): Promise<string> {
    const client = await this.auth.getClient();
    const tokenResponse = await client.getAccessToken();
    if (!tokenResponse.token) {
      throw new Error(
        'GCP-Authentifizierung fehlgeschlagen. Bitte "gcloud auth application-default login" ausführen.',
      );
    }
    return tokenResponse.token;
  }

  getBaseURL(): string {
    return `https://${this.gcpRegion}-aiplatform.googleapis.com/v1beta1/projects/${this.gcpProjectId}/locations/${this.gcpRegion}/endpoints/openapi`;
  }

  getModel(): string {
    return this.model;
  }
}
