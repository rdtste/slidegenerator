import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Param,
  Query,
  Body,
  Res,
  UploadedFile,
  UseInterceptors,
  HttpException,
  HttpStatus,
} from '@nestjs/common';
import type { Response } from 'express';
import { FileInterceptor } from '@nestjs/platform-express';
import { PresentationsService } from './presentations.service';

const MAX_FILE_SIZE = 50 * 1024 * 1024;

@Controller('presentations')
export class PresentationsController {
  constructor(private readonly service: PresentationsService) {}

  @Get()
  list() {
    return this.service.list();
  }

  @Get(':id')
  get(@Param('id') id: string) {
    const presentation = this.service.get(id);
    if (!presentation) {
      throw new HttpException(
        { detail: 'Präsentation nicht gefunden' },
        HttpStatus.NOT_FOUND,
      );
    }
    return presentation;
  }

  @Get(':id/download')
  download(
    @Param('id') id: string,
    @Query('version') version: string | undefined,
    @Res() res: Response,
  ) {
    const v = version ? parseInt(version, 10) : undefined;
    const filePath = this.service.getVersionPath(id, v);
    if (!filePath) {
      throw new HttpException(
        { detail: 'Version nicht gefunden' },
        HttpStatus.NOT_FOUND,
      );
    }

    const meta = this.service.get(id);
    const safeName = (meta?.name ?? 'presentation').replace(/[^a-zA-Z0-9äöüÄÖÜß _-]/g, '_');
    const versionSuffix = v ? `_v${v}` : '';
    res.download(filePath, `${safeName}${versionSuffix}.pptx`);
  }

  @Post()
  @UseInterceptors(FileInterceptor('file'))
  upload(
    @UploadedFile() file: Express.Multer.File,
    @Body('name') name?: string,
  ) {
    if (!file || !file.originalname?.toLowerCase().endsWith('.pptx')) {
      throw new HttpException(
        { detail: 'Nur .pptx-Dateien erlaubt' },
        HttpStatus.BAD_REQUEST,
      );
    }
    if (file.size > MAX_FILE_SIZE) {
      throw new HttpException(
        { detail: 'Datei zu groß (max 50 MB)' },
        HttpStatus.BAD_REQUEST,
      );
    }

    const presentationName = name || file.originalname.replace(/\.pptx$/i, '');
    return this.service.create(presentationName, 'uploaded', file.buffer);
  }

  @Post(':id/versions')
  @UseInterceptors(FileInterceptor('file'))
  addVersion(
    @Param('id') id: string,
    @UploadedFile() file: Express.Multer.File,
  ) {
    if (!file) {
      throw new HttpException({ detail: 'Datei fehlt' }, HttpStatus.BAD_REQUEST);
    }

    try {
      return this.service.addVersion(id, file.buffer);
    } catch {
      throw new HttpException(
        { detail: 'Präsentation nicht gefunden' },
        HttpStatus.NOT_FOUND,
      );
    }
  }

  @Patch(':id')
  rename(@Param('id') id: string, @Body('name') name: string) {
    if (!name?.trim()) {
      throw new HttpException(
        { detail: 'Name darf nicht leer sein' },
        HttpStatus.BAD_REQUEST,
      );
    }
    const result = this.service.rename(id, name.trim());
    if (!result) {
      throw new HttpException(
        { detail: 'Präsentation nicht gefunden' },
        HttpStatus.NOT_FOUND,
      );
    }
    return result;
  }

  @Delete(':id')
  remove(@Param('id') id: string) {
    const deleted = this.service.delete(id);
    if (!deleted) {
      throw new HttpException(
        { detail: 'Präsentation nicht gefunden' },
        HttpStatus.NOT_FOUND,
      );
    }
    return { success: true };
  }

  @Delete(':id/versions/:version')
  removeVersion(@Param('id') id: string, @Param('version') version: string) {
    const v = parseInt(version, 10);
    if (isNaN(v)) {
      throw new HttpException(
        { detail: 'Ungültige Versionsnummer' },
        HttpStatus.BAD_REQUEST,
      );
    }

    const result = this.service.deleteVersion(id, v);
    if (result === null) {
      return { deleted: true, message: 'Letzte Version gelöscht, Präsentation entfernt' };
    }
    return result;
  }
}
