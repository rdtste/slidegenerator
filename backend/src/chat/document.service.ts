import { Injectable, Logger } from '@nestjs/common';
import * as mammoth from 'mammoth';

// eslint-disable-next-line @typescript-eslint/no-require-imports
const pdfParse = require('pdf-parse') as (buffer: Buffer) => Promise<{ text: string }>;

const MAX_TEXT_LENGTH = 80_000;

@Injectable()
export class DocumentService {
  private readonly logger = new Logger(DocumentService.name);

  async extractText(file: Express.Multer.File): Promise<string> {
    const ext = file.originalname.toLowerCase().split('.').pop() ?? '';

    let text: string;
    switch (ext) {
      case 'pdf':
        text = await this.extractPdf(file.buffer);
        break;
      case 'docx':
        text = await this.extractDocx(file.buffer);
        break;
      case 'txt':
      case 'md':
        text = file.buffer.toString('utf-8');
        break;
      default:
        throw new Error(`Nicht unterstütztes Dateiformat: .${ext}`);
    }

    const trimmed = text.trim();
    if (trimmed.length > MAX_TEXT_LENGTH) {
      this.logger.warn(
        `Document "${file.originalname}" truncated from ${trimmed.length} to ${MAX_TEXT_LENGTH} chars`,
      );
      return trimmed.slice(0, MAX_TEXT_LENGTH);
    }

    this.logger.log(
      `Extracted ${trimmed.length} chars from "${file.originalname}"`,
    );
    return trimmed;
  }

  private async extractPdf(buffer: Buffer): Promise<string> {
    const data = await pdfParse(buffer);
    return data.text;
  }

  private async extractDocx(buffer: Buffer): Promise<string> {
    const result = await mammoth.extractRawText({ buffer });
    return result.value;
  }
}
