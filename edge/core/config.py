"""Configuration management for edge worker"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from parent directory
PROJECT_DIR = Path(__file__).resolve().parents[2]
env_path = PROJECT_DIR / ".env"
load_dotenv(dotenv_path=env_path)


def resolve_project_path(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return str(path.resolve())


def env(name: str, default: str = "") -> str:
    """Get environment variable with default value"""
    return os.getenv(name, default)


def env_required(name: str) -> str:
    """Get a required environment variable."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return raw.strip()


def env_int(name: str, default: int) -> int:
    """Parse integer environment variables safely."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return default


def env_int_required(name: str) -> int:
    """Parse a required integer environment variable."""
    raw = env_required(name)
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


def env_float(name: str, default: float) -> float:
    """Parse float environment variable safely."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except (TypeError, ValueError):
        return default


def env_float_required(name: str) -> float:
    """Parse a required float environment variable."""
    raw = env_required(name)
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Environment variable {name} must be a float") from exc


def env_bool(name: str, default: bool = False) -> bool:
    """Parse bool-like environment variable values."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_bool_required(name: str) -> bool:
    """Parse a required bool-like environment variable."""
    return env_required(name).lower() in {"1", "true", "yes", "on"}


# App environment — controls log verbosity (dev=DEBUG, else INFO)
APP_ENV = env("APP_ENV", "production").strip().lower()

# Mode configuration
MODE = env_required("EDGE_MODE").lower()
CAMERA_ID = env_int_required("EDGE_CAMERA_ID")

# Timing configuration
POST_INTERVAL = env_int_required("EDGE_POST_INTERVAL_SECONDS")
CONFIG_REFRESH = env_int_required("EDGE_CONFIG_REFRESH_SECONDS")

# Stream configuration
EDGE_STREAM_URL = env("EDGE_STREAM_URL", "").strip()
EDGE_STREAM_HOST = env_required("EDGE_STREAM_HOST")
EDGE_STREAM_PORT = env_int_required("EDGE_STREAM_PORT")
EDGE_STREAM_JPEG_QUALITY = max(10, min(95, env_int_required("EDGE_STREAM_JPEG_QUALITY")))
EDGE_STREAM_MAX_FPS = max(0.0, env_float("EDGE_STREAM_MAX_FPS", 0.0))
EDGE_PROCESSING_MAX_FPS = max(0.0, env_float("EDGE_PROCESSING_MAX_FPS", 12.0))
EDGE_STREAM_ALLOW_ORIGIN = env_required("EDGE_STREAM_ALLOW_ORIGIN")
EDGE_WEBRTC_ENABLED = env_bool("EDGE_WEBRTC_ENABLED", True)
EDGE_WEBRTC_ICE_SERVERS = env("EDGE_WEBRTC_ICE_SERVERS", "").strip()
EDGE_CAPTURE_OPEN_TIMEOUT_MS = max(1_000, env_int("EDGE_CAPTURE_OPEN_TIMEOUT_MS", 10_000))
EDGE_CAPTURE_READ_TIMEOUT_MS = max(250, env_int("EDGE_CAPTURE_READ_TIMEOUT_MS", 3_000))
EDGE_CAPTURE_FFMPEG_OPTIONS = env(
    "EDGE_CAPTURE_FFMPEG_OPTIONS",
    "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;500000|reorder_queue_size;0",
).strip()

# YOLO configuration
# YOLO_BACKEND: "yolov5" (torch.hub) | "ultralytics" (YOLOv8/v9/v10/v11 via ultralytics package)
YOLO_BACKEND = env("YOLO_BACKEND", "yolov5").strip().lower()
CONF_TH = env_float_required("YOLOV5_CONF")
IOU_TH = env_float_required("YOLOV5_IOU")
IMG_SIZE = env_int_required("YOLOV5_IMG_SIZE")
# Device: "cpu", "cuda", "xpu" (Intel GPU), or "auto" (auto-detect)
DEVICE = env_required("YOLOV5_DEVICE")
WEIGHTS = resolve_project_path(env_required("YOLOV5_WEIGHTS"))
REPO = resolve_project_path(env("YOLOV5_REPO", "").strip()) if env("YOLOV5_REPO", "").strip() else ""

# Tracking configuration
TRACK_MAX_DISAPPEARED = env_int_required("TRACK_MAX_DISAPPEARED")
TRACK_MAX_DISTANCE = env_float_required("TRACK_MAX_DISTANCE")
TRACK_CONFIRM_FRAMES = max(1, env_int_required("TRACK_CONFIRM_FRAMES"))
REID_MATCH_THRESHOLD = env_float("REID_MATCH_THRESHOLD", 0.77)
REID_MIN_TRACK_FRAMES = max(1, env_int("REID_MIN_TRACK_FRAMES", 3))
REID_STRONG_MATCH_THRESHOLD = env_float(
    "REID_STRONG_MATCH_THRESHOLD",
    max(REID_MATCH_THRESHOLD + 0.06, 0.86),
)
REID_AMBIGUITY_MARGIN = max(0.0, env_float("REID_AMBIGUITY_MARGIN", 0.04))
REID_PROTOTYPE_ALPHA = min(1.0, max(0.01, env_float("REID_PROTOTYPE_ALPHA", 0.18)))

# Face recognition configuration
FACE_RECOGNITION_ENABLED = env_bool_required("FACE_RECOGNITION_ENABLED")
INSIGHTFACE_MODEL_NAME = env_required("INSIGHTFACE_MODEL_NAME")
INSIGHTFACE_DET_SIZE = env_int_required("INSIGHTFACE_DET_SIZE")
INSIGHTFACE_PROVIDERS = [
    provider.strip()
    for provider in env_required("INSIGHTFACE_PROVIDERS").split(",")
    if provider.strip()
]
EMPLOYEE_MATCH_THRESHOLD = env_float_required("EMPLOYEE_MATCH_THRESHOLD")
EMPLOYEE_REGISTRY_REFRESH_SECONDS = env_int_required("EMPLOYEE_REGISTRY_REFRESH_SECONDS")
FACE_RECHECK_SECONDS = env_float_required("FACE_RECHECK_SECONDS")
FACE_UNKNOWN_TIMEOUT = env_float_required("FACE_UNKNOWN_TIMEOUT")
FACE_DETECTION_FRAME_INTERVAL = max(1, env_int("FACE_DETECTION_FRAME_INTERVAL", 3))

# Backend API configuration
BACKEND_URL = env_required("BACKEND_URL")
INGEST_URL = f"{BACKEND_URL}/api/events/ingest"
AUTH_USER = env_required("EDGE_AUTH_USERNAME")
AUTH_PASS = env_required("EDGE_AUTH_PASSWORD")
