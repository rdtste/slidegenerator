import { IsString, IsNotEmpty, IsOptional } from 'class-validator';

export class UpdateSettingsDto {
  @IsString()
  @IsOptional()
  gcpProjectId?: string;

  @IsString()
  @IsOptional()
  gcpRegion?: string;

  @IsString()
  @IsOptional()
  model?: string;
}

export class SettingsResponseDto {
  gcpProjectId!: string;
  gcpRegion!: string;
  model!: string;
  availableRegions!: RegionOption[];
  availableModels!: ModelOption[];
  presentationCount!: number;
}

export class RegionOption {
  id!: string;
  name!: string;
}

export class ModelOption {
  id!: string;
  name!: string;
}
