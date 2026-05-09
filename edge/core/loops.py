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
    login_token,
    send_visitor_event,
)
from .capture import LatestFrameCapture
from .config import (
    CAMERA_ID,
    CONFIG_REFRESH,
    EDGE_LOCAL_FILE_REPLAY_POST_EVENTS,
    EDGE_PROCESSING_MAX_FPS,
    EDGE_RECORDING_ENABLED,
    EDGE_RECORDING_FILE_PREFIX,
    EDGE_RECORDING_FPS,
    EDGE_RECORDING_MAX_GAP_SECONDS,
    EDGE_RECORDING_OUTPUT_DIR,
    EDGE_RECORDING_SEGMENT_MINUTES,
    EDGE_RECORDING_SEGMENT_SECONDS,
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
)
from .detection import load_model, parse_roi, point_in_roi, suppress_duplicate_person_detections
from .face_recognition import EmployeeFaceRecognizer
from .logger import get_logger
from .reid import cleanup_old_tracks, reset_daily_cache, update_track_identity
from .recording import SegmentedVideoRecorder
from .streaming import has_raw_stream_clients, update_latest_frame
from .tracker import CentroidTracker, DEEPSORT_AVAILABLE, DeepSORTTracker
from .visualization import draw_bounding_boxes, draw_exit_gate, draw_info_overlay, draw_roi_polygon

log = get_logger("loops")

EVENT_COOLDOWN = TRACK_EVENT_COOLDOWN_SECONDS
REFERENCE_FRAME_SIZE = (TEST_FRAME_WIDTH, TEST_FRAME_HEIGHT)


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
    return identity.get("identity_status") in {"CONFIRMED", "FALLBACK"}


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
    tracker_mode = "DeepSORT+ReID" if DEEPSORT_AVAILABLE and not FORCE_CENTROID else "CentroidTracker"
    if DEEPSORT_AVAILABLE and not FORCE_CENTROID:
        tracker = DeepSORTTracker(
            max_age=TRACK_MAX_DISAPPEARED,
            n_init=TRACK_CONFIRM_FRAMES,
            max_cosine_distance=TRACK_MAX_COSINE_DISTANCE,
        )
        if getattr(tracker, "using_fallback", False):
            tracker_mode = "CentroidTracker"
        return tracker, tracker_mode

    return (
        CentroidTracker(
            max_disappeared=TRACK_MAX_DISAPPEARED,
            max_distance=TRACK_MAX_DISTANCE,
        ),
        tracker_mode,
    )


def real_loop():
    """YOLO + tracking + optional offline video test profile."""
    requested_video_test = TEST_MODE == "video"
    test_input_exists = bool(TEST_INPUT) and Path(TEST_INPUT).exists()
    is_video_test = requested_video_test and test_input_exists
    base_events_enabled = not is_video_test
    events_enabled = base_events_enabled
    local_file_events_consumed = False
    needs_backend_auth = base_events_enabled or FACE_REGISTRY_SOURCE == "backend"

    token = login_token() if needs_backend_auth else None
    model = load_model()
    face_recognizer = EmployeeFaceRecognizer()

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
    last_frame_id = 0
    processed_frames = 0
    frame_w = TEST_FRAME_WIDTH
    frame_h = TEST_FRAME_HEIGHT
    output_writer = None
    output_video_path = None
    backup_recorder = SegmentedVideoRecorder(
        output_dir=EDGE_RECORDING_OUTPUT_DIR,
        camera_id=CAMERA_ID,
        segment_seconds=float(EDGE_RECORDING_SEGMENT_SECONDS),
        fps=_recording_fps(),
        enabled=EDGE_RECORDING_ENABLED,
        max_gap_seconds=EDGE_RECORDING_MAX_GAP_SECONDS,
        file_prefix=EDGE_RECORDING_FILE_PREFIX,
    )

    if backup_recorder.enabled:
        log.info(
            "YOLO backup active: every %d minute(s) -> %s",
            EDGE_RECORDING_SEGMENT_MINUTES,
            EDGE_RECORDING_OUTPUT_DIR,
        )

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

                if not is_video_test:
                    cfg = get_camera_config(token)
                    if cfg and not EDGE_STREAM_URL:
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
                    last_frame_id = 0
                    time.sleep(1)
                    continue
                log.warning("Frame read failed. Reconnecting...")
                if cap is not None:
                    cap.release()
                cap = None
                cap_source = ""
                last_frame_id = 0
                time.sleep(1)
                continue

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

            # Keep raw frame before drawing overlay.
            raw_frame = frame.copy() if has_raw_stream_clients() else None
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
            backup_recorder.write(display_frame, frame_ts=now_ts)

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
