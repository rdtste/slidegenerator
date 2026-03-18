import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as fs from 'fs';
import * as path from 'path';
import { randomUUID } from 'crypto';
import { PresentationDto, PresentationVersionDto } from './presentations.dto';

@Injectable()
export class PresentationsService {
  private readonly logger = new Logger(PresentationsService.name);
  private readonly storageDir: string;

  constructor(private readonly config: ConfigService) {
    this.storageDir = this.config.get<string>(
      'PRESENTATIONS_DIR',
      path.resolve(__dirname, '../../presentations'),
    );
    fs.mkdirSync(this.storageDir, { recursive: true });
  }

  list(): PresentationDto[] {
    if (!fs.existsSync(this.storageDir)) return [];

    const entries = fs.readdirSync(this.storageDir, { withFileTypes: true })
      .filter((d) => d.isDirectory());

    return entries
      .map((d) => this.readMeta(d.name))
      .filter((m): m is PresentationDto => m !== null)
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  }

  get(id: string): PresentationDto | null {
    return this.readMeta(id);
  }

  create(name: string, templateId: string, pptxBuffer: Buffer): PresentationDto {
    const id = randomUUID();
    const dir = path.join(this.storageDir, id);
    fs.mkdirSync(dir, { recursive: true });

    const now = new Date().toISOString();
    const filename = 'v1.pptx';
    fs.writeFileSync(path.join(dir, filename), pptxBuffer);

    const meta: PresentationDto = {
      id,
      name,
      templateId,
      createdAt: now,
      updatedAt: now,
      currentVersion: 1,
      versions: [
        { version: 1, filename, size: pptxBuffer.length, createdAt: now },
      ],
    };

    this.writeMeta(id, meta);
    this.logger.log(`Created presentation: ${id} "${name}"`);
    return meta;
  }

  addVersion(id: string, pptxBuffer: Buffer): PresentationDto {
    const meta = this.readMeta(id);
    if (!meta) {
      throw new Error(`Presentation ${id} not found`);
    }

    const nextVersion = meta.versions.length + 1;
    const filename = `v${nextVersion}.pptx`;
    const dir = path.join(this.storageDir, path.basename(id));
    fs.writeFileSync(path.join(dir, filename), pptxBuffer);

    const now = new Date().toISOString();
    meta.versions.push({
      version: nextVersion,
      filename,
      size: pptxBuffer.length,
      createdAt: now,
    });
    meta.currentVersion = nextVersion;
    meta.updatedAt = now;

    this.writeMeta(id, meta);
    this.logger.log(`Added version ${nextVersion} to presentation: ${id}`);
    return meta;
  }

  getVersionPath(id: string, version?: number): string | null {
    const meta = this.readMeta(id);
    if (!meta) return null;

    const v = version ?? meta.currentVersion;
    const versionMeta = meta.versions.find((vm) => vm.version === v);
    if (!versionMeta) return null;

    const filePath = path.join(this.storageDir, path.basename(id), versionMeta.filename);
    return fs.existsSync(filePath) ? filePath : null;
  }

  rename(id: string, name: string): PresentationDto | null {
    const meta = this.readMeta(id);
    if (!meta) return null;

    meta.name = name;
    meta.updatedAt = new Date().toISOString();
    this.writeMeta(id, meta);
    this.logger.log(`Renamed presentation ${id} to "${name}"`);
    return meta;
  }

  delete(id: string): boolean {
    const dir = path.join(this.storageDir, path.basename(id));
    if (!fs.existsSync(dir)) return false;

    fs.rmSync(dir, { recursive: true, force: true });
    this.logger.log(`Deleted presentation: ${id}`);
    return true;
  }

  deleteVersion(id: string, version: number): PresentationDto | null {
    const meta = this.readMeta(id);
    if (!meta) return null;

    const idx = meta.versions.findIndex((v) => v.version === version);
    if (idx === -1) return null;

    const versionMeta = meta.versions[idx];
    const filePath = path.join(this.storageDir, path.basename(id), versionMeta.filename);
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath);

    meta.versions.splice(idx, 1);
    meta.updatedAt = new Date().toISOString();

    if (meta.versions.length === 0) {
      this.delete(id);
      return null;
    }

    meta.currentVersion = meta.versions[meta.versions.length - 1].version;
    this.writeMeta(id, meta);
    return meta;
  }

  private readMeta(id: string): PresentationDto | null {
    const safeId = path.basename(id);
    const metaPath = path.join(this.storageDir, safeId, 'meta.json');
    if (!fs.existsSync(metaPath)) return null;

    try {
      return JSON.parse(fs.readFileSync(metaPath, 'utf-8'));
    } catch {
      this.logger.warn(`Failed to read meta for ${safeId}`);
      return null;
    }
  }

  private writeMeta(id: string, meta: PresentationDto): void {
    const safeId = path.basename(id);
    const metaPath = path.join(this.storageDir, safeId, 'meta.json');
    fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2), 'utf-8');
  }
}
