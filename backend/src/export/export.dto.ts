import { IsString, IsNotEmpty, IsOptional, IsIn } from 'class-validator';

export class ExportRequestDto {
  @IsString()
  @IsNotEmpty()
  markdown!: string;

  @IsString()
  @IsOptional()
  templateId?: string;

  @IsString()
  @IsOptional()
  @IsIn(['pptx', 'pdf', 'html'])
  format?: string = 'pptx';
}
