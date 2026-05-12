"""Main processing loop for the edge worker."""
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .api_client import (
    get_camera_config,
    get_counting_areas,
    get_employee_registry,
    get_runtime_config,
    login_token,
    send_visitor_event,
)
from . import capture as capture_module
from . import config as config_module
from . import detection as detection_module
from . import face_recognition as face_module
from . import reid as reid_module
from . import streaming as streaming_module
from .capture import LatestFrameCapture
from .config import (
    CAMERA_ID,
    CONFIG_REFRESH,
    EDGE_FILE_FRAME_STEP,
    EDGE_LOCAL_FILE_REPLAY_POST_EVENTS,
    EDGE_PROCESSING_MAX_FPS,
    EDGE_RECORDING_ENABLED,
    EDGE_RECORDING_FILE_PREFIX,
    EDGE_RECORDING_FPS,
    EDGE_RECORDING_MAX_GAP_SECONDS,
    EDGE_RECORDING_OUTPUT_DIR,
    EDGE_RECORDING_SAVE_MODE,
    EDGE_RECORDING_SEGMENT_MINUTES,
    EDGE_RECORDING_SEGMENT_SECONDS,
    EDGE_STREAM_JPEG_QUALITY,
    EDGE_STREAM_MAX_FPS,
    EDGE_STREAM_URL,
    FACE_DETECTION_FRAME_INTERVAL,
    FACE_REGISTRY_SOURCE,
    FORCE_CENTROID,
    IDENTITY_MODE,
    IMG_SIZE,
    TEST_FRAME_HEIGHT,
    TEST_FRAME_STEP,
    TEST_FRAME_WIDTH,
    TEST_INPUT,
    TEST_KEEP_SOURCE_SIZE,
    TEST_MAX_FRAMES,
    TEST_MAX_SECONDS,
    TEST_MODE,
    TEST_OUTPUT_DIR,
    TEST_OUTPUT_FPS,
    TEST_OUTPUT_NAME,
    TEST_ROI_JSON,
    BYTETRACK_HIGH_THRESH,
    BYTETRACK_LOW_THRESH,
    BYTETRACK_MATCH_THRESH,
    BYTETRACK_MIN_BOX_AREA,
    BYTETRACK_NEW_TRACK_THRESH,
    TRACK_CONFIRM_FRAMES,
    TRACK_ENTRY_CONFIRM_FRAMES,
    TRACK_EVENT_COOLDOWN_SECONDS,
    TRACK_EXIT_ALLOW_WITHOUT_ENTRY,
    TRACK_EXIT_BOTTOM_MARGIN,
    TRACK_EXIT_BOTTOM_CONFIRM_FRAMES,
    TRACK_EXIT_CONFIRM_FRAMES,
    TRACK_EXIT_EDGE_MARGIN,
    TRACK_EXIT_GATE_APPROACH_FRAMES,
    TRACK_EXIT_HEAD_CONFIRM_FRAMES,
    TRACK_EXIT_HEAD_RATIO,
    TRACK_EXIT_MIN_DELTA_Y,
    TRACK_EXIT_WITHOUT_ENTRY_MIN_FRAMES,
    TRACK_MAX_COSINE_DISTANCE,
    TRACK_MAX_DISAPPEARED,
    TRACK_MAX_DISTANCE,
    TRACK_REENTRY_COOLDOWN_SECONDS,
    TRACK_ROI_POINT,
    TRACK_SAME_TRACK_OUT_COOLDOWN_SECONDS,
    TRACKER_METHOD,
)
from .detection import load_model, parse_roi, point_in_roi, suppress_duplicate_person_detections
from .face_recognition import EmployeeFaceRecognizer
from .logger import get_logger
from .reid import cleanup_old_tracks, reset_daily_cache, update_track_identity
from .recording import SegmentedVideoRecorder
from .streaming import has_raw_stream_clients, update_latest_frame
from .tracker import ByteTrackTracker, CentroidTracker, DEEPSORT_AVAILABLE, DeepSORTTracker
from .visualization import draw_bounding_boxes, draw_exit_gate, draw_info_overlay, draw_roi_polygon

log = get_logger("loops")

EVENT_COOLDOWN = TRACK_EVENT_COOLDOWN_SECONDS
REFERENCE_FRAME_SIZE = (TEST_FRAME_WIDTH, TEST_FRAME_HEIGHT)
_TRACKER_REBUILD_KEYS = {
    "TRACKER_METHOD",
    "FORCE_CENTROID",
    "TRACK_MAX_AGE",
    "TRACK_N_INIT",
    "TRACK_MAX_DISTANCE",
    "TRACK_MAX_COSINE_DISTANCE",
    "BYTETRACK_HIGH_THRESH",
    "BYTETRACK_LOW_THRESH",
    "BYTETRACK_MATCH_THRESH",
    "BYTETRACK_NEW_TRACK_THRESH",
    "BYTETRACK_MIN_BOX_AREA",
}
_RECORDING_REBUILD_KEYS = {
    "EDGE_RECORDING_ENABLED",
    "EDGE_RECORDING_SAVE_MODE",
    "EDGE_RECORDING_SEGMENT_MINUTES",
    "EDGE_RECORDING_FPS",
    "EDGE_RECORDING_MAX_GAP_SECONDS",
}


def _runtime_values(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    values = payload.get("values")
    if isinstance(values, dict):
        return values
    items = payload.get("items")
    if isinstance(items, list):
        return {
            str(item.get("key")): item.get("value")
            for item in items
            if isinstance(item, dict) and item.get("key")
        }
    return {}


def _runtime_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _runtime_int(value: Any, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _runtime_float(
    value: Any,
    default: float,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _set_loop_global(name: str, value: Any) -> bool:
    previous = globals().get(name)
    if previous == value:
        return False
    globals()[name] = value
    return True


def _set_module_global(module: Any, name: str, value: Any) -> None:
    if hasattr(module, name):
        setattr(module, name, value)


def _set_across_modules(name: str, value: Any, modules: Tuple[Any, ...]) -> bool:
    changed = _set_loop_global(name, value)
    for module in modules:
        _set_module_global(module, name, value)
    return changed


def _apply_yolo_thresholds(model: Any, conf: Optional[float], iou: Optional[float]) -> None:
    if model is None:
        return
    if conf is not None:
        if hasattr(model, "_conf"):
            model._conf = conf
        if hasattr(model, "conf"):
            model.conf = conf
    if iou is not None:
        if hasattr(model, "_iou"):
            model._iou = iou
        if hasattr(model, "iou"):
            model.iou = iou


def _effective_detector_conf() -> float:
    """Lower detector threshold only when ByteTrack needs low-confidence boxes."""
    tracker_method = str(globals().get("TRACKER_METHOD", "auto") or "auto").strip().lower()
    if tracker_method == "bytetrack":
        return min(float(detection_module.CONF_TH), float(BYTETRACK_LOW_THRESH))
    return float(detection_module.CONF_TH)


def _apply_runtime_config(payload: Dict[str, Any], model: Any) -> Dict[str, Any]:
    values = _runtime_values(payload)
    if not values:
        return {"tracker_rebuild": False, "changed": []}

    changed: List[str] = []
    tracker_rebuild = False
    recording_rebuild = False

    def mark(key: str, did_change: bool) -> None:
        nonlocal tracker_rebuild, recording_rebuild
        if not did_change:
            return
        changed.append(key)
        if key in _TRACKER_REBUILD_KEYS:
            tracker_rebuild = True
        if key in _RECORDING_REBUILD_KEYS:
            recording_rebuild = True

    if "EDGE_STREAM_URL" in values:
        stream_url_value = str(values.get("EDGE_STREAM_URL") or "").strip()
        mark(
            "EDGE_STREAM_URL",
            _set_across_modules("EDGE_STREAM_URL", stream_url_value, (config_module, streaming_module)),
        )

    if "EDGE_CONFIG_REFRESH_SECONDS" in values:
        refresh_seconds = _runtime_int(values["EDGE_CONFIG_REFRESH_SECONDS"], CONFIG_REFRESH, minimum=1)
        mark("EDGE_CONFIG_REFRESH_SECONDS", _set_across_modules("CONFIG_REFRESH", refresh_seconds, (config_module,)))

    if "EDGE_PROCESSING_MAX_FPS" in values:
        processing_fps = _runtime_float(values["EDGE_PROCESSING_MAX_FPS"], EDGE_PROCESSING_MAX_FPS, minimum=0.0)
        mark(
            "EDGE_PROCESSING_MAX_FPS",
            _set_across_modules("EDGE_PROCESSING_MAX_FPS", processing_fps, (config_module, streaming_module)),
        )

    if "EDGE_STREAM_MAX_FPS" in values:
        stream_fps = _runtime_float(values["EDGE_STREAM_MAX_FPS"], EDGE_STREAM_MAX_FPS, minimum=0.0)
        mark(
            "EDGE_STREAM_MAX_FPS",
            _set_across_modules("EDGE_STREAM_MAX_FPS", stream_fps, (config_module, streaming_module)),
        )

    if "EDGE_STREAM_JPEG_QUALITY" in values:
        jpeg_quality = _runtime_int(values["EDGE_STREAM_JPEG_QUALITY"], 65, minimum=10, maximum=95)
        mark(
            "EDGE_STREAM_JPEG_QUALITY",
            _set_across_modules("EDGE_STREAM_JPEG_QUALITY", jpeg_quality, (config_module, streaming_module)),
        )

    if "EDGE_FILE_FRAME_STEP" in values:
        file_frame_step = _runtime_int(values["EDGE_FILE_FRAME_STEP"], EDGE_FILE_FRAME_STEP, minimum=1)
        previous = getattr(capture_module, "EDGE_FILE_FRAME_STEP", file_frame_step)
        capture_module.EDGE_FILE_FRAME_STEP = file_frame_step
        _set_module_global(config_module, "EDGE_FILE_FRAME_STEP", file_frame_step)
        if previous != file_frame_step:
            changed.append("EDGE_FILE_FRAME_STEP")

    if "EDGE_LOCAL_FILE_REPLAY_POST_EVENTS" in values:
        replay_events = _runtime_bool(
            values["EDGE_LOCAL_FILE_REPLAY_POST_EVENTS"],
            EDGE_LOCAL_FILE_REPLAY_POST_EVENTS,
        )
        mark(
            "EDGE_LOCAL_FILE_REPLAY_POST_EVENTS",
            _set_across_modules(
                "EDGE_LOCAL_FILE_REPLAY_POST_EVENTS",
                replay_events,
                (config_module,),
            ),
        )

    if "EDGE_RECORDING_ENABLED" in values:
        recording_enabled = _runtime_bool(values["EDGE_RECORDING_ENABLED"], EDGE_RECORDING_ENABLED)
        mark(
            "EDGE_RECORDING_ENABLED",
            _set_across_modules("EDGE_RECORDING_ENABLED", recording_enabled, (config_module,)),
        )

    if "EDGE_RECORDING_SAVE_MODE" in values:
        recording_mode = config_module.normalize_recording_save_mode(
            str(values["EDGE_RECORDING_SAVE_MODE"] or "detection")
        )
        mark(
            "EDGE_RECORDING_SAVE_MODE",
            _set_across_modules("EDGE_RECORDING_SAVE_MODE", recording_mode, (config_module,)),
        )

    if "EDGE_RECORDING_SEGMENT_MINUTES" in values:
        segment_minutes = _runtime_int(
            values["EDGE_RECORDING_SEGMENT_MINUTES"],
            EDGE_RECORDING_SEGMENT_MINUTES,
            minimum=1,
        )
        did_change = _set_across_modules("EDGE_RECORDING_SEGMENT_MINUTES", segment_minutes, (config_module,))
        did_change = (
            _set_across_modules("EDGE_RECORDING_SEGMENT_SECONDS", segment_minutes * 60, (config_module,))
            or did_change
        )
        mark("EDGE_RECORDING_SEGMENT_MINUTES", did_change)

    if "EDGE_RECORDING_FPS" in values:
        recording_fps = _runtime_float(values["EDGE_RECORDING_FPS"], EDGE_RECORDING_FPS, minimum=0.0)
        mark(
            "EDGE_RECORDING_FPS",
            _set_across_modules("EDGE_RECORDING_FPS", recording_fps, (config_module,)),
        )

    if "EDGE_RECORDING_MAX_GAP_SECONDS" in values:
        recording_gap = _runtime_float(
            values["EDGE_RECORDING_MAX_GAP_SECONDS"],
            EDGE_RECORDING_MAX_GAP_SECONDS,
            minimum=1.0,
        )
        mark(
            "EDGE_RECORDING_MAX_GAP_SECONDS",
            _set_across_modules("EDGE_RECORDING_MAX_GAP_SECONDS", recording_gap, (config_module,)),
        )

    if "YOLO_BACKEND" in values:
        yolo_backend = str(values["YOLO_BACKEND"] or "yolov5").strip().lower() or "yolov5"
        mark(
            "YOLO_BACKEND",
            _set_across_modules("YOLO_BACKEND", yolo_backend, (config_module, detection_module, streaming_module)),
        )

    if "YOLOV5_WEIGHTS" in values:
        raw_weights = str(values["YOLOV5_WEIGHTS"] or "./edge/yolov5s.pt").strip() or "./edge/yolov5s.pt"
        weights = config_module.resolve_existing_project_path(raw_weights, "")
        mark(
            "YOLOV5_WEIGHTS",
            _set_across_modules("WEIGHTS", weights, (config_module, detection_module, streaming_module)),
        )

    if "YOLO_REPO" in values:
        repo_raw = str(values["YOLO_REPO"] or "").strip()
        repo_path = config_module.resolve_project_path(repo_raw) if repo_raw else ""
        _set_module_global(config_module, "REPO_RAW", repo_raw)
        mark("YOLO_REPO", _set_across_modules("REPO", repo_path, (config_module, detection_module)))

    if "YOLO_DEVICE" in values:
        yolo_device = str(values["YOLO_DEVICE"] or "auto").strip() or "auto"
        mark(
            "YOLO_DEVICE",
            _set_across_modules("DEVICE", yolo_device, (config_module, detection_module, streaming_module)),
        )

    yolo_conf = None
    if "YOLO_CONF" in values:
        yolo_conf = _runtime_float(values["YOLO_CONF"], detection_module.CONF_TH, minimum=0.0, maximum=1.0)
        previous = getattr(detection_module, "CONF_TH", yolo_conf)
        detection_module.CONF_TH = yolo_conf
        streaming_module.CONF_TH = yolo_conf
        config_module.CONF_TH = yolo_conf
        if previous != yolo_conf:
            changed.append("YOLO_CONF")

    yolo_iou = None
    if "YOLO_IOU" in values:
        yolo_iou = _runtime_float(values["YOLO_IOU"], detection_module.IOU_TH, minimum=0.0, maximum=1.0)
        previous = getattr(detection_module, "IOU_TH", yolo_iou)
        detection_module.IOU_TH = yolo_iou
        streaming_module.IOU_TH = yolo_iou
        config_module.IOU_TH = yolo_iou
        if previous != yolo_iou:
            changed.append("YOLO_IOU")

    detector_threshold_refresh = yolo_conf is not None or yolo_iou is not None

    if "YOLO_IMG_SIZE" in values:
        img_size = _runtime_int(values["YOLO_IMG_SIZE"], IMG_SIZE, minimum=32)
        mark("YOLO_IMG_SIZE", _set_across_modules("IMG_SIZE", img_size, (config_module, streaming_module)))

    if "SUPPRESS_NESTED_DUPLICATES" in values:
        suppress_duplicates = _runtime_bool(
            values["SUPPRESS_NESTED_DUPLICATES"],
            detection_module.SUPPRESS_NESTED_DUPLICATES,
        )
        previous = getattr(detection_module, "SUPPRESS_NESTED_DUPLICATES", suppress_duplicates)
        detection_module.SUPPRESS_NESTED_DUPLICATES = suppress_duplicates
        streaming_module.SUPPRESS_NESTED_DUPLICATES = suppress_duplicates
        config_module.SUPPRESS_NESTED_DUPLICATES = suppress_duplicates
        if previous != suppress_duplicates:
            changed.append("SUPPRESS_NESTED_DUPLICATES")

    if "DUPLICATE_CONTAINMENT_THRESHOLD" in values:
        containment = _runtime_float(
            values["DUPLICATE_CONTAINMENT_THRESHOLD"],
            detection_module.DUPLICATE_CONTAINMENT_THRESHOLD,
            minimum=0.0,
            maximum=1.0,
        )
        previous = getattr(detection_module, "DUPLICATE_CONTAINMENT_THRESHOLD", containment)
        detection_module.DUPLICATE_CONTAINMENT_THRESHOLD = containment
        streaming_module.DUPLICATE_CONTAINMENT_THRESHOLD = containment
        config_module.DUPLICATE_CONTAINMENT_THRESHOLD = containment
        if previous != containment:
            changed.append("DUPLICATE_CONTAINMENT_THRESHOLD")

    if "DUPLICATE_IOU_THRESHOLD" in values:
        duplicate_iou = _runtime_float(
            values["DUPLICATE_IOU_THRESHOLD"],
            detection_module.DUPLICATE_IOU_THRESHOLD,
            minimum=0.0,
            maximum=1.0,
        )
        previous = getattr(detection_module, "DUPLICATE_IOU_THRESHOLD", duplicate_iou)
        detection_module.DUPLICATE_IOU_THRESHOLD = duplicate_iou
        streaming_module.DUPLICATE_IOU_THRESHOLD = duplicate_iou
        config_module.DUPLICATE_IOU_THRESHOLD = duplicate_iou
        if previous != duplicate_iou:
            changed.append("DUPLICATE_IOU_THRESHOLD")

    if "TRACKER_METHOD" in values:
        tracker_method = str(values["TRACKER_METHOD"] or "auto").strip().lower() or "auto"
        if tracker_method not in {"auto", "deepsort", "bytetrack", "centroid"}:
            tracker_method = "auto"
        mark(
            "TRACKER_METHOD",
            _set_across_modules("TRACKER_METHOD", tracker_method, (config_module, streaming_module)),
        )

    tracker_fields = {
        "FORCE_CENTROID": ("FORCE_CENTROID", _runtime_bool, False, (config_module, streaming_module)),
        "TRACK_MAX_AGE": ("TRACK_MAX_DISAPPEARED", _runtime_int, 0, (config_module, streaming_module)),
        "TRACK_N_INIT": ("TRACK_CONFIRM_FRAMES", _runtime_int, 1, (config_module, streaming_module)),
        "TRACK_MAX_DISTANCE": ("TRACK_MAX_DISTANCE", _runtime_float, 0.0, (config_module, streaming_module)),
        "TRACK_MAX_COSINE_DISTANCE": (
            "TRACK_MAX_COSINE_DISTANCE",
            _runtime_float,
            0.0,
            (config_module, streaming_module),
        ),
        "BYTETRACK_HIGH_THRESH": ("BYTETRACK_HIGH_THRESH", _runtime_float, 0.0, (config_module, streaming_module)),
        "BYTETRACK_LOW_THRESH": ("BYTETRACK_LOW_THRESH", _runtime_float, 0.0, (config_module, streaming_module)),
        "BYTETRACK_MATCH_THRESH": ("BYTETRACK_MATCH_THRESH", _runtime_float, 0.0, (config_module, streaming_module)),
        "BYTETRACK_NEW_TRACK_THRESH": (
            "BYTETRACK_NEW_TRACK_THRESH",
            _runtime_float,
            0.0,
            (config_module, streaming_module),
        ),
        "BYTETRACK_MIN_BOX_AREA": ("BYTETRACK_MIN_BOX_AREA", _runtime_float, 0.0, (config_module, streaming_module)),
    }
    for env_key, (global_name, caster, minimum, modules) in tracker_fields.items():
        if env_key not in values:
            continue
        default = globals().get(global_name)
        if caster is _runtime_bool:
            parsed = caster(values[env_key], bool(default))
        else:
            parsed = caster(values[env_key], default, minimum=minimum)
        mark(env_key, _set_across_modules(global_name, parsed, modules))

    if any(key in changed for key in ("TRACKER_METHOD", "BYTETRACK_LOW_THRESH")):
        detector_threshold_refresh = True

    if detector_threshold_refresh:
        _apply_yolo_thresholds(model, _effective_detector_conf(), yolo_iou)

    live_loop_fields = {
        "TRACK_ROI_POINT": ("TRACK_ROI_POINT", str),
        "TRACK_ENTRY_CONFIRM_FRAMES": ("TRACK_ENTRY_CONFIRM_FRAMES", int),
        "TRACK_EXIT_CONFIRM_FRAMES": ("TRACK_EXIT_CONFIRM_FRAMES", int),
        "TRACK_EXIT_BOTTOM_CONFIRM_FRAMES": ("TRACK_EXIT_BOTTOM_CONFIRM_FRAMES", int),
        "TRACK_EXIT_EDGE_MARGIN": ("TRACK_EXIT_EDGE_MARGIN", float),
        "TRACK_EXIT_BOTTOM_MARGIN": ("TRACK_EXIT_BOTTOM_MARGIN", float),
        "TRACK_EXIT_MIN_DELTA_Y": ("TRACK_EXIT_MIN_DELTA_Y", float),
        "TRACK_EXIT_ALLOW_WITHOUT_ENTRY": ("TRACK_EXIT_ALLOW_WITHOUT_ENTRY", bool),
        "TRACK_EXIT_WITHOUT_ENTRY_MIN_FRAMES": ("TRACK_EXIT_WITHOUT_ENTRY_MIN_FRAMES", int),
        "TRACK_EVENT_COOLDOWN_SECONDS": ("TRACK_EVENT_COOLDOWN_SECONDS", float),
        "TRACK_SAME_TRACK_OUT_COOLDOWN_SECONDS": ("TRACK_SAME_TRACK_OUT_COOLDOWN_SECONDS", float),
        "TRACK_REENTRY_COOLDOWN_SECONDS": ("TRACK_REENTRY_COOLDOWN_SECONDS", float),
        "IDENTITY_MODE": ("IDENTITY_MODE", str),
    }
    for env_key, (global_name, value_type) in live_loop_fields.items():
        if env_key not in values:
            continue
        default = globals().get(global_name)
        if value_type is bool:
            parsed = _runtime_bool(values[env_key], bool(default))
        elif value_type is int:
            parsed = _runtime_int(values[env_key], int(default), minimum=1)
        elif value_type is float:
            parsed = _runtime_float(values[env_key], float(default), minimum=0.0)
        else:
            parsed = str(values[env_key] or "").strip().lower() or str(default)
        did_change = _set_across_modules(global_name, parsed, (config_module, streaming_module))
        if global_name == "TRACK_EVENT_COOLDOWN_SECONDS":
            _set_loop_global("EVENT_COOLDOWN", parsed)
        mark(env_key, did_change)

    reid_fields = {
        "REID_MATCH_THRESHOLD": ("REID_MATCH_THRESHOLD", float, 0.0, 1.0),
        "REID_MIN_TRACK_FRAMES": ("REID_MIN_TRACK_FRAMES", int, 1, None),
        "REID_STRONG_MATCH_THRESHOLD": ("REID_STRONG_MATCH_THRESHOLD", float, 0.0, 1.0),
        "REID_AMBIGUITY_MARGIN": ("REID_AMBIGUITY_MARGIN", float, 0.0, 1.0),
        "REID_PROTOTYPE_ALPHA": ("REID_PROTOTYPE_ALPHA", float, 0.01, 1.0),
    }
    for env_key, (global_name, value_type, minimum, maximum) in reid_fields.items():
        if env_key not in values:
            continue
        default = getattr(reid_module, global_name)
        if value_type is int:
            parsed = _runtime_int(values[env_key], int(default), minimum=int(minimum))
        else:
            parsed = _runtime_float(values[env_key], float(default), minimum=minimum, maximum=maximum)
        previous = getattr(reid_module, global_name)
        setattr(reid_module, global_name, parsed)
        _set_module_global(config_module, global_name, parsed)
        _set_module_global(streaming_module, global_name, parsed)
        if previous != parsed:
            changed.append(env_key)

    face_fields = {
        "EMPLOYEE_MATCH_THRESHOLD": ("EMPLOYEE_MATCH_THRESHOLD", float, 0.0, 1.0),
        "EMPLOYEE_REGISTRY_REFRESH_SECONDS": ("EMPLOYEE_REGISTRY_REFRESH_SECONDS", int, 1, None),
        "FACE_RECHECK_SECONDS": ("FACE_RECHECK_SECONDS", float, 0.0, 60.0),
        "FACE_UNKNOWN_TIMEOUT": ("FACE_UNKNOWN_TIMEOUT", float, 0.0, 120.0),
        "FACE_DETECTION_FRAME_INTERVAL": ("FACE_DETECTION_FRAME_INTERVAL", int, 1, None),
    }
    for env_key, (global_name, value_type, minimum, maximum) in face_fields.items():
        if env_key not in values:
            continue
        default = getattr(face_module, global_name)
        if value_type is int:
            parsed = _runtime_int(values[env_key], int(default), minimum=int(minimum))
        else:
            parsed = _runtime_float(values[env_key], float(default), minimum=minimum, maximum=maximum)
        previous = getattr(face_module, global_name)
        setattr(face_module, global_name, parsed)
        _set_module_global(config_module, global_name, parsed)
        _set_module_global(streaming_module, global_name, parsed)
        if global_name == "FACE_DETECTION_FRAME_INTERVAL":
            _set_loop_global(global_name, parsed)
        if previous != parsed:
            changed.append(env_key)

    if "WITH_FACE_RECOGNITION" in values:
        face_enabled = _runtime_bool(values["WITH_FACE_RECOGNITION"], face_module.FACE_RECOGNITION_ENABLED)
        mark(
            "WITH_FACE_RECOGNITION",
            _set_across_modules(
                "FACE_RECOGNITION_ENABLED",
                face_enabled,
                (config_module, face_module, streaming_module),
            ),
        )

    if "FACE_REGISTRY_SOURCE" in values:
        registry_source = str(values["FACE_REGISTRY_SOURCE"] or "backend").strip().lower() or "backend"
        previous = getattr(face_module, "FACE_REGISTRY_SOURCE", registry_source)
        face_module.FACE_REGISTRY_SOURCE = registry_source
        _set_across_modules("FACE_REGISTRY_SOURCE", registry_source, (config_module, streaming_module))
        if previous != registry_source:
            changed.append("FACE_REGISTRY_SOURCE")

    if "EDGE_EMPLOYEE_FACES_DIR" in values:
        raw_employee_faces_dir = str(values["EDGE_EMPLOYEE_FACES_DIR"] or "").strip()
        employee_faces_dir = (
            config_module.resolve_project_path(raw_employee_faces_dir)
            if raw_employee_faces_dir
            else ""
        )
        previous = getattr(face_module, "EDGE_EMPLOYEE_FACES_DIR", employee_faces_dir)
        face_module.EDGE_EMPLOYEE_FACES_DIR = employee_faces_dir
        _set_module_global(config_module, "EDGE_EMPLOYEE_FACES_DIR", employee_faces_dir)
        _set_module_global(streaming_module, "EDGE_EMPLOYEE_FACES_DIR", employee_faces_dir)
        if previous != employee_faces_dir:
            changed.append("EDGE_EMPLOYEE_FACES_DIR")

    if changed:
        log.info("Applied runtime config update: %s", ", ".join(changed))

    return {
        "tracker_rebuild": tracker_rebuild,
        "recording_rebuild": recording_rebuild,
        "changed": changed,
        "stream_url": str(values.get("EDGE_STREAM_URL") or "").strip(),
    }


def _stable_identity_key(fallback_key: str, classification: Dict[str, Any]) -> str:
    if classification.get("person_type") == "EMPLOYEE" and classification.get("employee_id"):
        return f"employee_{classification['employee_id']}"
    return fallback_key


def _send_track_event(
    direction: str,
    track_id: int,
    visitor_key: str,
    area_id: Optional[int],
    now_time: datetime,
    avg_confidence: float,
    classification: Dict[str, Any],
    token: Optional[str],
) -> Dict[str, Any]:
    payload = {
        "camera_id": CAMERA_ID,
        "area_id": area_id,
        "event_time": now_time.isoformat(),
        "track_id": f"t{track_id}",
        "visitor_key": visitor_key,
        "direction": direction,
        "person_type": classification.get("person_type", "CUSTOMER"),
        "employee_id": classification.get("employee_id"),
        "face_match_score": (
            round(float(classification["match_score"]), 4)
            if classification.get("match_score") is not None
            else None
        ),
        "recognition_source": classification.get("recognition_source"),
        "confidence_avg": round(avg_confidence, 4),
    }
    return send_visitor_event(payload, token)


def _track_counting_point(track) -> Tuple[float, float]:
    """Use a stable body point for ROI tests; feet work better for gate crossing."""
    x1, y1, x2, y2 = track.bbox
    point_mode = TRACK_ROI_POINT
    center_x = (float(x1) + float(x2)) / 2.0
    if point_mode in {"feet", "foot", "bottom"}:
        return center_x, float(y2)
    if point_mode in {"head", "top"}:
        return center_x, float(y1)
    return float(track.centroid[0]), float(track.centroid[1])


def _bbox_center(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (float(x1) + float(x2)) / 2.0, (float(y1) + float(y2)) / 2.0


def _bbox_area_local(bbox: Tuple[float, float, float, float]) -> float:
    return max(0.0, float(bbox[2]) - float(bbox[0])) * max(0.0, float(bbox[3]) - float(bbox[1]))


def _bbox_iou_local(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float],
) -> float:
    inter_x1 = max(float(box_a[0]), float(box_b[0]))
    inter_y1 = max(float(box_a[1]), float(box_b[1]))
    inter_x2 = min(float(box_a[2]), float(box_b[2]))
    inter_y2 = min(float(box_a[3]), float(box_b[3]))
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    union = _bbox_area_local(box_a) + _bbox_area_local(box_b) - inter_area
    return inter_area / union if union > 0 else 0.0


def _same_spatial_region(
    bbox_a: Tuple[float, float, float, float],
    bbox_b: Tuple[float, float, float, float],
) -> bool:
    iou = _bbox_iou_local(bbox_a, bbox_b)
    if iou >= 0.16:
        return True

    ax, ay = _bbox_center(bbox_a)
    bx, by = _bbox_center(bbox_b)
    center_distance = float(np.linalg.norm(np.array([ax - bx, ay - by], dtype=np.float32)))
    scale = max(
        abs(float(bbox_a[2]) - float(bbox_a[0])),
        abs(float(bbox_a[3]) - float(bbox_a[1])),
        abs(float(bbox_b[2]) - float(bbox_b[0])),
        abs(float(bbox_b[3]) - float(bbox_b[1])),
        1.0,
    )
    return center_distance <= max(42.0, min(150.0, scale * 0.35))


def _bbox_near_frame_edge(
    bbox: Tuple[float, float, float, float],
    frame_width: int,
    frame_height: int,
    margin: float = TRACK_EXIT_EDGE_MARGIN,
) -> bool:
    x1, y1, x2, y2 = bbox
    return (
        float(x1) <= margin
        or float(y1) <= margin
        or float(x2) >= frame_width - margin
        or float(y2) >= frame_height - margin
    )


def _roi_bottom_y(roi: Optional[List[List[float]]], frame_height: int) -> float:
    if not roi:
        return float(frame_height)
    return max(float(point[1]) for point in roi)


def _bbox_in_bottom_exit_zone(
    bbox: Tuple[float, float, float, float],
    roi: Optional[List[List[float]]],
    frame_height: int,
    margin: float = TRACK_EXIT_BOTTOM_MARGIN,
) -> bool:
    if margin <= 0:
        return False

    bottom_y = float(bbox[3])
    roi_bottom = _roi_bottom_y(roi, frame_height)
    # For near-full-frame ROI, use the earlier of the ROI bottom band and frame bottom band.
    threshold = min(float(frame_height) - margin, roi_bottom - (margin * 0.35))
    threshold = max(0.0, threshold)
    return bottom_y >= threshold


def _exit_gate_y(roi: Optional[List[List[float]]], frame_height: int) -> int:
    roi_bottom = _roi_bottom_y(roi, frame_height)
    gate_y = min(
        float(frame_height) - TRACK_EXIT_BOTTOM_MARGIN,
        roi_bottom - (TRACK_EXIT_BOTTOM_MARGIN * 0.35),
    )
    return int(max(0.0, min(float(frame_height - 1), gate_y)))


def _state_cleared_exit_zone(state: Dict[str, Any]) -> bool:
    """Track must move away from the bottom gate before it can be counted OUT."""
    return bool(state.get("cleared_exit_zone"))


def _bbox_height(bbox: Tuple[float, float, float, float]) -> float:
    return max(1.0, float(bbox[3]) - float(bbox[1]))


def _bbox_near_bottom_edge(
    bbox: Tuple[float, float, float, float],
    frame_height: int,
    margin: float = TRACK_EXIT_EDGE_MARGIN,
) -> bool:
    if margin <= 0:
        return False
    return float(bbox[3]) >= max(0.0, float(frame_height) - margin)


def _reset_exit_sequence_state(state: Dict[str, Any]) -> None:
    state["exit_sequence_active"] = False
    state["exit_sequence_frames"] = 0
    state["exit_peak_height"] = 0.0
    state["exit_bottom_edge_frames"] = 0
    state["exit_head_only_frames"] = 0
    state["exit_head_only_seen"] = False
    state["exit_candidate_logged"] = False


def _update_exit_sequence_state(
    state: Dict[str, Any],
    bbox: Tuple[float, float, float, float],
    frame_height: int,
    in_bottom_exit_zone: bool,
    moving_toward_bottom: bool,
    moving_away_from_bottom: bool,
) -> None:
    """Track a strict exit sequence: gate approach -> bottom-edge crop -> disappear."""
    if not _state_cleared_exit_zone(state):
        _reset_exit_sequence_state(state)
        return

    if moving_away_from_bottom or not in_bottom_exit_zone:
        _reset_exit_sequence_state(state)
        return

    if not moving_toward_bottom:
        return

    bbox_height = _bbox_height(bbox)
    near_bottom_edge = _bbox_near_bottom_edge(bbox, frame_height)
    if not state.get("exit_sequence_active"):
        _reset_exit_sequence_state(state)
        state["exit_sequence_active"] = True

    state["exit_sequence_frames"] = int(state.get("exit_sequence_frames", 0)) + 1
    state["exit_peak_height"] = max(float(state.get("exit_peak_height", 0.0)), bbox_height)

    if near_bottom_edge:
        state["exit_bottom_edge_frames"] = int(state.get("exit_bottom_edge_frames", 0)) + 1
    else:
        state["exit_bottom_edge_frames"] = 0

    peak_height = max(float(state.get("exit_peak_height", 0.0)), 1.0)
    shrink_ratio = bbox_height / peak_height
    if near_bottom_edge and shrink_ratio <= TRACK_EXIT_HEAD_RATIO:
        state["exit_head_only_frames"] = int(state.get("exit_head_only_frames", 0)) + 1
        if int(state.get("exit_head_only_frames", 0)) >= TRACK_EXIT_HEAD_CONFIRM_FRAMES:
            state["exit_head_only_seen"] = True
    elif not state.get("exit_head_only_seen"):
        state["exit_head_only_frames"] = 0


def _state_has_exit_gate_evidence(state: Dict[str, Any]) -> bool:
    return (
        bool(state.get("exit_sequence_active"))
        and _state_cleared_exit_zone(state)
        and int(state.get("exit_sequence_frames", 0)) >= TRACK_EXIT_GATE_APPROACH_FRAMES
        and int(state.get("exit_bottom_edge_frames", 0)) >= TRACK_EXIT_BOTTOM_CONFIRM_FRAMES
    )


def _state_outside_roi_long_enough(state: Dict[str, Any]) -> bool:
    return (
        not bool(state.get("last_in_roi", True))
        and int(state.get("outside_frames", 0)) >= TRACK_EXIT_CONFIRM_FRAMES
    )


def _state_ready_for_exit_commit(
    state: Dict[str, Any],
    *,
    final_phase: bool = False,
    frame_height: Optional[int] = None,
) -> bool:
    if not _state_has_exit_gate_evidence(state):
        return False

    if bool(state.get("exit_head_only_seen")):
        return True

    if _state_outside_roi_long_enough(state):
        return True

    if not final_phase:
        return False

    if int(state.get("missing_frames", 0)) >= TRACK_EXIT_CONFIRM_FRAMES:
        return True

    last_bbox = state.get("last_bbox")
    return bool(
        frame_height is not None
        and last_bbox
        and _bbox_near_bottom_edge(last_bbox, frame_height)
    )


def _identity_ready(identity: Dict[str, Any]) -> bool:
    status = str(identity.get("identity_status") or "").upper()
    if IDENTITY_MODE == "reid":
        if status != "CONFIRMED":
            return False

        # ReID can oscillate briefly when a new track is still stabilizing.
        # Delay counting "new_visitor" until it has a few extra embedding samples
        # so relay jitter/occlusion is less likely to inflate unique counts.
        source = str(identity.get("reid_source") or "").strip().lower()
        samples = int(identity.get("embedding_samples") or 0)
        min_track_samples = int(getattr(reid_module, "REID_MIN_TRACK_FRAMES", 3) or 3)
        min_new_visitor_samples = max(min_track_samples + 2, 6)

        if source == "new_visitor" and samples < min_new_visitor_samples:
            return False
        return True

    if IDENTITY_MODE == "track":
        return status in {"CONFIRMED", "FALLBACK"}

    return status in {"CONFIRMED", "FALLBACK"}


def _classification_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "person_type": state.get("person_type", "CUSTOMER"),
        "employee_id": state.get("employee_id"),
        "employee_code": state.get("employee_code"),
        "employee_name": state.get("employee_name"),
        "match_score": state.get("match_score"),
        "recognition_source": state.get("recognition_source"),
    }


def _state_can_exit(state: Dict[str, Any]) -> bool:
    person_type = state.get("person_type", "CUSTOMER")
    has_logged_entry = bool(state.get("entry_logged"))
    observed_long_enough = (
        max(
            int(state.get("seen_frames", 0)),
            int(state.get("track_hits", 0)),
            int(state.get("observed_frames", 0)),
        )
        >= TRACK_EXIT_WITHOUT_ENTRY_MIN_FRAMES
    )
    return (
        person_type not in {"UNKNOWN", "EMPLOYEE"}
        and bool(state.get("visitor_key"))
        and (
            has_logged_entry
            or (TRACK_EXIT_ALLOW_WITHOUT_ENTRY and observed_long_enough)
        )
    )


def _finalize_open_exit_states(
    visitor_states: Dict[int, Dict[str, Any]],
    visitor_flow_states: Dict[str, Dict[str, Any]],
    last_event_time: Dict[str, float],
    roi: Optional[List[List[float]]],
    frame_width: int,
    frame_height: int,
    area_id: Optional[int],
    area_direction_mode: str,
    token: Optional[str],
    now_ts: float,
) -> int:
    """Flush likely OUT events before a local video source restarts."""
    if area_direction_mode not in {"BOTH", "OUT"}:
        return 0

    now_time = datetime.now()
    counted = 0
    for track_id, state in list(visitor_states.items()):
        visitor_key = state.get("visitor_key", "")
        last_bbox = state.get("last_bbox")
        if (
            not visitor_key
            or not last_bbox
            or state.get("exit_logged")
            or not _state_can_exit(state)
            or not _state_ready_for_exit_commit(
                state,
                final_phase=True,
                frame_height=frame_height,
            )
        ):
            continue

        if not (
            _bbox_near_bottom_edge(last_bbox, frame_height)
            or not bool(state.get("last_in_roi", True))
        ):
            continue

        debounce_key = f"{visitor_key}_OUT"
        if now_ts - last_event_time.get(debounce_key, 0.0) < EVENT_COOLDOWN:
            continue

        classification = _classification_from_state(state)
        result = _send_track_event(
            "OUT",
            track_id,
            visitor_key,
            area_id,
            now_time,
            0.0,
            classification,
            token,
        )
        if not result["success"]:
            log.error(
                "Failed to send final OUT event: %s",
                result.get("error", "Unknown"),
            )
            continue

        last_event_time[debounce_key] = now_ts
        state["entry_logged"] = False
        state["pending_entry"] = False
        state["direction"] = "OUT"
        state["exit_logged"] = True
        flow = visitor_flow_states.setdefault(visitor_key, {})
        flow["inside"] = False
        flow["last_out_ts"] = now_ts
        flow["suppress_in_until"] = now_ts + TRACK_REENTRY_COOLDOWN_SECONDS
        counted += 1
        log.info(
            "Finalized OUT at source end track=%s visitor=%s observed=%s",
            track_id,
            visitor_key[:8],
            state.get("observed_frames", state.get("seen_frames", 0)),
        )

    return counted


def _scale_roi(
    roi: List[List[float]],
    frame_width: int,
    frame_height: int,
) -> List[List[float]]:
    if not roi:
        return roi

    ref_w, ref_h = REFERENCE_FRAME_SIZE
    max_x = max(float(point[0]) for point in roi)
    max_y = max(float(point[1]) for point in roi)

    if frame_width == ref_w and frame_height == ref_h:
        return roi
    if max_x > ref_w or max_y > ref_h:
        return roi

    scale_x = frame_width / float(ref_w)
    scale_y = frame_height / float(ref_h)
    return [
        [round(float(x) * scale_x, 2), round(float(y) * scale_y, 2)]
        for x, y in roi
    ]


def _default_roi(frame_width: int, frame_height: int) -> List[List[float]]:
    roi = parse_roi(TEST_ROI_JSON) if TEST_ROI_JSON else None
    if roi:
        return _scale_roi(roi, frame_width, frame_height)
    base_roi = [
        [50.0, 50.0],
        [float(max(REFERENCE_FRAME_SIZE[0] - 50, 1)), 50.0],
        [float(max(REFERENCE_FRAME_SIZE[0] - 50, 1)), float(max(REFERENCE_FRAME_SIZE[1] - 50, 1))],
        [50.0, float(max(REFERENCE_FRAME_SIZE[1] - 50, 1))],
    ]
    return _scale_roi(base_roi, frame_width, frame_height)


def _is_local_file_source(stream_url: str) -> bool:
    raw = (stream_url or "").strip()
    if not raw or raw.isdigit() or "://" in raw:
        return False
    return Path(raw).expanduser().exists()


def _output_fps(source_fps: float) -> float:
    if TEST_OUTPUT_FPS > 0:
        return TEST_OUTPUT_FPS
    if source_fps > 0:
        return max(source_fps / max(TEST_FRAME_STEP, 1), 1.0)
    if EDGE_PROCESSING_MAX_FPS > 0:
        return EDGE_PROCESSING_MAX_FPS
    if EDGE_STREAM_MAX_FPS > 0:
        return EDGE_STREAM_MAX_FPS
    return 30.0


def _recording_fps() -> float:
    if EDGE_RECORDING_FPS > 0:
        return EDGE_RECORDING_FPS
    if EDGE_PROCESSING_MAX_FPS > 0:
        return EDGE_PROCESSING_MAX_FPS
    if EDGE_STREAM_MAX_FPS > 0:
        return EDGE_STREAM_MAX_FPS
    return 12.0


def _build_backup_recorder() -> SegmentedVideoRecorder:
    recorder = SegmentedVideoRecorder(
        output_dir=EDGE_RECORDING_OUTPUT_DIR,
        camera_id=CAMERA_ID,
        segment_seconds=float(EDGE_RECORDING_SEGMENT_SECONDS),
        fps=_recording_fps(),
        enabled=EDGE_RECORDING_ENABLED,
        max_gap_seconds=EDGE_RECORDING_MAX_GAP_SECONDS,
        file_prefix=EDGE_RECORDING_FILE_PREFIX,
    )

    if recorder.enabled:
        log.info(
            "CCTV recording active: mode=%s, every %d minute(s) -> %s",
            EDGE_RECORDING_SAVE_MODE,
            EDGE_RECORDING_SEGMENT_MINUTES,
            EDGE_RECORDING_OUTPUT_DIR,
        )
    else:
        log.info("CCTV recording disabled")

    return recorder


def _resolve_identity_embedding(face_recognizer: EmployeeFaceRecognizer, track) -> Optional[np.ndarray]:
    mode = IDENTITY_MODE
    if mode == "face":
        return face_recognizer.extract_track_face_embedding(track.bbox)
    if mode == "reid":
        return getattr(track, "embedding", None)
    return None


def _build_output_writer(stream_url: str, frame: np.ndarray, source_fps: float):
    output_dir = Path(TEST_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_name = TEST_OUTPUT_NAME.strip()
    if not output_name:
        source_name = Path(stream_url).stem if stream_url else "video_test"
        output_name = f"{source_name}_tracking"

    output_path = output_dir / f"{output_name}.mp4"
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        _output_fps(source_fps),
        (frame.shape[1], frame.shape[0]),
    )

    if not writer.isOpened():
        log.warning("Failed to open output writer for %s", output_path)
        return None, None

    log.info("Writing processed test video to %s", output_path)
    return writer, output_path


def _build_tracker():
    tracker_method = str(TRACKER_METHOD or "auto").strip().lower()

    if tracker_method == "bytetrack":
        return (
            ByteTrackTracker(
                max_age=TRACK_MAX_DISAPPEARED,
                n_init=TRACK_CONFIRM_FRAMES,
                high_thresh=BYTETRACK_HIGH_THRESH,
                low_thresh=BYTETRACK_LOW_THRESH,
                match_thresh=BYTETRACK_MATCH_THRESH,
                new_track_thresh=BYTETRACK_NEW_TRACK_THRESH,
                min_box_area=BYTETRACK_MIN_BOX_AREA,
            ),
            "ByteTrack",
        )

    if tracker_method == "centroid" or (tracker_method == "auto" and FORCE_CENTROID):
        return (
            CentroidTracker(
                max_disappeared=TRACK_MAX_DISAPPEARED,
                max_distance=TRACK_MAX_DISTANCE,
            ),
            "CentroidTracker",
        )

    if tracker_method in {"auto", "deepsort"} and DEEPSORT_AVAILABLE:
        tracker = DeepSORTTracker(
            max_age=TRACK_MAX_DISAPPEARED,
            n_init=TRACK_CONFIRM_FRAMES,
            max_cosine_distance=TRACK_MAX_COSINE_DISTANCE,
        )
        tracker_mode = "DeepSORT+ReID"
        if getattr(tracker, "using_fallback", False):
            tracker_mode = "CentroidTracker"
        return tracker, tracker_mode

    if tracker_method == "deepsort" and not DEEPSORT_AVAILABLE:
        log.warning("TRACKER_METHOD=deepsort requested but DeepSORT is unavailable; using CentroidTracker")

    return (
        CentroidTracker(
            max_disappeared=TRACK_MAX_DISAPPEARED,
            max_distance=TRACK_MAX_DISTANCE,
        ),
        "CentroidTracker",
    )


def real_loop():
    """YOLO + tracking + optional offline video test profile."""
    requested_video_test = TEST_MODE == "video"
    test_input_exists = bool(TEST_INPUT) and Path(TEST_INPUT).exists()
    is_video_test = requested_video_test and test_input_exists
    base_events_enabled = not is_video_test
    events_enabled = base_events_enabled
    local_file_events_consumed = False
    needs_backend_auth = True

    token = login_token() if needs_backend_auth else None
    startup_runtime_config = get_runtime_config(token)
    _apply_runtime_config(startup_runtime_config, None)
    model = load_model()
    face_recognizer = EmployeeFaceRecognizer()
    _apply_runtime_config(startup_runtime_config, model)
    _apply_yolo_thresholds(model, _effective_detector_conf(), detection_module.IOU_TH)

    # log.info("Running in REAL mode (%s + employee filtering)", tracker_mode)
    log.info(
        "Runtime tuning: processing_target=%s fps | stream_target=%s fps | face_interval=%s frame(s)",
        EDGE_PROCESSING_MAX_FPS or "unlimited",
        EDGE_STREAM_MAX_FPS or "worker-rate",
        FACE_DETECTION_FRAME_INTERVAL,
    )
    if requested_video_test and not test_input_exists:
        log.warning("TEST_MODE=video requested but TEST_INPUT was not found: %s", TEST_INPUT or "(empty)")
    if is_video_test:
        log.info(
            "Video test profile active: input=%s | size=%sx%s | frame_step=%s | max_frames=%s | max_seconds=%s",
            TEST_INPUT,
            TEST_FRAME_WIDTH,
            TEST_FRAME_HEIGHT,
            TEST_FRAME_STEP,
            TEST_MAX_FRAMES or "all",
            TEST_MAX_SECONDS or "all",
        )

    tracker, tracker_mode = _build_tracker()
    if IDENTITY_MODE == "reid" and tracker_mode != "DeepSORT+ReID":
        log.warning(
            "IDENTITY_MODE=reid berjalan di %s. "
            "Embedding ReID tidak tersedia, visitor_key fallback ke track-id, "
            "dan hitungan unik bisa membengkak saat stream relay tidak stabil."
            " Gunakan IDENTITY_MODE=track untuk ByteTrack/Centroid atau pilih DeepSORT+ReID.",
            tracker_mode,
        )

    last_cfg_fetch = 0.0
    roi = None
    roi_shape: Tuple[int, int] = (0, 0)
    stream_url = TEST_INPUT if is_video_test else (EDGE_STREAM_URL or "")
    area_id = None
    area_direction_mode = "BOTH"
    visitor_states: Dict[int, Dict[str, Any]] = {}
    visitor_flow_states: Dict[str, Dict[str, Any]] = {}
    current_date = ""
    last_event_time: Dict[str, float] = {}
    cap = None
    cap_source = ""
    cap_started_ts = 0.0
    last_good_frame_ts = 0.0
    last_frame_id = 0
    processed_frames = 0
    frame_w = TEST_FRAME_WIDTH
    frame_h = TEST_FRAME_HEIGHT
    output_writer = None
    output_video_path = None
    backup_recorder = _build_backup_recorder()

    # Processing cadence is independent from stream cadence; the stream layer can
    # duplicate the latest annotated frame between inference updates.
    target_frame_time = 1.0 / EDGE_PROCESSING_MAX_FPS if EDGE_PROCESSING_MAX_FPS > 0 else 0.0

    try:
        while True:
            frame_start = time.time()
            now_ts = frame_start
            today = datetime.now().strftime("%Y-%m-%d")

            if today != current_date:
                visitor_states = {}
                visitor_flow_states = {}
                last_event_time = {}
                current_date = today
                reset_daily_cache(today)
                face_recognizer.reset_daily()
                for _, track in tracker.tracks.items():
                    track.in_roi = False
                log.info("New day: %s — reset visitor tracking + face cache", today)

            if now_ts - last_cfg_fetch > CONFIG_REFRESH or last_cfg_fetch == 0:
                if needs_backend_auth and token is None:
                    token = login_token()

                runtime_apply = _apply_runtime_config(get_runtime_config(token), model)
                if runtime_apply.get("tracker_rebuild"):
                    tracker, tracker_mode = _build_tracker()
                    visitor_states = {}
                    log.info("Tracker rebuilt after runtime config update (%s)", tracker_mode)
                if runtime_apply.get("recording_rebuild"):
                    backup_recorder.close()
                    backup_recorder = _build_backup_recorder()
                target_frame_time = 1.0 / EDGE_PROCESSING_MAX_FPS if EDGE_PROCESSING_MAX_FPS > 0 else 0.0

                if not is_video_test:
                    cfg = get_camera_config(token)
                    runtime_stream_url = (runtime_apply.get("stream_url") or "").strip()
                    if runtime_stream_url:
                        stream_url = runtime_stream_url
                    elif cfg and not EDGE_STREAM_URL:
                        stream_url = (cfg.get("stream_url") or "").strip() or stream_url

                    areas = get_counting_areas(token)
                    if areas:
                        active_area = next((area for area in areas if area.get("is_active")), None)
                        if active_area:
                            roi = parse_roi(active_area.get("roi_polygon"))
                            area_id = active_area.get("area_id")
                            area_direction_mode = (active_area.get("direction_mode") or "BOTH").upper()

                face_recognizer.refresh_registry(
                    get_employee_registry,
                    token,
                    force=last_cfg_fetch == 0,
                )

                last_cfg_fetch = now_ts
                if roi:
                    log.debug("ROI loaded: %s", roi)
                if stream_url:
                    log.debug("Stream URL: %s", stream_url)

            if not stream_url:
                source_hint = "TEST_INPUT" if is_video_test else "EDGE_STREAM_URL"
                log.warning("Stream URL not set. Configure via UI or env %s", source_hint)
                time.sleep(5)
                continue

            if cap_source != stream_url and cap is not None:
                log.info("Stream source changed → reconnecting to %s", stream_url)
                cap.release()
                cap = None
                cap_source = ""
                cap_started_ts = 0.0
                last_good_frame_ts = 0.0
                last_frame_id = 0
                events_enabled = base_events_enabled
                local_file_events_consumed = False
                backup_recorder.reset(reason="stream source changed")

            if cap is None or not cap.isOpened():
                cap = LatestFrameCapture(stream_url)
                if not cap.start():
                    log.warning("Failed to open stream. Retrying...")
                    cap = None
                    cap_source = ""
                    time.sleep(3)
                    continue
                cap_source = stream_url
                cap_started_ts = now_ts
                last_good_frame_ts = 0.0
                last_frame_id = 0

            ok, frame, last_frame_id = cap.read(last_frame_id=last_frame_id, timeout=1.0)
            if not ok or frame is None:
                if cap is not None and getattr(cap, "file_ended", False):
                    if is_video_test:
                        log.info("Video test input finished.")
                        break
                    if _is_local_file_source(stream_url) and events_enabled:
                        finalized = _finalize_open_exit_states(
                            visitor_states,
                            visitor_flow_states,
                            last_event_time,
                            roi,
                            frame_w,
                            frame_h,
                            area_id,
                            area_direction_mode,
                            token,
                            now_ts,
                        )
                        if finalized:
                            log.info("Finalized %d OUT event(s) before local replay", finalized)

                        if EDGE_LOCAL_FILE_REPLAY_POST_EVENTS:
                            visitor_states = {}
                            visitor_flow_states = {}
                            last_event_time = {}
                            face_recognizer.reset_daily()
                            tracker, tracker_mode = _build_tracker()
                            local_file_events_consumed = False
                            log.info(
                                "Local video source finished once; restarting with event posting enabled"
                            )
                        else:
                            events_enabled = False
                            local_file_events_consumed = True
                            log.info(
                                "Local video source finished once; restarting preview without event posting"
                            )
                    log.info("Video file ended. Restarting from beginning...")
                    cap.release()
                    cap = None
                    cap_source = ""
                    cap_started_ts = 0.0
                    last_good_frame_ts = 0.0
                    last_frame_id = 0
                    time.sleep(1)
                    continue

                stream_stall_grace = max(3.0, float(EDGE_RECORDING_MAX_GAP_SECONDS) + 2.0)
                last_stream_activity_ts = last_good_frame_ts or cap_started_ts or now_ts
                stream_stall_age = now_ts - last_stream_activity_ts
                if (
                    cap is not None
                    and not _is_local_file_source(stream_url)
                    and stream_stall_age < stream_stall_grace
                ):
                    time.sleep(0.05)
                    continue

                log.warning("Frame read failed. Reconnecting...")
                if cap is not None:
                    cap.release()
                cap = None
                cap_source = ""
                cap_started_ts = 0.0
                last_good_frame_ts = 0.0
                last_frame_id = 0
                time.sleep(1)
                continue

            last_good_frame_ts = now_ts

            if is_video_test and TEST_FRAME_STEP > 1 and (last_frame_id % TEST_FRAME_STEP) != 0:
                continue

            if not TEST_KEEP_SOURCE_SIZE and (
                frame.shape[1] != TEST_FRAME_WIDTH or frame.shape[0] != TEST_FRAME_HEIGHT
            ):
                frame = cv2.resize(frame, (TEST_FRAME_WIDTH, TEST_FRAME_HEIGHT))

            frame_h, frame_w = frame.shape[:2]
            if roi is None or (is_video_test and roi_shape != (frame_w, frame_h)):
                roi = _default_roi(frame_w, frame_h) if is_video_test else (roi or _default_roi(frame_w, frame_h))
                roi_shape = (frame_w, frame_h)

            if is_video_test and output_writer is None:
                output_writer, output_video_path = _build_output_writer(
                    stream_url,
                    frame,
                    float(getattr(cap, "source_fps", 0.0)),
                )

            # Keep a clean frame before drawing overlay when a raw stream or raw recording needs it.
            raw_frame = (
                frame.copy()
                if has_raw_stream_clients() or EDGE_RECORDING_SAVE_MODE == "raw"
                else None
            )
            display_frame = frame

            results = model(frame, size=IMG_SIZE)
            raw_detections = (
                results.xyxy[0].detach().cpu().numpy()
                if hasattr(results, "xyxy")
                else np.zeros((0, 6), dtype=np.float32)
            )

            detections: List[Tuple[float, float, float, float, float]] = []
            for x1, y1, x2, y2, conf, _ in raw_detections:
                detections.append((float(x1), float(y1), float(x2), float(y2), float(conf)))
            detections = suppress_duplicate_person_detections(detections)

            if isinstance(tracker, DeepSORTTracker):
                tracks = tracker.update(frame, detections)
                tracker_mode_runtime = (
                    "CentroidTracker" if getattr(tracker, "using_fallback", False) else "DeepSORT+ReID"
                )
            elif isinstance(tracker, ByteTrackTracker):
                tracks = tracker.update(detections)
                tracker_mode_runtime = "ByteTrack"
            else:
                boxes = [(det[0], det[1], det[2], det[3]) for det in detections]
                tracks = tracker.update(boxes)
                tracker_mode_runtime = "CentroidTracker"

            active_track_ids = list(tracks.keys())
            cleanup_old_tracks(active_track_ids)
            face_recognizer.cleanup(active_track_ids)

            # Face recognition is the second-heaviest stage after YOLO, so only refresh
            # the batch detector while it is useful for employee classification or face identity mode.
            should_detect_faces = face_recognizer.needs_detection(active_track_ids)
            if (
                IDENTITY_MODE == "face"
                and face_recognizer.enabled
                and face_recognizer.available
                and active_track_ids
            ):
                should_detect_faces = True

            if should_detect_faces:
                face_recognizer.detect_faces_batch(frame, frame_id=last_frame_id)

            now_time = datetime.now()
            avg_confidence = float(np.mean([det[4] for det in detections])) if detections else 0.0
            customer_tracks = 0
            employee_tracks = 0
            verifying_tracks = 0

            for flow in visitor_flow_states.values():
                if (
                    flow.get("inside")
                    and now_ts - float(flow.get("last_seen_ts", now_ts)) > TRACK_REENTRY_COOLDOWN_SECONDS
                ):
                    flow["inside"] = False
                    flow["expired_without_exit"] = True

            def has_nearby_inside_track(track_id: int, state: Dict[str, Any]) -> bool:
                if IDENTITY_MODE != "track":
                    return False
                current_bbox = state.get("last_bbox")
                if not current_bbox:
                    return False

                for other_track_id, other_state in visitor_states.items():
                    if other_track_id == track_id:
                        continue
                    if not other_state.get("entry_logged") or other_state.get("exit_logged"):
                        continue
                    if not other_state.get("visitor_key"):
                        continue
                    if now_ts - float(other_state.get("last_seen_ts", now_ts) or now_ts) > TRACK_REENTRY_COOLDOWN_SECONDS:
                        continue
                    other_bbox = other_state.get("last_bbox")
                    if other_bbox and _same_spatial_region(tuple(current_bbox), tuple(other_bbox)):
                        return True
                return False

            def commit_count_event(
                direction: str,
                track_id: int,
                visitor_key: str,
                state: Dict[str, Any],
                classification: Dict[str, Any],
                reason: str = "",
            ) -> bool:
                flow = visitor_flow_states.setdefault(
                    visitor_key,
                    {
                        "inside": False,
                        "last_in_ts": 0.0,
                        "last_out_ts": 0.0,
                        "last_seen_ts": now_ts,
                    },
                )

                if direction == "OUT":
                    if state.get("entry_suppressed"):
                        _reset_exit_sequence_state(state)
                        state["pending_entry"] = False
                        state["entry_logged"] = False
                        state["exit_logged"] = True
                        state["direction"] = "OUT"
                        flow["inside"] = False
                        flow["last_out_ts"] = now_ts
                        flow["suppress_in_until"] = now_ts + TRACK_REENTRY_COOLDOWN_SECONDS
                        return True

                    if state.get("exit_logged"):
                        state["pending_entry"] = False
                        state["entry_logged"] = False
                        state["direction"] = "OUT"
                        return True

                    last_track_out_ts = float(state.get("last_track_out_ts", 0.0) or 0.0)
                    if (
                        TRACK_SAME_TRACK_OUT_COOLDOWN_SECONDS > 0
                        and now_ts - last_track_out_ts
                        < TRACK_SAME_TRACK_OUT_COOLDOWN_SECONDS
                    ):
                        state["pending_entry"] = False
                        state["entry_logged"] = False
                        state["direction"] = "OUT"
                        return True

                    if not _state_ready_for_exit_commit(state):
                        state["pending_entry"] = False
                        state["direction"] = "EXITING" if state.get("exit_sequence_active") else (
                            "IN_ROI" if state.get("entry_logged") else "TRACKING"
                        )
                        log.debug(
                            "Skip OUT before strict exit sequence completes track=%s visitor=%s",
                            track_id,
                            visitor_key[:8],
                        )
                        return True

                if (
                    direction == "IN"
                    and now_ts < float(flow.get("suppress_in_until", 0.0) or 0.0)
                ):
                    _reset_exit_sequence_state(state)
                    state["pending_entry"] = False
                    state["entry_logged"] = False
                    state["is_new"] = False
                    state["direction"] = "OUT"
                    return True

                if classification.get("person_type") == "EMPLOYEE":
                    _reset_exit_sequence_state(state)
                    state["pending_entry"] = False
                    state["entry_logged"] = False
                    state["is_new"] = False
                    state["direction"] = "IGNORE"
                    flow["inside"] = False
                    return True

                if area_direction_mode not in {"BOTH", direction}:
                    if direction == "IN":
                        _reset_exit_sequence_state(state)
                        state["pending_entry"] = False
                        state["entry_logged"] = True
                        state["is_new"] = False
                        state["direction"] = "IN_ROI"
                        flow["inside"] = True
                        flow["last_in_ts"] = now_ts
                    else:
                        _reset_exit_sequence_state(state)
                        state["entry_logged"] = False
                        state["exit_logged"] = True
                        state["direction"] = "OUT"
                        flow["inside"] = False
                        flow["last_out_ts"] = now_ts
                    return True

                if direction == "IN" and has_nearby_inside_track(track_id, state):
                    _reset_exit_sequence_state(state)
                    state["pending_entry"] = False
                    state["entry_logged"] = True
                    state["exit_logged"] = False
                    state["entry_suppressed"] = True
                    state["is_new"] = False
                    state["direction"] = "IN_ROI"
                    flow["inside"] = True
                    flow["last_in_ts"] = now_ts
                    flow["last_seen_ts"] = now_ts
                    flow["active_track_id"] = track_id
                    log.debug(
                        "Suppress duplicate centroid IN track=%s visitor=%s near existing inside track",
                        track_id,
                        visitor_key[:8],
                    )
                    return True

                debounce_key = f"{visitor_key}_{direction}"
                if now_ts - last_event_time.get(debounce_key, 0.0) < EVENT_COOLDOWN:
                    if direction == "IN":
                        _reset_exit_sequence_state(state)
                        state["pending_entry"] = False
                        state["entry_logged"] = True
                        state["is_new"] = False
                        state["direction"] = "IN_ROI"
                        flow["inside"] = True
                    else:
                        _reset_exit_sequence_state(state)
                        state["entry_logged"] = False
                        state["exit_logged"] = True
                        state["direction"] = "OUT"
                        flow["inside"] = False
                    return True

                if events_enabled:
                    result = _send_track_event(
                        direction,
                        track_id,
                        visitor_key,
                        area_id,
                        now_time,
                        avg_confidence,
                        classification,
                        token,
                    )
                    if not result["success"]:
                        log.error(
                            "Failed to send %s event: %s",
                            direction,
                            result.get("error", "Unknown"),
                        )
                        return False
                    is_new_unique = result["data"].get("is_new_unique", False)
                else:
                    is_new_unique = False

                last_event_time[debounce_key] = now_ts
                state["pending_entry"] = False
                if direction == "IN":
                    _reset_exit_sequence_state(state)
                    state["entry_logged"] = True
                    state["exit_logged"] = False
                    state["entry_suppressed"] = False
                    state["is_new"] = bool(is_new_unique)
                    state["direction"] = "IN"
                    flow["inside"] = True
                    flow["last_in_ts"] = now_ts
                else:
                    _reset_exit_sequence_state(state)
                    state["entry_logged"] = False
                    state["direction"] = "OUT"
                    state["exit_logged"] = True
                    state["last_track_out_ts"] = now_ts
                    flow["inside"] = False
                    flow["last_out_ts"] = now_ts
                    flow["suppress_in_until"] = now_ts + TRACK_REENTRY_COOLDOWN_SECONDS
                    state["suppress_entry_until"] = flow["suppress_in_until"]
                flow["last_seen_ts"] = now_ts
                flow["active_track_id"] = track_id
                log.info(
                    "Counted %s event track=%s visitor=%s source=%s reason=%s",
                    direction,
                    track_id,
                    visitor_key[:8],
                    classification.get("recognition_source"),
                    reason or "roi",
                )
                return True

            for track_id, track in tracks.items():
                state = visitor_states.setdefault(
                    track_id,
                    {
                        "is_new": False,
                        "direction": "TRACKING",
                        "visitor_key": "",
                        "person_type": "UNKNOWN",
                        "identity_status": "PENDING",
                        "pending_entry": False,
                        "entry_logged": False,
                        "entry_suppressed": False,
                        "inside_frames": 0,
                        "outside_frames": 0,
                        "exit_zone_frames": 0,
                        "exit_motion_frames": 0,
                        "cleared_exit_zone": False,
                        "exit_sequence_active": False,
                        "exit_sequence_frames": 0,
                        "exit_peak_height": 0.0,
                        "exit_bottom_edge_frames": 0,
                        "exit_head_only_frames": 0,
                        "exit_head_only_seen": False,
                        "seen_frames": 0,
                        "missing_frames": 0,
                    },
                )
                detected_now = int(getattr(track, "disappeared", 0) or 0) == 0

                if detected_now:
                    point_x, point_y = _track_counting_point(track)
                    in_roi_now = point_in_roi(roi, point_x, point_y)
                    identity_embedding = _resolve_identity_embedding(face_recognizer, track)
                    identity = update_track_identity(track_id, identity_embedding, CAMERA_ID, today)
                    classification = face_recognizer.classify_track(frame, track_id, track.bbox)
                    visitor_key = _stable_identity_key(identity["visitor_key"], classification)
                    previous_bbox = state.get("last_bbox")
                    previous_centroid = state.get("last_centroid")
                    previous_bottom = float(previous_bbox[3]) if previous_bbox else None
                    bottom_delta = (
                        float(track.bbox[3]) - previous_bottom
                        if previous_bottom is not None
                        else 0.0
                    )
                    centroid_delta = (
                        float(track.centroid[1]) - float(previous_centroid[1])
                        if previous_centroid is not None
                        else 0.0
                    )
                    moving_toward_bottom = (
                        bottom_delta >= TRACK_EXIT_MIN_DELTA_Y
                        or centroid_delta >= TRACK_EXIT_MIN_DELTA_Y
                    )
                    moving_away_from_bottom = (
                        bottom_delta <= -TRACK_EXIT_MIN_DELTA_Y
                        or centroid_delta <= -TRACK_EXIT_MIN_DELTA_Y
                    )
                    in_bottom_exit_zone = _bbox_in_bottom_exit_zone(track.bbox, roi, frame_h)

                    previous_key = state.get("visitor_key")
                    if previous_key and previous_key != visitor_key and previous_key in visitor_flow_states:
                        old_flow = visitor_flow_states[previous_key]
                        if old_flow.get("inside"):
                            visitor_flow_states.setdefault(visitor_key, {}).update(old_flow)

                    state.update(
                        {
                            "visitor_key": visitor_key,
                            "person_type": classification.get("person_type", "UNKNOWN"),
                            "employee_id": classification.get("employee_id"),
                            "employee_code": classification.get("employee_code"),
                            "employee_name": classification.get("employee_name"),
                            "match_score": classification.get("match_score"),
                            "recognition_source": classification.get("recognition_source"),
                            "identity_status": identity.get("identity_status", "PENDING"),
                            "identity_samples": identity.get("embedding_samples", 0),
                            "previous_centroid": previous_centroid,
                            "last_bbox": tuple(track.bbox),
                            "last_centroid": tuple(track.centroid),
                            "last_seen_ts": now_ts,
                            "last_in_roi": in_roi_now,
                            "missing_frames": 0,
                        }
                    )
                    state["seen_frames"] = int(state.get("seen_frames", 0)) + 1
                    track_hits = int(getattr(track, "hits", 0) or 0)
                    state["track_hits"] = track_hits
                    state["observed_frames"] = max(
                        int(state.get("seen_frames", 0)),
                        track_hits,
                    )

                    if in_roi_now:
                        state["inside_frames"] = int(state.get("inside_frames", 0)) + 1
                        state["outside_frames"] = 0
                    else:
                        state["outside_frames"] = int(state.get("outside_frames", 0)) + 1
                        state["inside_frames"] = 0

                    if in_bottom_exit_zone:
                        state["exit_zone_frames"] = int(state.get("exit_zone_frames", 0)) + 1
                    else:
                        state["exit_zone_frames"] = 0
                        state["cleared_exit_zone"] = True

                    if moving_toward_bottom:
                        state["exit_motion_frames"] = int(state.get("exit_motion_frames", 0)) + 1
                    else:
                        state["exit_motion_frames"] = max(
                            0,
                            int(state.get("exit_motion_frames", 0)) - 1,
                        )

                    _update_exit_sequence_state(
                        state,
                        tuple(track.bbox),
                        frame_h,
                        in_bottom_exit_zone,
                        moving_toward_bottom,
                        moving_away_from_bottom,
                    )

                    if classification["person_type"] == "EMPLOYEE":
                        employee_tracks += 1
                    elif classification["person_type"] == "UNKNOWN":
                        verifying_tracks += 1
                    else:
                        customer_tracks += 1

                    if visitor_key:
                        flow = visitor_flow_states.setdefault(
                            visitor_key,
                            {
                                "inside": False,
                                "last_in_ts": 0.0,
                                "last_out_ts": 0.0,
                            },
                        )
                        flow["last_seen_ts"] = now_ts
                        flow["active_track_id"] = track_id
                    else:
                        flow = {"inside": False}

                    ready_to_count = (
                        classification.get("person_type") != "UNKNOWN"
                        and _identity_ready(identity)
                        and bool(visitor_key)
                    )
                    ready_to_exit = (
                        classification.get("person_type") != "UNKNOWN"
                        and bool(visitor_key)
                        and (
                            bool(state.get("entry_logged"))
                            or (
                                TRACK_EXIT_ALLOW_WITHOUT_ENTRY
                                and int(state.get("observed_frames", 0))
                                >= TRACK_EXIT_WITHOUT_ENTRY_MIN_FRAMES
                            )
                        )
                    )
                    exit_sequence_ready = ready_to_exit and _state_ready_for_exit_commit(state)
                    if state.get("exit_sequence_active") and not state.get("exit_candidate_logged"):
                        log.debug(
                            (
                                "Exit sequence track=%s visitor=%s ready=%s seen=%s "
                                "hits=%s observed=%s entry=%s motion=%s zone=%s "
                                "head=%s head_frames=%s peak=%.1f bottom_delta=%.1f centroid_delta=%.1f"
                            ),
                            track_id,
                            visitor_key[:8],
                            exit_sequence_ready,
                            state.get("seen_frames", 0),
                            state.get("track_hits", 0),
                            state.get("observed_frames", 0),
                            state.get("entry_logged"),
                            state.get("exit_motion_frames", 0),
                            state.get("exit_zone_frames", 0),
                            state.get("exit_head_only_seen"),
                            state.get("exit_head_only_frames", 0),
                            float(state.get("exit_peak_height", 0.0)),
                            bottom_delta,
                            centroid_delta,
                        )
                        state["exit_candidate_logged"] = True

                    if classification.get("person_type") == "EMPLOYEE":
                        state["pending_entry"] = False
                        state["entry_logged"] = False
                        state["is_new"] = False
                        state["direction"] = "IGNORE"
                    elif ready_to_exit and state.get("exit_sequence_active"):
                        state["pending_entry"] = False
                        if exit_sequence_ready:
                            commit_count_event(
                                "OUT",
                                track_id,
                                visitor_key,
                                state,
                                classification,
                                reason="exit_gate_confirmed",
                            )
                        else:
                            state["direction"] = "EXITING"
                    elif in_roi_now and not ready_to_count and not state.get("entry_logged"):
                        state["pending_entry"] = True
                        state["direction"] = "VERIFY"
                    elif in_roi_now:
                        if not state.get("entry_logged"):
                            if int(state.get("inside_frames", 0)) >= TRACK_ENTRY_CONFIRM_FRAMES:
                                if flow.get("inside"):
                                    state["pending_entry"] = False
                                    state["entry_logged"] = True
                                    state["is_new"] = False
                                    state["direction"] = "IN_ROI"
                                else:
                                    commit_count_event("IN", track_id, visitor_key, state, classification)
                            else:
                                state["pending_entry"] = True
                                state["direction"] = "VERIFY"
                        elif state.get("direction") not in {"IN", "OUT"}:
                            state["direction"] = "IN_ROI"
                    elif state.get("entry_logged"):
                        state["pending_entry"] = False
                        if exit_sequence_ready or state.get("exit_sequence_active"):
                            state["direction"] = "EXITING"
                        elif state.get("direction") not in {"IN", "OUT"}:
                            state["direction"] = "IN_ROI"
                    else:
                        state["pending_entry"] = False
                        state["direction"] = "TRACKING"

                    track.in_roi = in_roi_now
                else:
                    state["missing_frames"] = int(state.get("missing_frames", 0)) + 1
                    visitor_key = state.get("visitor_key", "")
                    classification = _classification_from_state(state)
                    track.in_roi = bool(state.get("last_in_roi", track.in_roi))
                    if visitor_key and visitor_key in visitor_flow_states:
                        visitor_flow_states[visitor_key]["last_seen_ts"] = now_ts

                    last_bbox = state.get("last_bbox")
                    if (
                        _state_can_exit(state)
                        and last_bbox
                        and int(state.get("missing_frames", 0)) >= TRACK_EXIT_CONFIRM_FRAMES
                        and _state_ready_for_exit_commit(
                            state,
                            final_phase=True,
                            frame_height=frame_h,
                        )
                    ):
                        commit_count_event(
                            "OUT",
                            track_id,
                            visitor_key,
                            state,
                            classification,
                            reason="exit_gate_head_disappear",
                        )

                visitor_states[track_id] = state

            lost_track_ids = [tid for tid in list(visitor_states.keys()) if tid not in active_track_ids]
            for lost_track_id in lost_track_ids:
                state = visitor_states.get(lost_track_id, {})
                visitor_key = state.get("visitor_key", "")
                last_bbox = state.get("last_bbox")
                should_finalize_exit = (
                    _state_can_exit(state)
                    and last_bbox
                    and _state_ready_for_exit_commit(
                        state,
                        final_phase=True,
                        frame_height=frame_h,
                    )
                )
                if should_finalize_exit:
                    commit_count_event(
                        "OUT",
                        lost_track_id,
                        visitor_key,
                        state,
                        _classification_from_state(state),
                        reason="exit_gate_head_disappear",
                    )
                del visitor_states[lost_track_id]

            draw_roi_polygon(display_frame, roi)
            draw_exit_gate(display_frame, _exit_gate_y(roi, frame_h))
            draw_bounding_boxes(display_frame, tracks, visitor_states)

            info_lines = [
                f"Tracks: {len(tracks)} | {tracker_mode_runtime}",
                (
                    f"Customer: {customer_tracks} | "
                    f"Employee: {employee_tracks} | Verify: {verifying_tracks}"
                ),
            ]
            if is_video_test:
                info_lines.append(
                    f"Video test: frame_step={TEST_FRAME_STEP} | identity={IDENTITY_MODE}"
                )
            elif local_file_events_consumed:
                info_lines.append("Local replay: events paused after first pass")
            if face_recognizer.enabled:
                if face_recognizer.available:
                    info_lines.append(f"Face registry: {face_recognizer.registry_size} employee(s)")
                else:
                    info_lines.append("Face recognition disabled")

            draw_info_overlay(display_frame, info_lines)
            update_latest_frame(display_frame, raw_frame=raw_frame)
            if output_writer is not None:
                output_writer.write(display_frame)
            recording_frame = raw_frame if EDGE_RECORDING_SAVE_MODE == "raw" and raw_frame is not None else display_frame
            backup_recorder.write(recording_frame, frame_ts=now_ts)

            processed_frames += 1
            if is_video_test:
                source_fps = float(getattr(cap, "source_fps", 0.0))
                source_seconds = (
                    max(last_frame_id - 1, 0) / source_fps
                    if source_fps > 0
                    else 0.0
                )
                if TEST_MAX_FRAMES > 0 and processed_frames >= TEST_MAX_FRAMES:
                    log.info("Stopping video test after %d processed frame(s)", processed_frames)
                    break
                if TEST_MAX_SECONDS > 0 and source_seconds >= TEST_MAX_SECONDS:
                    log.info("Stopping video test at %.2f source second(s)", source_seconds)
                    break

            # Adaptive sleep: only sleep if processing is faster than target fps.
            elapsed = time.time() - frame_start
            remaining = target_frame_time - elapsed
            if remaining > 0:
                time.sleep(remaining)
    finally:
        backup_recorder.close()
        if cap is not None:
            cap.release()
        if output_writer is not None:
            output_writer.release()
            if output_video_path is not None:
                log.info("Saved processed test video to %s", output_video_path)
