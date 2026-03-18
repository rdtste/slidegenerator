import { Controller, Get, Put, Body } from '@nestjs/common';
import { SettingsService } from './settings.service';
import { UpdateSettingsDto, SettingsResponseDto } from './settings.dto';

@Controller('settings')
export class SettingsController {
  constructor(private readonly settingsService: SettingsService) {}

  @Get()
  getSettings(): SettingsResponseDto {
    return this.settingsService.getSettings();
  }

  @Put()
  updateSettings(@Body() dto: UpdateSettingsDto): SettingsResponseDto {
    return this.settingsService.updateSettings(dto);
  }
}
