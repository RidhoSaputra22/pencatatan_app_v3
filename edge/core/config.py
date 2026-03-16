"""Configuration management for edge worker"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from parent directory
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


def env(name: str, default: str = "") -> str:
    """Get environment variable with default value"""
    return os.getenv(name, default)


def env_int(name: str, default: int) -> int:
    """Parse integer environment variables safely."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return default


def env_bool(name: str, default: bool = False) -> bool:
    """Parse bool-like environment variable values."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Mode configuration
MODE = env("EDGE_MODE", "fake").lower()
CAMERA_ID = int(env("EDGE_CAMERA_ID", "1"))

# Timing configuration
POST_INTERVAL = int(env("EDGE_POST_INTERVAL_SECONDS", "3"))
CONFIG_REFRESH = int(env("EDGE_CONFIG_REFRESH_SECONDS", "30"))

# Stream configuration
EDGE_STREAM_URL = env("EDGE_STREAM_URL", "").strip()
EDGE_STREAM_PORT = env_int("EDGE_STREAM_PORT", 5000)
EDGE_STREAM_JPEG_QUALITY = max(50, min(95, env_int("EDGE_STREAM_JPEG_QUALITY", 80)))
EDGE_STREAM_MAX_FPS = max(0, env_int("EDGE_STREAM_MAX_FPS", 0))

# YOLOv5 configuration
CONF_TH = float(env("YOLOV5_CONF", "0.35"))
IOU_TH = float(env("YOLOV5_IOU", "0.45"))
IMG_SIZE = int(env("YOLOV5_IMG_SIZE", "640"))
# Device: "cpu", "cuda", "xpu" (Intel GPU), or "auto" (auto-detect)
DEVICE = env("YOLOV5_DEVICE", "auto")
WEIGHTS = env("YOLOV5_WEIGHTS", "").strip()
REPO = env("YOLOV5_REPO", "").strip()

# Tracking configuration
TRACK_MAX_DISAPPEARED = int(env("TRACK_MAX_DISAPPEARED", "20"))
TRACK_MAX_DISTANCE = float(env("TRACK_MAX_DISTANCE", "80"))
TRACK_CONFIRM_FRAMES = max(1, env_int("TRACK_CONFIRM_FRAMES", 1))

# Face recognition configuration
FACE_RECOGNITION_ENABLED = env_bool("FACE_RECOGNITION_ENABLED", True)
INSIGHTFACE_MODEL_NAME = env("INSIGHTFACE_MODEL_NAME", "buffalo_l")
INSIGHTFACE_DET_SIZE = int(env("INSIGHTFACE_DET_SIZE", "640"))
EMPLOYEE_MATCH_THRESHOLD = float(env("EMPLOYEE_MATCH_THRESHOLD", "0.45"))
EMPLOYEE_REGISTRY_REFRESH_SECONDS = int(env("EMPLOYEE_REGISTRY_REFRESH_SECONDS", "60"))
FACE_RECHECK_SECONDS = float(env("FACE_RECHECK_SECONDS", "0.8"))
FACE_UNKNOWN_TIMEOUT = float(env("FACE_UNKNOWN_TIMEOUT", "2.5"))

# Backend API configuration
BACKEND_URL = env("BACKEND_URL", "http://localhost:8000")
INGEST_URL = f"{BACKEND_URL}/api/events/ingest"
AUTH_USER = env("EDGE_AUTH_USERNAME", "admin")
AUTH_PASS = env("EDGE_AUTH_PASSWORD", "admin123")
