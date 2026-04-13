import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { GoogleAuth } from 'google-auth-library';
import * as fs from 'fs';
import * as path from 'path';
import {
  SettingsResponseDto,
  RegionOption,
  ModelOption,
} from './settings.dto';

const REGIONS: RegionOption[] = [
  { id: 'europe-west1', name: 'Europe West 1 (Belgium)' },
  { id: 'europe-west3', name: 'Europe West 3 (Frankfurt)' },
  { id: 'europe-west4', name: 'Europe West 4 (Netherlands)' },
  { id: 'europe-west9', name: 'Europe West 9 (Paris)' },
  { id: 'us-central1', name: 'US Central 1 (Iowa)' },
  { id: 'us-east4', name: 'US East 4 (Virginia)' },
  { id: 'asia-southeast1', name: 'Asia Southeast 1 (Singapore)' },
  { id: 'asia-northeast1', name: 'Asia Northeast 1 (Tokyo)' },
];

const MODELS: ModelOption[] = [
  { id: 'google/gemini-2.5-pro', name: 'Gemini 2.5 Pro' },
  { id: 'google/gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
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
  private readonly statsPath: string;

  constructor(private readonly config: ConfigService) {
    this.gcpProjectId = this.config.get<string>(
      'GCP_PROJECT_ID',
      'rd-cmpd-prod513-psl-mate-dev',
    );
    this.gcpRegion = this.config.get<string>('GCP_REGION', 'europe-west1');
    this.model = this.config.get<string>('GCP_MODEL', 'google/gemini-2.5-pro');

    const templatesDir = this.config.get<string>(
      'TEMPLATES_DIR',
      path.resolve(__dirname, '../../templates'),
    );
    this.statsPath = path.join(templatesDir, 'stats.json');

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
      presentationCount: this.loadStats().presentationCount,
    };
  }

  incrementPresentationCount(): void {
    const stats = this.loadStats();
    stats.presentationCount++;
    this.cachedCount = stats.presentationCount;
    this.saveStats(stats);
  }

  private cachedCount: number | null = null;

  private loadStats(): { presentationCount: number } {
    try {
      if (fs.existsSync(this.statsPath)) {
        const data = JSON.parse(fs.readFileSync(this.statsPath, 'utf-8'));
        this.cachedCount = data.presentationCount;
        return data;
      }
    } catch {
      this.logger.warn('Could not read stats file');
    }
    // Use in-memory count if file is unavailable (GCS FUSE not ready)
    if (this.cachedCount != null) {
      return { presentationCount: this.cachedCount };
    }
    return { presentationCount: 0 };
  }

  private saveStats(stats: { presentationCount: number }): void {
    try {
      const dir = path.dirname(this.statsPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(this.statsPath, JSON.stringify(stats, null, 2));
    } catch (err) {
      this.logger.warn(`Could not write stats: ${err}`);
    }
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
