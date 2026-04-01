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
  @IsIn(['pptx', 'pdf'])
  format?: string = 'pptx';

  @IsString()
  @IsOptional()
  customColor?: string;

  @IsString()
  @IsOptional()
  customFont?: string;
}

export class ExportV2RequestDto {
  @IsString()
  @IsNotEmpty()
  prompt!: string;

  @IsString()
  @IsOptional()
  @IsIn(['design', 'template'])
  mode?: string = 'design';

  @IsString()
  @IsOptional()
  documentText?: string;

  @IsString()
  @IsOptional()
  audience?: string = 'management';

  @IsString()
  @IsOptional()
  imageStyle?: string = 'minimal';

  @IsString()
  @IsOptional()
  accentColor?: string = '#2563EB';

  @IsString()
  @IsOptional()
  fontFamily?: string = 'Calibri';

  @IsString()
  @IsOptional()
  templateId?: string;
}

export class PregenerateV2RequestDto {
  @IsString()
  @IsNotEmpty()
  prompt!: string;

  @IsString()
  @IsOptional()
  audience?: string = 'management';

  @IsString()
  @IsOptional()
  imageStyle?: string = 'minimal';

  @IsString()
  @IsOptional()
  accentColor?: string;

  @IsString()
  @IsOptional()
  fontFamily?: string;

  @IsString()
  @IsOptional()
  templateId?: string;
}

export class GenerateDeckRequestDto {
  @IsString()
  @IsNotEmpty()
  topic!: string;

  @IsString()
  @IsOptional()
  @IsIn(['design', 'template'])
  mode?: string = 'design';

  @IsString()
  @IsOptional()
  audience?: string = 'management';

  @IsString()
  @IsOptional()
  imageStyle?: string = 'minimal';

  @IsString()
  @IsOptional()
  accentColor?: string = '#2563EB';

  @IsString()
  @IsOptional()
  fontFamily?: string = 'Calibri';

  /** Default: REWE digital Master template */
  @IsString()
  @IsOptional()
  templateId?: string = '2023_REWEdigital_Master_DE_01';
}
