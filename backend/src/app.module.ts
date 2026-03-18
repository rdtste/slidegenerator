import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { SettingsModule } from './settings/settings.module';
import { ChatModule } from './chat/chat.module';
import { PreviewModule } from './preview/preview.module';
import { TemplatesModule } from './templates/templates.module';
import { ExportModule } from './export/export.module';
import { HealthController } from './common/health.controller';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    SettingsModule,
    ChatModule,
    PreviewModule,
    TemplatesModule,
    ExportModule,
  ],
  controllers: [HealthController],
})
export class AppModule {}
