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
    // Track increments that haven't been persisted yet
    this.pendingIncrements++;
    this.flushStats();
  }

  private pendingIncrements = 0;

  private flushStats(): void {
    // Try to read the persisted count from disk
    let diskCount: number | null = null;
    try {
      if (fs.existsSync(this.statsPath)) {
        const data = JSON.parse(fs.readFileSync(this.statsPath, 'utf-8'));
        diskCount = data.presentationCount ?? 0;
      }
    } catch {
      this.logger.warn('Could not read stats file');
    }

    if (diskCount == null) {
      // File not available (GCS FUSE not ready) — keep increments pending
      this.logger.warn(
        `Stats file unavailable, ${this.pendingIncrements} increment(s) pending`,
      );
      return;
    }

    // Merge pending increments with persisted count
    const newCount = diskCount + this.pendingIncrements;
    this.pendingIncrements = 0;
    try {
      const dir = path.dirname(this.statsPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(
        this.statsPath,
        JSON.stringify({ presentationCount: newCount }, null, 2),
      );
    } catch (err) {
      // Write failed — restore pending so next flush retries
      this.pendingIncrements = newCount - diskCount;
      this.logger.warn(`Could not write stats: ${err}`);
    }
  }

  private loadStats(): { presentationCount: number } {
    // Try flushing any pending increments first
    if (this.pendingIncrements > 0) {
      this.flushStats();
    }
    try {
      if (fs.existsSync(this.statsPath)) {
        const data = JSON.parse(fs.readFileSync(this.statsPath, 'utf-8'));
        return { presentationCount: (data.presentationCount ?? 0) + this.pendingIncrements };
      }
    } catch {
      this.logger.warn('Could not read stats file');
    }
    return { presentationCount: this.pendingIncrements };
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
