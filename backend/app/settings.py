import json
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

# Get base directory for SQLite database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = Path(BASE_DIR).parent
SQLITE_URL_PREFIX = "sqlite:///"


def resolve_project_path(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return str(path.resolve())


def normalize_sqlite_url(database_url: str) -> str:
    if not database_url.startswith(SQLITE_URL_PREFIX):
        return database_url

    raw_path = database_url[len(SQLITE_URL_PREFIX):]
    if not raw_path or raw_path == ":memory:":
        return database_url

    db_path = Path(raw_path).expanduser()
    if not db_path.is_absolute():
        db_path = PROJECT_DIR / db_path

    return f"{SQLITE_URL_PREFIX}{db_path.resolve()}"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_DIR / ".env"),
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str

    jwt_secret: str
    jwt_alg: str
    jwt_exp_minutes: int

    admin_username: str
    admin_password: str
    admin_fullname: str

    default_camera_name: str
    default_camera_location: str
    default_camera_stream: Optional[str] = None
    default_area_name: str
    default_area_direction_mode: str
    default_area_roi_polygon: str
    employee_faces_dir: str
    insightface_model_name: str
    insightface_det_size: int
    insightface_providers: str

    # SQLite database - no Docker dependency
    database_url: str

    cors_origins: str

    def model_post_init(self, __context) -> None:
        self.database_url = normalize_sqlite_url(self.database_url)
        self.employee_faces_dir = resolve_project_path(self.employee_faces_dir)

    def cors_list(self) -> List[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one origin")
        return origins

    def insightface_provider_list(self) -> List[str]:
        providers = [provider.strip() for provider in self.insightface_providers.split(",") if provider.strip()]
        if not providers:
            raise ValueError("INSIGHTFACE_PROVIDERS must contain at least one provider")
        return providers

    def default_area_roi(self) -> List[List[int]]:
        try:
            parsed = json.loads(self.default_area_roi_polygon)
        except json.JSONDecodeError:
            raise ValueError("DEFAULT_AREA_ROI_POLYGON must be valid JSON") from None

        if not isinstance(parsed, list):
            raise ValueError("DEFAULT_AREA_ROI_POLYGON must be a list of [x, y] points")

        points: List[List[int]] = []
        for point in parsed:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("DEFAULT_AREA_ROI_POLYGON must contain [x, y] pairs")
            try:
                points.append([int(point[0]), int(point[1])])
            except (TypeError, ValueError):
                raise ValueError("DEFAULT_AREA_ROI_POLYGON coordinates must be integers") from None

        if not points:
            raise ValueError("DEFAULT_AREA_ROI_POLYGON must contain at least one point")
        return points

settings = Settings()
