"""Configuration management for the edge worker and video test profile."""
import os
from pathlib import Path
from typing import Iterable, Optional

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


def _first_env_value(names: Iterable[str]) -> Optional[str]:
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            return raw.strip()
    return None


def env(name: str, default: str = "") -> str:
    """Get environment variable with default value."""
    return os.getenv(name, default)


def env_alias(names: Iterable[str], default: str = "") -> str:
    """Get the first non-empty value from an ordered list of env names."""
    raw = _first_env_value(names)
    if raw is None:
        return default
    return raw


def env_required(name: str) -> str:
    """Get a required environment variable."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return raw.strip()


def env_required_alias(names: Iterable[str]) -> str:
    """Get a required env value from multiple candidate names."""
    raw = _first_env_value(names)
    if raw is None:
        joined = ", ".join(names)
        raise RuntimeError(f"Missing required environment variable. Expected one of: {joined}")
    return raw


def env_int(name: str, default: int) -> int:
    """Parse integer environment variables safely."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return default


def env_int_alias(names: Iterable[str], default: int) -> int:
    """Parse the first available integer env value from aliases."""
    raw = _first_env_value(names)
    if raw is None:
        return default
    try:
        return int(raw)
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


def env_float_alias(names: Iterable[str], default: float) -> float:
    """Parse the first available float env value from aliases."""
    raw = _first_env_value(names)
    if raw is None:
        return default
    try:
        return float(raw)
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


def env_bool_alias(names: Iterable[str], default: bool = False) -> bool:
    """Parse the first available bool-like env value from aliases."""
    raw = _first_env_value(names)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def env_bool_required(name: str) -> bool:
    """Parse a required bool-like environment variable."""
    return env_required(name).lower() in {"1", "true", "yes", "on"}


def _optional_project_path(value: str) -> str:
    raw = (value or "").strip()
    return resolve_project_path(raw) if raw else ""


def _resolved_existing_path(preferred: str, fallback: str = "") -> str:
    preferred_path = Path(resolve_project_path(preferred))
    if preferred_path.exists():
        return str(preferred_path)

    fallback_raw = (fallback or "").strip()
    if fallback_raw:
        fallback_path = Path(resolve_project_path(fallback_raw))
        if fallback_path.exists():
            return str(fallback_path)

    return str(preferred_path)


# App environment — controls log verbosity (dev=DEBUG, else INFO)
APP_ENV = env("APP_ENV", "production").strip().lower()

# Compatibility profile for offline video testing.
TEST_MODE = env_alias(("TEST_MODE", "EDGE_TEST_MODE"), "").strip().lower()
TEST_INPUT = _optional_project_path(env_alias(("TEST_INPUT", "EDGE_TEST_INPUT"), ""))
TEST_OUTPUT_DIR = resolve_project_path(env_alias(("TEST_OUTPUT_DIR", "EDGE_TEST_OUTPUT_DIR"), "test/output"))
TEST_OUTPUT_NAME = env_alias(("TEST_OUTPUT_NAME", "EDGE_TEST_OUTPUT_NAME"), "").strip()
TEST_ROI_JSON = env_alias(("TEST_ROI_JSON", "EDGE_TEST_ROI_JSON"), "").strip()
TEST_FRAME_WIDTH = max(1, env_int_alias(("TEST_FRAME_WIDTH", "EDGE_TEST_FRAME_WIDTH"), 1280))
TEST_FRAME_HEIGHT = max(1, env_int_alias(("TEST_FRAME_HEIGHT", "EDGE_TEST_FRAME_HEIGHT"), 720))
TEST_KEEP_SOURCE_SIZE = env_bool_alias(("TEST_KEEP_SOURCE_SIZE", "EDGE_TEST_KEEP_SOURCE_SIZE"), False)
TEST_MAX_FRAMES = max(0, env_int_alias(("TEST_MAX_FRAMES", "EDGE_TEST_MAX_FRAMES"), 0))
TEST_MAX_SECONDS = max(0.0, env_float_alias(("TEST_MAX_SECONDS", "EDGE_TEST_MAX_SECONDS"), 0.0))
TEST_FRAME_STEP = max(1, env_int_alias(("TEST_FRAME_STEP", "EDGE_TEST_FRAME_STEP"), 1))
TEST_OUTPUT_FPS = max(0.0, env_float_alias(("TEST_OUTPUT_FPS", "EDGE_TEST_OUTPUT_FPS"), 0.0))

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
YOLO_BACKEND = env_alias(("YOLO_BACKEND", "BACKEND"), "yolov5").strip().lower()
CONF_TH = env_float_alias(("YOLO_CONF", "YOLOV5_CONF"), 0.45)
IOU_TH = env_float_alias(("YOLO_IOU", "YOLOV5_IOU"), 0.45)
IMG_SIZE = max(32, env_int_alias(("YOLO_IMG_SIZE", "YOLOV5_IMG_SIZE"), 640))
# Device: "cpu", "cuda", "xpu" (Intel GPU), or "auto" (auto-detect)
DEVICE = env_alias(("YOLO_DEVICE", "YOLOV5_DEVICE"), "auto").strip() or "auto"
WEIGHTS = _resolved_existing_path(
    env_required_alias(("YOLO_WEIGHTS", "YOLOV5_WEIGHTS")),
    env("YOLOV5_WEIGHTS", ""),
)
REPO_RAW = env_alias(("YOLO_REPO", "YOLOV5_REPO"), "").strip()
REPO = resolve_project_path(REPO_RAW) if REPO_RAW else ""

# Duplicate suppression before tracking.
SUPPRESS_NESTED_DUPLICATES = env_bool_alias(("SUPPRESS_NESTED_DUPLICATES",), True)
DUPLICATE_CONTAINMENT_THRESHOLD = min(
    1.0,
    max(0.0, env_float_alias(("DUPLICATE_CONTAINMENT_THRESHOLD",), 0.9)),
)

# Tracking configuration
FORCE_CENTROID = env_bool_alias(("FORCE_CENTROID",), False)
TRACK_MAX_DISAPPEARED = max(0, env_int_alias(("TRACK_MAX_AGE", "TRACK_MAX_DISAPPEARED"), 30))
TRACK_MAX_DISTANCE = max(0.0, env_float_alias(("TRACK_MAX_DISTANCE",), 80.0))
TRACK_CONFIRM_FRAMES = max(1, env_int_alias(("TRACK_N_INIT", "TRACK_CONFIRM_FRAMES"), 3))
TRACK_MAX_COSINE_DISTANCE = max(0.0, env_float_alias(("TRACK_MAX_COSINE_DISTANCE",), 0.3))
IDENTITY_MODE = env_alias(("IDENTITY_MODE",), "reid").strip().lower() or "reid"
FACE_ID_MATCH_THRESHOLD = env_float_alias(("FACE_ID_MATCH_THRESHOLD",), 0.55)
FACE_ID_MIN_TRACK_FRAMES = max(1, env_int_alias(("FACE_ID_MIN_TRACK_FRAMES",), 3))
FACE_ID_STRONG_MATCH_THRESHOLD = env_float_alias(("FACE_ID_STRONG_MATCH_THRESHOLD",), 0.65)
FACE_ID_AMBIGUITY_MARGIN = max(0.0, env_float_alias(("FACE_ID_AMBIGUITY_MARGIN",), 0.03))
FACE_ID_PROTOTYPE_ALPHA = min(1.0, max(0.01, env_float_alias(("FACE_ID_PROTOTYPE_ALPHA",), 0.18)))

reid_default_match_threshold = FACE_ID_MATCH_THRESHOLD if IDENTITY_MODE == "face" else 0.77
reid_default_min_track_frames = FACE_ID_MIN_TRACK_FRAMES if IDENTITY_MODE == "face" else 3
reid_default_strong_match_threshold = FACE_ID_STRONG_MATCH_THRESHOLD if IDENTITY_MODE == "face" else 0.86
reid_default_ambiguity_margin = FACE_ID_AMBIGUITY_MARGIN if IDENTITY_MODE == "face" else 0.04
reid_default_prototype_alpha = FACE_ID_PROTOTYPE_ALPHA if IDENTITY_MODE == "face" else 0.18

REID_MATCH_THRESHOLD = env_float("REID_MATCH_THRESHOLD", reid_default_match_threshold)
REID_MIN_TRACK_FRAMES = max(1, env_int("REID_MIN_TRACK_FRAMES", reid_default_min_track_frames))
REID_STRONG_MATCH_THRESHOLD = env_float(
    "REID_STRONG_MATCH_THRESHOLD",
    max(REID_MATCH_THRESHOLD + 0.06, reid_default_strong_match_threshold),
)
REID_AMBIGUITY_MARGIN = max(0.0, env_float("REID_AMBIGUITY_MARGIN", reid_default_ambiguity_margin))
REID_PROTOTYPE_ALPHA = min(1.0, max(0.01, env_float("REID_PROTOTYPE_ALPHA", reid_default_prototype_alpha)))

# Face recognition configuration
FACE_RECOGNITION_ENABLED = env_bool_alias(("WITH_FACE_RECOGNITION", "FACE_RECOGNITION_ENABLED"), False)
FACE_REGISTRY_SOURCE = env_alias(("FACE_REGISTRY_SOURCE",), "backend").strip().lower() or "backend"
EDGE_EMPLOYEE_FACES_DIR = resolve_project_path(
    env_alias(("EDGE_EMPLOYEE_FACES_DIR", "EMPLOYEE_FACES_DIR"), "./backend/storage/employee_faces")
)
INSIGHTFACE_MODEL_NAME = env_required("INSIGHTFACE_MODEL_NAME")
INSIGHTFACE_DET_SIZE = env_int_required("INSIGHTFACE_DET_SIZE")
INSIGHTFACE_PROVIDERS = [
    provider.strip()
    for provider in env_required("INSIGHTFACE_PROVIDERS").split(",")
    if provider.strip()
]
EMPLOYEE_MATCH_THRESHOLD = env_float("EMPLOYEE_MATCH_THRESHOLD", 0.45)
EMPLOYEE_REGISTRY_REFRESH_SECONDS = env_int("EMPLOYEE_REGISTRY_REFRESH_SECONDS", 60)
FACE_RECHECK_SECONDS = env_float("FACE_RECHECK_SECONDS", 0.8)
FACE_UNKNOWN_TIMEOUT = env_float("FACE_UNKNOWN_TIMEOUT", 2.5)
FACE_DETECTION_FRAME_INTERVAL = max(1, env_int("FACE_DETECTION_FRAME_INTERVAL", 3))

# Backend API configuration
BACKEND_URL = env_required("BACKEND_URL")
INGEST_URL = f"{BACKEND_URL}/api/events/ingest"
AUTH_USER = env_required("EDGE_AUTH_USERNAME")
AUTH_PASS = env_required("EDGE_AUTH_PASSWORD")
