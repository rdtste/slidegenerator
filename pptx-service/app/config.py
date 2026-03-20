from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    templates_dir: Path = Path(__file__).resolve().parent.parent / "templates"

    # GCP settings for Imagen image generation
    gcp_project_id: str = "rd-cmpd-prod513-psl-mate-dev"
    gcp_region: str = "europe-west1"
    imagen_model: str = "imagen-3.0-generate-002"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def model_post_init(self, __context: object) -> None:
        # Resolve relative paths against the project root
        if not self.templates_dir.is_absolute():
            project_root = Path(__file__).resolve().parent.parent
            object.__setattr__(self, "templates_dir", (project_root / self.templates_dir).resolve())


settings = Settings()
