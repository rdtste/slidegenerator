import { Module } from '@nestjs/common';
import { ChatController } from './chat.controller';
import { ChatService } from './chat.service';
import { DocumentService } from './document.service';
import { TemplatesModule } from '../templates/templates.module';

@Module({
  imports: [TemplatesModule],
  controllers: [ChatController],
  providers: [ChatService, DocumentService],
  exports: [ChatService],
})
export class ChatModule {}
