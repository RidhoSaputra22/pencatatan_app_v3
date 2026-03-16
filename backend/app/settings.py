from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os

# Get base directory for SQLite database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = Path(BASE_DIR).parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_DIR / ".env"),
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "dev"

    jwt_secret: str = "change-me-in-production"
    jwt_alg: str = "HS256"
    jwt_exp_minutes: int = 60 * 24

    admin_username: str = "admin"
    admin_password: str = "admin123"
    admin_fullname: str = "Administrator"

    default_camera_name: str = "Kamera Utama"
    default_camera_location: str = "Pintu Masuk Utama"
    default_camera_stream: Optional[str] = None
    employee_faces_dir: str = os.path.join(BASE_DIR, "storage", "employee_faces")
    insightface_model_name: str = "buffalo_l"
    insightface_det_size: int = 640

    # SQLite database - no Docker dependency
    database_url: str = f"sqlite:///{os.path.join(BASE_DIR, 'visitors.db')}"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    def cors_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

settings = Settings()
