"""Main processing loop for the edge worker."""
import time
from datetime import datetime
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
from .capture import LatestFrameCapture, is_video_file
from .config import (
    CAMERA_ID,
    CONFIG_REFRESH,
    EDGE_STREAM_URL,
    IMG_SIZE,
    TRACK_CONFIRM_FRAMES,
    TRACK_MAX_DISAPPEARED,
    TRACK_MAX_DISTANCE,
)
from .detection import load_model, parse_roi, point_in_roi
from .face_recognition import EmployeeFaceRecognizer
from .logger import get_logger
from .reid import cleanup_old_tracks, reset_daily_cache, update_track_embedding
from .streaming import has_raw_stream_clients, update_latest_frame
from .tracker import CentroidTracker, DEEPSORT_AVAILABLE, DeepSORTTracker
from .visualization import draw_bounding_boxes, draw_info_overlay, draw_roi_polygon

log = get_logger("loops")

# Standard frame resolution — must match the frontend ROI editor (NATIVE_W × NATIVE_H)
FRAME_W = 1280
FRAME_H = 720
EVENT_COOLDOWN = 10.0


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


def real_loop():
    """YOLOv5 + DeepSORT + face recognition + employee-aware counting."""
    tracker_mode = "DeepSORT+ReID" if DEEPSORT_AVAILABLE else "CentroidTracker"

    token = login_token()
    model = load_model()
    face_recognizer = EmployeeFaceRecognizer()

    log.info("Running in REAL mode (%s + employee filtering)", tracker_mode)

    if DEEPSORT_AVAILABLE:
        tracker = DeepSORTTracker(
            max_age=TRACK_MAX_DISAPPEARED,
            n_init=TRACK_CONFIRM_FRAMES,
            max_cosine_distance=0.3,
        )
    else:
        tracker = CentroidTracker(
            max_disappeared=TRACK_MAX_DISAPPEARED,
            max_distance=TRACK_MAX_DISTANCE,
        )

    last_cfg_fetch = 0.0
    roi = None
    stream_url = EDGE_STREAM_URL or ""
    area_id = None
    visitor_states: Dict[int, Dict[str, Any]] = {}
    current_date = ""
    last_event_time: Dict[str, float] = {}
    cap = None
    cap_source = ""
    last_frame_id = 0

    # Target ~30 fps — adaptive sleep will skip if processing already takes longer
    TARGET_FRAME_TIME = 1.0 / 30.0

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
            if token is None:
                token = login_token()

            cfg = get_camera_config(token)
            if cfg and not EDGE_STREAM_URL:
                stream_url = (cfg.get("stream_url") or "").strip() or stream_url

            areas = get_counting_areas(token)
            if areas:
                active_area = next((area for area in areas if area.get("is_active")), None)
                if active_area:
                    roi = parse_roi(active_area.get("roi_polygon"))
                    area_id = active_area.get("area_id")

            if not roi:
                roi = [[50, 50], [1230, 50], [1230, 670], [50, 670]]

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
            log.warning("Stream URL not set. Configure via UI or env EDGE_STREAM_URL")
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
            if cap is not None and hasattr(cap, 'file_ended') and cap.file_ended:
                # Video file ended — loop from beginning
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

        if frame.shape[1] != FRAME_W or frame.shape[0] != FRAME_H:
            frame = cv2.resize(frame, (FRAME_W, FRAME_H))

        # Simpan raw_frame sebelum overlay (hanya copy jika ada client raw stream)
        raw_frame = frame.copy() if has_raw_stream_clients() else None
        display_frame = frame  # akan digambar overlay langsung di frame

        results = model(frame, size=IMG_SIZE)
        raw_detections = (
            results.xyxy[0].detach().cpu().numpy()
            if hasattr(results, "xyxy")
            else np.zeros((0, 6), dtype=np.float32)
        )

        detections: List[Tuple[float, float, float, float, float]] = []
        for x1, y1, x2, y2, conf, _ in raw_detections:
            detections.append((float(x1), float(y1), float(x2), float(y2), float(conf)))

        if DEEPSORT_AVAILABLE:
            tracks = tracker.update(frame, detections)
        else:
            boxes = [(det[0], det[1], det[2], det[3]) for det in detections]
            tracks = tracker.update(boxes)

        active_track_ids = list(tracks.keys())
        cleanup_old_tracks(active_track_ids)
        face_recognizer.cleanup(active_track_ids)

        # Batch face detection: run InsightFace once per frame, not per track
        face_recognizer.detect_faces_batch(frame, frame_id=last_frame_id)

        now_time = datetime.now()
        avg_confidence = float(np.mean([det[4] for det in detections])) if detections else 0.0
        customer_tracks = 0
        employee_tracks = 0
        verifying_tracks = 0

        for track_id, track in tracks.items():
            in_roi_now = point_in_roi(roi, track.centroid[0], track.centroid[1])
            body_embedding = track.embedding if hasattr(track, "embedding") else None
            fallback_key = update_track_embedding(track_id, body_embedding, CAMERA_ID, today)
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
                                label = classification.get("employee_name") or visitor_key
                                log.debug("Employee ignored IN: %s -> %s", label, result['status_code'])
                            else:
                                is_new = result["data"].get("is_new_unique", False)
                                status = "NEW" if is_new else "EXISTING"
                                state["is_new"] = is_new
                                state["direction"] = "IN"
                                log.debug("Visitor IN: %s... [%s] -> %s", visitor_key[:8], status, result['status_code'])
                        else:
                            log.error("Failed to send IN event: %s", result.get('error', 'Unknown'))
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
                            if classification["person_type"] == "EMPLOYEE":
                                label = classification.get("employee_name") or visitor_key
                                log.debug("Employee ignored OUT: %s -> %s", label, result['status_code'])
                            else:
                                log.debug("Visitor OUT: %s... -> %s", visitor_key[:8], result['status_code'])
                        else:
                            log.error("Failed to send OUT event: %s", result.get('error', 'Unknown'))
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
            else:
                if classification["person_type"] == "UNKNOWN":
                    state["direction"] = "TRACKING"

            visitor_states[track_id] = state
            track.in_roi = in_roi_now

        draw_roi_polygon(display_frame, roi)
        draw_bounding_boxes(display_frame, tracks, visitor_states)

        info_lines = [
            f"Tracks: {len(tracks)} | {tracker_mode}",
            (
                f"Customer: {customer_tracks} | "
                f"Employee: {employee_tracks} | Verify: {verifying_tracks}"
            ),
        ]
        if face_recognizer.enabled:
            if face_recognizer.available:
                info_lines.append(f"Face registry: {face_recognizer.registry_size} employee(s)")
            else:
                info_lines.append("Face recognition disabled")

        draw_info_overlay(display_frame, info_lines)
        update_latest_frame(display_frame, raw_frame=raw_frame)

        # Adaptive sleep: hanya sleep sisa waktu jika proses lebih cepat dari target fps
        elapsed = time.time() - frame_start
        remaining = TARGET_FRAME_TIME - elapsed
        if remaining > 0:
            time.sleep(remaining)
