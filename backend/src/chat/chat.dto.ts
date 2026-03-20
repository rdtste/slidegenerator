import { IsString, IsNotEmpty, IsOptional, MinLength } from 'class-validator';

export class ChatRequestDto {
  @IsString()
  @IsNotEmpty()
  @MinLength(1)
  prompt!: string;

  @IsString()
  @IsOptional()
  templateId?: string;

  @IsString()
  @IsOptional()
  audience?: string;

  @IsString()
  @IsOptional()
  imageStyle?: string;
}

export class SlideDto {
  layout!: string;
  title!: string;
  subtitle!: string;
  body!: string;
  bullets!: string[];
  notes!: string;
  imageDescription!: string;
  leftColumn!: string;
  rightColumn!: string;
}

export class ChatResponseDto {
  markdown!: string;
  slides!: SlideDto[];
}

export class ClarifyResponseDto {
  needsClarification!: boolean;
  questions!: string;
}
