import { IsString, IsNotEmpty, IsOptional } from 'class-validator';

export class PreviewRequestDto {
  @IsString()
  @IsNotEmpty()
  markdown!: string;

  @IsString()
  @IsOptional()
  theme?: string;

  @IsString()
  @IsOptional()
  templateId?: string;
}
