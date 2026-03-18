export class PresentationVersionDto {
  version!: number;
  filename!: string;
  size!: number;
  createdAt!: string;
}

export class PresentationDto {
  id!: string;
  name!: string;
  templateId!: string;
  createdAt!: string;
  updatedAt!: string;
  currentVersion!: number;
  versions!: PresentationVersionDto[];
}
