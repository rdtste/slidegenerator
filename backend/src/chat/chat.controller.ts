import {
  Controller,
  Post,
  Body,
  HttpException,
  HttpStatus,
  UploadedFiles,
  UseInterceptors,
} from '@nestjs/common';
import { FilesInterceptor } from '@nestjs/platform-express';
import { ChatService } from './chat.service';
import { DocumentService } from './document.service';
import { ChatResponseDto, ClarifyResponseDto } from './chat.dto';

const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB
const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md'];

@Controller('chat')
export class ChatController {
  constructor(
    private readonly chatService: ChatService,
    private readonly documentService: DocumentService,
  ) {}

  @Post('clarify')
  @UseInterceptors(FilesInterceptor('files', 5))
  async clarify(
    @Body('prompt') prompt: string,
    @Body('conversation') conversationJson?: string,
    @UploadedFiles() files?: Express.Multer.File[],
  ): Promise<ClarifyResponseDto> {
    if (!prompt?.trim()) {
      throw new HttpException(
        { detail: 'Prompt darf nicht leer sein' },
        HttpStatus.BAD_REQUEST,
      );
    }

    try {
      const documentTexts: string[] = [];
      if (files?.length) {
        for (const file of files) {
          const ext = '.' + (file.originalname.toLowerCase().split('.').pop() ?? '');
          if (!ALLOWED_EXTENSIONS.includes(ext)) {
            throw new HttpException(
              { detail: `Nicht unterstütztes Format: ${ext}. Erlaubt: ${ALLOWED_EXTENSIONS.join(', ')}` },
              HttpStatus.BAD_REQUEST,
            );
          }
          if (file.size > MAX_FILE_SIZE) {
            throw new HttpException(
              { detail: `Datei "${file.originalname}" zu groß (max 20 MB)` },
              HttpStatus.BAD_REQUEST,
            );
          }
          const text = await this.documentService.extractText(file);
          documentTexts.push(`--- Dokument: ${file.originalname} ---\n${text}`);
        }
      }

      let previousConversation: Array<{ role: string; content: string }> = [];
      if (conversationJson) {
        try {
          previousConversation = JSON.parse(conversationJson);
        } catch {
          // ignore malformed JSON
        }
      }

      return await this.chatService.clarify(prompt.trim(), documentTexts, previousConversation);
    } catch (error: unknown) {
      if (error instanceof HttpException) throw error;
      const message = error instanceof Error ? error.message : 'Unknown error';
      throw new HttpException(
        { detail: `LLM-Fehler: ${message}` },
        HttpStatus.BAD_GATEWAY,
      );
    }
  }

  @Post('pimp')
  async pimpSlides(
    @Body('markdown') markdown: string,
    @Body('templateId') templateId?: string,
    @Body('audience') audience?: string,
    @Body('imageStyle') imageStyle?: string,
    @Body('customColor') customColor?: string,
    @Body('customFont') customFont?: string,
  ): Promise<ChatResponseDto> {
    if (!markdown?.trim()) {
      throw new HttpException(
        { detail: 'Markdown darf nicht leer sein' },
        HttpStatus.BAD_REQUEST,
      );
    }

    try {
      return await this.chatService.pimpSlides(
        markdown.trim(),
        templateId,
        audience,
        imageStyle,
        customColor,
        customFont,
      );
    } catch (error: unknown) {
      if (error instanceof HttpException) throw error;
      const message = error instanceof Error ? error.message : 'Unknown error';
      throw new HttpException(
        { detail: `LLM-Fehler: ${message}` },
        HttpStatus.BAD_GATEWAY,
      );
    }
  }

  @Post('optimize')
  async optimizeMarkdown(
    @Body('markdown') markdown: string,
    @Body('templateId') templateId?: string,
    @Body('audience') audience?: string,
    @Body('imageStyle') imageStyle?: string,
    @Body('customColor') customColor?: string,
    @Body('customFont') customFont?: string,
  ): Promise<ChatResponseDto> {
    if (!markdown?.trim()) {
      throw new HttpException(
        { detail: 'Markdown darf nicht leer sein' },
        HttpStatus.BAD_REQUEST,
      );
    }

    try {
      return await this.chatService.optimizeMarkdown(
        markdown.trim(),
        templateId,
        audience,
        imageStyle,
        customColor,
        customFont,
      );
    } catch (error: unknown) {
      if (error instanceof HttpException) throw error;
      const message = error instanceof Error ? error.message : 'Unknown error';
      throw new HttpException(
        { detail: `LLM-Fehler: ${message}` },
        HttpStatus.BAD_GATEWAY,
      );
    }
  }

  @Post()
  @UseInterceptors(FilesInterceptor('files', 5))
  async chat(
    @Body('prompt') prompt: string,
    @Body('templateId') templateId?: string,
    @Body('audience') audience?: string,
    @Body('imageStyle') imageStyle?: string,
    @Body('customColor') customColor?: string,
    @Body('customFont') customFont?: string,
    @UploadedFiles() files?: Express.Multer.File[],
  ): Promise<ChatResponseDto> {
    if (!prompt?.trim()) {
      throw new HttpException(
        { detail: 'Prompt darf nicht leer sein' },
        HttpStatus.BAD_REQUEST,
      );
    }

    try {
      const documentTexts: string[] = [];

      if (files?.length) {
        for (const file of files) {
          const ext = '.' + (file.originalname.toLowerCase().split('.').pop() ?? '');
          if (!ALLOWED_EXTENSIONS.includes(ext)) {
            throw new HttpException(
              { detail: `Nicht unterstütztes Format: ${ext}. Erlaubt: ${ALLOWED_EXTENSIONS.join(', ')}` },
              HttpStatus.BAD_REQUEST,
            );
          }
          if (file.size > MAX_FILE_SIZE) {
            throw new HttpException(
              { detail: `Datei "${file.originalname}" zu groß (max 20 MB)` },
              HttpStatus.BAD_REQUEST,
            );
          }
          const text = await this.documentService.extractText(file);
          documentTexts.push(`--- Dokument: ${file.originalname} ---\n${text}`);
        }
      }

      return await this.chatService.generate(prompt.trim(), documentTexts, templateId, audience, imageStyle, customColor, customFont);
    } catch (error: unknown) {
      if (error instanceof HttpException) throw error;
      const message = error instanceof Error ? error.message : 'Unknown error';
      throw new HttpException(
        { detail: `LLM-Fehler: ${message}` },
        HttpStatus.BAD_GATEWAY,
      );
    }
  }
}
