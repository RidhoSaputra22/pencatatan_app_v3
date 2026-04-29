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
    EDGE_PROCESSING_MAX_FPS,
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
    TRACK_MAX_COSINE_DISTANCE,
    TRACK_MAX_DISAPPEARED,
    TRACK_MAX_DISTANCE,
)
from .detection import load_model, parse_roi, point_in_roi, suppress_duplicate_person_detections
from .face_recognition import EmployeeFaceRecognizer
from .logger import get_logger
from .reid import cleanup_old_tracks, reset_daily_cache, update_track_embedding
from .streaming import has_raw_stream_clients, update_latest_frame
from .tracker import CentroidTracker, DEEPSORT_AVAILABLE, DeepSORTTracker
from .visualization import draw_bounding_boxes, draw_info_overlay, draw_roi_polygon

log = get_logger("loops")

EVENT_COOLDOWN = 10.0
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


def real_loop():
    """YOLO + tracking + optional offline video test profile."""
    requested_video_test = TEST_MODE == "video"
    test_input_exists = bool(TEST_INPUT) and Path(TEST_INPUT).exists()
    is_video_test = requested_video_test and test_input_exists
    events_enabled = not is_video_test
    tracker_mode = "DeepSORT+ReID" if DEEPSORT_AVAILABLE and not FORCE_CENTROID else "CentroidTracker"
    needs_backend_auth = events_enabled or FACE_REGISTRY_SOURCE == "backend"

    token = login_token() if needs_backend_auth else None
    model = load_model()
    face_recognizer = EmployeeFaceRecognizer()

    log.info("Running in REAL mode (%s + employee filtering)", tracker_mode)
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

    if DEEPSORT_AVAILABLE and not FORCE_CENTROID:
        tracker = DeepSORTTracker(
            max_age=TRACK_MAX_DISAPPEARED,
            n_init=TRACK_CONFIRM_FRAMES,
            max_cosine_distance=TRACK_MAX_COSINE_DISTANCE,
        )
        if getattr(tracker, "using_fallback", False):
            tracker_mode = "CentroidTracker"
    else:
        tracker = CentroidTracker(
            max_disappeared=TRACK_MAX_DISAPPEARED,
            max_distance=TRACK_MAX_DISTANCE,
        )

    last_cfg_fetch = 0.0
    roi = None
    roi_shape: Tuple[int, int] = (0, 0)
    stream_url = TEST_INPUT if is_video_test else (EDGE_STREAM_URL or "")
    area_id = None
    visitor_states: Dict[int, Dict[str, Any]] = {}
    current_date = ""
    last_event_time: Dict[str, float] = {}
    cap = None
    cap_source = ""
    last_frame_id = 0
    processed_frames = 0
    output_writer = None
    output_video_path = None

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

            for track_id, track in tracks.items():
                in_roi_now = point_in_roi(roi, track.centroid[0], track.centroid[1])
                identity_embedding = _resolve_identity_embedding(face_recognizer, track)
                fallback_key = update_track_embedding(track_id, identity_embedding, CAMERA_ID, today)
                classification = face_recognizer.classify_track(frame, track_id, track.bbox)
                visitor_key = _stable_identity_key(fallback_key, classification)

                state = visitor_states.setdefault(
                    track_id,
                    {
                        "is_new": False,
                        "direction": "TRACKING",
                        "visitor_key": visitor_key,
                        "person_type": classification.get("person_type", "UNKNOWN"),
                        "pending_entry": False,
                        "entry_logged": False,
                    },
                )
                state.update(
                    {
                        "visitor_key": visitor_key,
                        "person_type": classification.get("person_type", "UNKNOWN"),
                        "employee_id": classification.get("employee_id"),
                        "employee_code": classification.get("employee_code"),
                        "employee_name": classification.get("employee_name"),
                        "match_score": classification.get("match_score"),
                    }
                )

                if classification["person_type"] == "EMPLOYEE":
                    employee_tracks += 1
                elif classification["person_type"] == "UNKNOWN":
                    verifying_tracks += 1
                else:
                    customer_tracks += 1

                if (not track.in_roi) and in_roi_now:
                    state["pending_entry"] = True

                if in_roi_now and state.get("pending_entry"):
                    if classification["person_type"] == "UNKNOWN":
                        state["direction"] = "VERIFY"
                    else:
                        debounce_key = f"{visitor_key}_IN"
                        if now_ts - last_event_time.get(debounce_key, 0.0) >= EVENT_COOLDOWN:
                            if events_enabled:
                                result = _send_track_event(
                                    "IN",
                                    track_id,
                                    visitor_key,
                                    area_id,
                                    now_time,
                                    avg_confidence,
                                    classification,
                                    token,
                                )
                                if result["success"]:
                                    state["pending_entry"] = False
                                    state["entry_logged"] = True
                                    last_event_time[debounce_key] = now_ts
                                    if classification["person_type"] == "EMPLOYEE":
                                        state["is_new"] = False
                                        state["direction"] = "IGNORE"
                                    else:
                                        state["is_new"] = result["data"].get("is_new_unique", False)
                                        state["direction"] = "IN"
                                else:
                                    log.error("Failed to send IN event: %s", result.get("error", "Unknown"))
                            else:
                                state["pending_entry"] = False
                                state["entry_logged"] = True
                                state["direction"] = (
                                    "IGNORE" if classification["person_type"] == "EMPLOYEE" else "IN"
                                )
                                last_event_time[debounce_key] = now_ts
                        else:
                            state["pending_entry"] = False
                            state["entry_logged"] = False
                            state["direction"] = (
                                "IGNORE"
                                if classification["person_type"] == "EMPLOYEE"
                                else "IN"
                            )

                elif track.in_roi and (not in_roi_now):
                    state["pending_entry"] = False
                    if state.get("entry_logged"):
                        debounce_key = f"{visitor_key}_OUT"
                        if now_ts - last_event_time.get(debounce_key, 0.0) >= EVENT_COOLDOWN:
                            if events_enabled:
                                result = _send_track_event(
                                    "OUT",
                                    track_id,
                                    visitor_key,
                                    area_id,
                                    now_time,
                                    avg_confidence,
                                    classification,
                                    token,
                                )
                                if result["success"]:
                                    last_event_time[debounce_key] = now_ts
                                    state["entry_logged"] = False
                                    state["direction"] = (
                                        "IGNORE"
                                        if classification["person_type"] == "EMPLOYEE"
                                        else "OUT"
                                    )
                                else:
                                    log.error("Failed to send OUT event: %s", result.get("error", "Unknown"))
                            else:
                                last_event_time[debounce_key] = now_ts
                                state["entry_logged"] = False
                                state["direction"] = (
                                    "IGNORE" if classification["person_type"] == "EMPLOYEE" else "OUT"
                                )
                        else:
                            state["entry_logged"] = False
                            state["direction"] = (
                                "IGNORE"
                                if classification["person_type"] == "EMPLOYEE"
                                else "OUT"
                            )

                elif in_roi_now:
                    if state.get("pending_entry"):
                        state["direction"] = "VERIFY"
                    elif classification["person_type"] == "EMPLOYEE":
                        state["direction"] = "IGNORE"
                    elif classification["person_type"] == "UNKNOWN":
                        state["direction"] = "VERIFY"
                    elif state.get("direction") not in {"IN", "OUT"}:
                        state["direction"] = "IN_ROI"
                elif classification["person_type"] == "UNKNOWN":
                    state["direction"] = "TRACKING"

                visitor_states[track_id] = state
                track.in_roi = in_roi_now

            draw_roi_polygon(display_frame, roi)
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
            if face_recognizer.enabled:
                if face_recognizer.available:
                    info_lines.append(f"Face registry: {face_recognizer.registry_size} employee(s)")
                else:
                    info_lines.append("Face recognition disabled")

            draw_info_overlay(display_frame, info_lines)
            update_latest_frame(display_frame, raw_frame=raw_frame)
            if output_writer is not None:
                output_writer.write(display_frame)

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
        if cap is not None:
            cap.release()
        if output_writer is not None:
            output_writer.release()
            if output_video_path is not None:
                log.info("Saved processed test video to %s", output_video_path)
