#!/usr/bin/env python3
"""Offline video test harness for YOLO + DeepSORT + reID."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "test" / "edge" / "output"
EDGE_REFERENCE_SIZE = (1280, 720)


def _resolve_project_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return path.resolve()


def _slugify(value: str) -> str:
    cleaned = []
    for char in value.strip().lower():
        if char.isalnum():
            cleaned.append(char)
        elif char in {"-", "_", "."}:
            cleaned.append("_")
        else:
            cleaned.append("_")
    slug = "".join(cleaned).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "default"


def _model_label(backend: str, weights: str) -> str:
    backend_slug = _slugify(backend or "model")
    if weights:
        weight_name = Path(weights).stem
    else:
        weight_name = "default_weights"
    weight_slug = _slugify(weight_name)
    return f"{backend_slug}_{weight_slug}"


def _bootstrap_runtime(argv: Sequence[str]) -> None:
    """Apply CLI overrides before importing edge modules that read .env."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--weights")
    parser.add_argument("--backend", choices=("yolov5", "ultralytics"))
    parser.add_argument("--device")
    parser.add_argument("--reid-match-threshold", type=float)
    parser.add_argument("--with-face-recognition", action="store_true")
    args, _ = parser.parse_known_args(argv)

    if args.weights:
        os.environ["YOLOV5_WEIGHTS"] = str(_resolve_project_path(args.weights))
    if args.backend:
        os.environ["YOLO_BACKEND"] = args.backend
    if args.device:
        os.environ["YOLOV5_DEVICE"] = args.device
    if args.reid_match_threshold is not None:
        os.environ["REID_MATCH_THRESHOLD"] = str(args.reid_match_threshold)
    if not args.with_face_recognition:
        os.environ["FACE_RECOGNITION_ENABLED"] = "false"

    configured_weights = os.getenv("YOLOV5_WEIGHTS", "").strip()
    resolved_weights = _resolve_project_path(configured_weights) if configured_weights else None
    fallback_weights = PROJECT_DIR / "edge" / "yolov5s.pt"

    if (not configured_weights or not resolved_weights or not resolved_weights.exists()) and fallback_weights.exists():
        os.environ["YOLOV5_WEIGHTS"] = str(fallback_weights)
        if not args.backend:
            os.environ["YOLO_BACKEND"] = "yolov5"


_bootstrap_runtime(sys.argv[1:])

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import cv2
import numpy as np

from edge.core.config import CAMERA_ID, IMG_SIZE, TRACK_CONFIRM_FRAMES, TRACK_MAX_DISAPPEARED, TRACK_MAX_DISTANCE
from edge.core.detection import load_model, parse_roi, point_in_roi, suppress_duplicate_person_detections
from edge.core.face_recognition import EmployeeFaceRecognizer
from edge.core.reid import cleanup_old_tracks, reset_daily_cache, update_track_embedding
from edge.core.tracker import CentroidTracker, DEEPSORT_AVAILABLE, DeepSORTTracker
from edge.core.visualization import draw_info_overlay, draw_roi_polygon


TRACK_CSV_FIELDS = [
    "frame_index",
    "time_seconds",
    "track_id",
    "visitor_key",
    "visitor_key_short",
    "reid_source",
    "track_backend",
    "roi_status",
    "event",
    "unique_status",
    "person_type",
    "employee_id",
    "employee_code",
    "employee_name",
    "match_score",
    "x1",
    "y1",
    "x2",
    "y2",
    "centroid_x",
    "centroid_y",
    "confidence",
    "embedding_available",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test YOLO + DeepSORT + reID on a local video and export annotated video + CSV.",
    )
    parser.add_argument("--input", required=True, help="Path video input.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Folder keluaran untuk video, CSV, dan summary.",
    )
    parser.add_argument(
        "--output-name",
        default="",
        help="Prefix nama file output. Default: nama file video input.",
    )
    parser.add_argument(
        "--roi-json",
        default="",
        help="ROI polygon JSON, contoh: [[50,50],[1230,50],[1230,670],[50,670]]",
    )
    parser.add_argument(
        "--frame-width",
        type=int,
        default=EDGE_REFERENCE_SIZE[0],
        help="Lebar frame output. Default menyesuaikan pipeline edge.",
    )
    parser.add_argument(
        "--frame-height",
        type=int,
        default=EDGE_REFERENCE_SIZE[1],
        help="Tinggi frame output. Default menyesuaikan pipeline edge.",
    )
    parser.add_argument(
        "--keep-source-size",
        action="store_true",
        help="Gunakan resolusi asli video input tanpa resize ke 1280x720.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Batasi jumlah frame yang diproses. 0 = semua frame.",
    )
    parser.add_argument(
        "--frame-step",
        type=int,
        default=1,
        help="Proses tiap N frame. Contoh 2 = ambil 1 frame tiap 2 frame.",
    )
    parser.add_argument(
        "--output-fps",
        type=float,
        default=0.0,
        help="FPS output. 0 = ikuti FPS video input (dibagi frame-step bila perlu).",
    )
    parser.add_argument(
        "--img-size",
        type=int,
        default=IMG_SIZE,
        help="Ukuran inferensi YOLO.",
    )
    parser.add_argument(
        "--force-centroid",
        action="store_true",
        help="Paksa pakai CentroidTracker walau DeepSORT tersedia.",
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=TRACK_MAX_DISAPPEARED,
        help="Maksimum frame track boleh hilang sebelum dihapus.",
    )
    parser.add_argument(
        "--n-init",
        type=int,
        default=TRACK_CONFIRM_FRAMES,
        help="Jumlah konfirmasi awal track untuk DeepSORT.",
    )
    parser.add_argument(
        "--max-distance",
        type=float,
        default=TRACK_MAX_DISTANCE,
        help="Maksimum jarak centroid untuk fallback tracker.",
    )
    parser.add_argument(
        "--max-cosine-distance",
        type=float,
        default=0.3,
        help="Threshold cosine distance DeepSORT.",
    )
    parser.add_argument(
        "--backend",
        choices=("yolov5", "ultralytics"),
        default=os.getenv("YOLO_BACKEND", "yolov5"),
        help="Override backend YOLO untuk sesi test ini.",
    )
    parser.add_argument(
        "--weights",
        default=os.getenv("YOLOV5_WEIGHTS", ""),
        help="Override file weights model untuk sesi test ini.",
    )
    parser.add_argument(
        "--device",
        default=os.getenv("YOLOV5_DEVICE", "auto"),
        help="Override device inferensi, misal cpu/cuda/xpu/auto.",
    )
    parser.add_argument(
        "--reid-match-threshold",
        type=float,
        default=float(os.getenv("REID_MATCH_THRESHOLD", "0.77")),
        help="Threshold similarity untuk merge reID antar track.",
    )
    parser.add_argument(
        "--with-face-recognition",
        action="store_true",
        help="Aktifkan klasifikasi wajah employee jika dependency tersedia.",
    )
    return parser


def _load_roi(roi_json: str, frame_width: int, frame_height: int) -> List[List[float]]:
    roi = parse_roi(roi_json) if roi_json else None
    if roi is None:
        roi = parse_roi(os.getenv("DEFAULT_AREA_ROI_POLYGON", ""))
    if roi is None:
        roi = [
            [0.0, 0.0],
            [float(frame_width - 1), 0.0],
            [float(frame_width - 1), float(frame_height - 1)],
            [0.0, float(frame_height - 1)],
        ]
    return _scale_roi(roi, frame_width, frame_height)


def _scale_roi(roi: List[List[float]], frame_width: int, frame_height: int) -> List[List[float]]:
    if not roi:
        return roi

    ref_w, ref_h = EDGE_REFERENCE_SIZE
    max_x = max(float(point[0]) for point in roi)
    max_y = max(float(point[1]) for point in roi)

    if frame_width == ref_w and frame_height == ref_h:
        return roi
    if max_x > ref_w or max_y > ref_h:
        return roi

    scale_x = frame_width / float(ref_w)
    scale_y = frame_height / float(ref_h)
    scaled: List[List[float]] = []
    for x, y in roi:
        scaled.append([round(float(x) * scale_x, 2), round(float(y) * scale_y, 2)])
    return scaled


def _bbox_iou(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter_area
    if denom <= 0:
        return 0.0
    return inter_area / denom


def _match_detection_confidence(
    track_bbox: Tuple[float, float, float, float],
    detections: List[Tuple[float, float, float, float, float]],
) -> float:
    best_iou = 0.0
    best_conf = 0.0
    for detection in detections:
        bbox = (detection[0], detection[1], detection[2], detection[3])
        score = _bbox_iou(track_bbox, bbox)
        if score > best_iou:
            best_iou = score
            best_conf = float(detection[4])
    return round(best_conf, 4)


def _track_color(state: Dict[str, Any], in_roi: bool) -> Tuple[int, int, int]:
    person_type = state.get("person_type", "CUSTOMER")
    if person_type == "EMPLOYEE":
        return (255, 0, 0)
    if person_type == "UNKNOWN":
        return (0, 255, 255)
    if not in_roi:
        return (160, 160, 160)
    if state.get("unique_status") == "NEW":
        return (0, 255, 0)
    return (0, 165, 255)


def _draw_test_tracks(frame: np.ndarray, tracks: Dict[int, Any], visitor_states: Dict[int, Dict[str, Any]]) -> None:
    for track_id, track in tracks.items():
        if getattr(track, "disappeared", 0) > 0:
            continue

        state = visitor_states.get(track_id, {})
        in_roi = bool(state.get("in_roi", False))
        color = _track_color(state, in_roi)

        x1, y1, x2, y2 = [int(v) for v in track.bbox]
        label_parts = [f"T{track_id}"]
        if state.get("unique_status"):
            label_parts.append(str(state["unique_status"]))
        if state.get("roi_status"):
            label_parts.append(str(state["roi_status"]))
        if state.get("visitor_key_short"):
            label_parts.append(f"V:{state['visitor_key_short']}")
        if state.get("person_type") == "EMPLOYEE" and state.get("employee_code"):
            label_parts.append(str(state["employee_code"]))
        label = " ".join(label_parts)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, (int(track.centroid[0]), int(track.centroid[1])), 4, color, -1)

        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        top = max(0, y1 - 22)
        bottom = max(label_h + 10, y1)
        cv2.rectangle(frame, (x1, top), (x1 + label_w + 10, bottom), color, -1)
        cv2.putText(
            frame,
            label,
            (x1 + 5, bottom - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )


def _writer_fps(source_fps: float, output_fps: float, frame_step: int) -> float:
    if output_fps > 0:
        return output_fps
    base = source_fps if source_fps > 0 else 30.0
    adjusted = base / max(frame_step, 1)
    return max(adjusted, 1.0)


def _build_tracker(args: argparse.Namespace) -> Tuple[Any, str]:
    if not args.force_centroid and DEEPSORT_AVAILABLE:
        tracker = DeepSORTTracker(
            max_age=args.max_age,
            n_init=args.n_init,
            max_cosine_distance=args.max_cosine_distance,
        )
        if not getattr(tracker, "using_fallback", False):
            return tracker, "DeepSORT+ReID"
        return tracker, "CentroidTracker"

    tracker = CentroidTracker(
        max_disappeared=args.max_age,
        max_distance=args.max_distance,
    )
    return tracker, "CentroidTracker"


def _current_tracker_backend(tracker: Any, default_backend: str) -> str:
    if isinstance(tracker, DeepSORTTracker):
        return "CentroidTracker" if getattr(tracker, "using_fallback", False) else "DeepSORT+ReID"
    return default_backend


def _print_progress(processed_frames: int, total_frames: int, elapsed: float) -> None:
    if total_frames > 0:
        print(f"[progress] frame {processed_frames}/{total_frames} | elapsed {elapsed:.1f}s")
    else:
        print(f"[progress] frame {processed_frames} | elapsed {elapsed:.1f}s")


def _person_type_bucket(person_type: Optional[str]) -> str:
    value = (person_type or "UNKNOWN").upper()
    if value in {"CUSTOMER", "EMPLOYEE", "UNKNOWN"}:
        return value
    return "UNKNOWN"


def _person_type_rank(person_type: Optional[str]) -> int:
    value = _person_type_bucket(person_type)
    if value == "EMPLOYEE":
        return 3
    if value == "CUSTOMER":
        return 2
    return 1


def main() -> int:
    args = build_parser().parse_args()

    input_path = _resolve_project_path(args.input)
    if not input_path.exists():
        print(f"Input video tidak ditemukan: {input_path}", file=sys.stderr)
        return 1

    output_dir = _resolve_project_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    name_prefix = args.output_name.strip() or input_path.stem
    active_backend = os.getenv("YOLO_BACKEND", args.backend)
    active_weights = os.getenv("YOLOV5_WEIGHTS", args.weights)
    model_label = _model_label(active_backend, active_weights)
    model_output_dir = output_dir / model_label
    model_output_dir.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        print(f"Gagal membuka video: {input_path}", file=sys.stderr)
        return 1

    try:
        source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        total_frames_raw = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        total_frames_estimated = (
            (total_frames_raw + max(args.frame_step, 1) - 1) // max(args.frame_step, 1)
            if total_frames_raw > 0
            else 0
        )

        frame_width = source_width if args.keep_source_size and source_width > 0 else args.frame_width
        frame_height = source_height if args.keep_source_size and source_height > 0 else args.frame_height
        writer_fps = _writer_fps(source_fps, args.output_fps, args.frame_step)

        roi = _load_roi(args.roi_json, frame_width, frame_height)

        video_path = model_output_dir / f"{name_prefix}_tracking.mp4"
        csv_path = model_output_dir / f"{name_prefix}_tracks.csv"
        summary_path = model_output_dir / f"{name_prefix}_summary.json"

        writer = cv2.VideoWriter(
            str(video_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            writer_fps,
            (frame_width, frame_height),
        )
        if not writer.isOpened():
            print(f"Gagal membuat video output: {video_path}", file=sys.stderr)
            return 1

        model = load_model()
        tracker, tracker_backend = _build_tracker(args)
        tracker_uses_frame_detections = isinstance(tracker, DeepSORTTracker)
        face_recognizer = EmployeeFaceRecognizer()

        visitor_states: Dict[int, Dict[str, Any]] = {}
        seen_visitor_keys: set[str] = set()
        seen_track_ids: set[int] = set()
        visitor_profiles: Dict[str, Dict[str, Any]] = {}
        visitor_last_state: Dict[str, Dict[str, Any]] = {}
        event_counts = {"enter_roi": 0, "exit_roi": 0}
        event_counts_by_person_type = {
            "CUSTOMER": {"enter_roi": 0, "exit_roi": 0},
            "EMPLOYEE": {"enter_roi": 0, "exit_roi": 0},
            "UNKNOWN": {"enter_roi": 0, "exit_roi": 0},
        }
        unique_event_visitors = {"enter_roi": set(), "exit_roi": set()}
        peak_concurrent_tracks = 0
        peak_tracks_in_roi = 0
        peak_unique_visitors_visible = 0
        peak_unique_visitors_in_roi = 0
        peak_unique_visitors_by_person_type_visible = {
            "CUSTOMER": 0,
            "EMPLOYEE": 0,
            "UNKNOWN": 0,
        }
        peak_unique_visitors_by_person_type_in_roi = {
            "CUSTOMER": 0,
            "EMPLOYEE": 0,
            "UNKNOWN": 0,
        }
        frames_with_detections = 0
        last_frame_unique_visitors: set[str] = set()
        last_frame_unique_visitors_in_roi: set[str] = set()
        last_frame_unique_visitors_by_person_type = {
            "CUSTOMER": set(),
            "EMPLOYEE": set(),
            "UNKNOWN": set(),
        }
        start_time = time.time()
        today = datetime.now().strftime("%Y-%m-%d")
        reset_daily_cache(today)
        tracker_backend_runtime = _current_tracker_backend(tracker, tracker_backend)

        processed_frames = 0
        csv_rows = 0
        source_frame_index = 0

        print(f"[info] input   : {input_path}")
        print(f"[info] model   : {model_label}")
        print(f"[info] out dir : {model_output_dir}")
        print(f"[info] output  : {video_path}")
        print(f"[info] csv     : {csv_path}")
        print(f"[info] tracker : {tracker_backend_runtime}")
        print(f"[info] yolo    : {active_backend} | weights={active_weights}")
        print(f"[info] reid    : threshold={os.getenv('REID_MATCH_THRESHOLD', '0.77')}")
        print(
            f"[info] face    : "
            f"{'enabled' if face_recognizer.enabled and face_recognizer.available else 'disabled'}"
        )

        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer_csv = csv.DictWriter(csv_file, fieldnames=TRACK_CSV_FIELDS)
            writer_csv.writeheader()

            while True:
                ok, frame = capture.read()
                if not ok or frame is None:
                    break

                source_frame_index += 1
                if args.frame_step > 1 and (source_frame_index - 1) % args.frame_step != 0:
                    continue

                if frame.shape[1] != frame_width or frame.shape[0] != frame_height:
                    frame = cv2.resize(frame, (frame_width, frame_height))

                results = model(frame, size=args.img_size)
                raw_detections = (
                    results.xyxy[0].detach().cpu().numpy()
                    if hasattr(results, "xyxy")
                    else np.zeros((0, 6), dtype=np.float32)
                )

                detections: List[Tuple[float, float, float, float, float]] = []
                for x1, y1, x2, y2, conf, _ in raw_detections:
                    detections.append((float(x1), float(y1), float(x2), float(y2), float(conf)))
                detections = suppress_duplicate_person_detections(detections)
                if detections:
                    frames_with_detections += 1

                if tracker_uses_frame_detections:
                    tracks = tracker.update(frame, detections)
                else:
                    boxes = [(det[0], det[1], det[2], det[3]) for det in detections]
                    tracks = tracker.update(boxes)
                tracker_backend_runtime = _current_tracker_backend(tracker, tracker_backend)

                active_track_ids = list(tracks.keys())
                cleanup_old_tracks(active_track_ids)
                face_recognizer.cleanup(active_track_ids)
                face_recognizer.detect_faces_batch(frame, frame_id=source_frame_index)

                display_frame = frame.copy()
                draw_roi_polygon(display_frame, roi)

                customer_tracks = 0
                employee_tracks = 0
                verifying_tracks = 0
                tracks_in_roi = 0
                frame_unique_visitors: set[str] = set()
                frame_unique_visitors_in_roi: set[str] = set()
                frame_unique_visitors_by_person_type = {
                    "CUSTOMER": set(),
                    "EMPLOYEE": set(),
                    "UNKNOWN": set(),
                }
                frame_unique_visitors_in_roi_by_person_type = {
                    "CUSTOMER": set(),
                    "EMPLOYEE": set(),
                    "UNKNOWN": set(),
                }

                for track_id, track in tracks.items():
                    seen_track_ids.add(track_id)
                    previous_in_roi = bool(getattr(track, "in_roi", False))
                    in_roi_now = point_in_roi(roi, track.centroid[0], track.centroid[1])
                    if in_roi_now:
                        tracks_in_roi += 1

                    body_embedding = getattr(track, "embedding", None)
                    visitor_key = update_track_embedding(track_id, body_embedding, CAMERA_ID, today)
                    classification = face_recognizer.classify_track(frame, track_id, track.bbox)
                    person_type = _person_type_bucket(classification.get("person_type", "CUSTOMER"))
                    frame_unique_visitors.add(visitor_key)
                    frame_unique_visitors_by_person_type[person_type].add(visitor_key)
                    if in_roi_now:
                        frame_unique_visitors_in_roi.add(visitor_key)
                        frame_unique_visitors_in_roi_by_person_type[person_type].add(visitor_key)

                    unique_status = "NEW" if visitor_key not in seen_visitor_keys else "SEEN"
                    seen_visitor_keys.add(visitor_key)

                    profile = visitor_profiles.get(visitor_key)
                    if profile is None or _person_type_rank(person_type) >= _person_type_rank(profile.get("person_type")):
                        visitor_profiles[visitor_key] = {
                            "person_type": person_type,
                            "employee_id": classification.get("employee_id"),
                            "employee_code": classification.get("employee_code"),
                            "employee_name": classification.get("employee_name"),
                        }

                    if person_type == "EMPLOYEE":
                        employee_tracks += 1
                    elif person_type == "UNKNOWN":
                        verifying_tracks += 1
                    else:
                        customer_tracks += 1

                    event = ""
                    if not previous_in_roi and in_roi_now:
                        event = "ENTER_ROI"
                    elif previous_in_roi and not in_roi_now:
                        event = "EXIT_ROI"

                    if event == "ENTER_ROI":
                        event_counts["enter_roi"] += 1
                        event_counts_by_person_type[person_type]["enter_roi"] += 1
                        unique_event_visitors["enter_roi"].add(visitor_key)
                    elif event == "EXIT_ROI":
                        event_counts["exit_roi"] += 1
                        event_counts_by_person_type[person_type]["exit_roi"] += 1
                        unique_event_visitors["exit_roi"].add(visitor_key)

                    roi_status = "IN_ROI" if in_roi_now else "OUTSIDE_ROI"
                    visitor_key_short = visitor_key[:8] if visitor_key else ""
                    confidence = _match_detection_confidence(track.bbox, detections)
                    visitor_last_state[visitor_key] = {
                        "in_roi": in_roi_now,
                        "track_id": track_id,
                        "person_type": person_type,
                        "last_frame_index": source_frame_index,
                    }

                    state = visitor_states.setdefault(track_id, {})
                    state.update(
                        {
                            "visitor_key": visitor_key,
                            "visitor_key_short": visitor_key_short,
                            "unique_status": unique_status,
                            "roi_status": roi_status,
                            "event": event,
                            "in_roi": in_roi_now,
                            "person_type": person_type,
                            "employee_id": classification.get("employee_id"),
                            "employee_code": classification.get("employee_code"),
                            "employee_name": classification.get("employee_name"),
                            "match_score": classification.get("match_score"),
                            "confidence": confidence,
                        }
                    )

                    track.in_roi = in_roi_now

                    writer_csv.writerow(
                        {
                            "frame_index": source_frame_index,
                            "time_seconds": round(
                                (source_frame_index - 1) / (source_fps if source_fps > 0 else writer_fps),
                                3,
                            ),
                            "track_id": track_id,
                            "visitor_key": visitor_key,
                            "visitor_key_short": visitor_key_short,
                            "reid_source": "embedding" if body_embedding is not None else "fallback_track_id",
                            "track_backend": tracker_backend_runtime,
                            "roi_status": roi_status,
                            "event": event,
                            "unique_status": unique_status,
                            "person_type": classification.get("person_type", "CUSTOMER"),
                            "employee_id": classification.get("employee_id"),
                            "employee_code": classification.get("employee_code"),
                            "employee_name": classification.get("employee_name"),
                            "match_score": (
                                round(float(classification["match_score"]), 4)
                                if classification.get("match_score") is not None
                                else ""
                            ),
                            "x1": round(float(track.bbox[0]), 2),
                            "y1": round(float(track.bbox[1]), 2),
                            "x2": round(float(track.bbox[2]), 2),
                            "y2": round(float(track.bbox[3]), 2),
                            "centroid_x": round(float(track.centroid[0]), 2),
                            "centroid_y": round(float(track.centroid[1]), 2),
                            "confidence": confidence,
                            "embedding_available": bool(body_embedding is not None),
                        }
                    )
                    csv_rows += 1

                _draw_test_tracks(display_frame, tracks, visitor_states)
                last_frame_unique_visitors = set(frame_unique_visitors)
                last_frame_unique_visitors_in_roi = set(frame_unique_visitors_in_roi)
                last_frame_unique_visitors_by_person_type = {
                    person_type: set(visitor_keys)
                    for person_type, visitor_keys in frame_unique_visitors_by_person_type.items()
                }
                info_lines = [
                    f"Tracks: {len(tracks)} | {tracker_backend_runtime}",
                    f"Customer: {customer_tracks} | Employee: {employee_tracks} | Verify: {verifying_tracks}",
                    f"Unique so far: {len(seen_visitor_keys)} | Detections: {len(detections)}",
                    f"Unique now: {len(frame_unique_visitors)} | In ROI now: {len(frame_unique_visitors_in_roi)}",
                ]
                draw_info_overlay(display_frame, info_lines, show_live_indicator=False)
                writer.write(display_frame)

                peak_concurrent_tracks = max(peak_concurrent_tracks, len(tracks))
                peak_tracks_in_roi = max(peak_tracks_in_roi, tracks_in_roi)
                peak_unique_visitors_visible = max(peak_unique_visitors_visible, len(frame_unique_visitors))
                peak_unique_visitors_in_roi = max(peak_unique_visitors_in_roi, len(frame_unique_visitors_in_roi))
                for person_type, visitor_keys in frame_unique_visitors_by_person_type.items():
                    peak_unique_visitors_by_person_type_visible[person_type] = max(
                        peak_unique_visitors_by_person_type_visible[person_type],
                        len(visitor_keys),
                    )
                for person_type, visitor_keys in frame_unique_visitors_in_roi_by_person_type.items():
                    peak_unique_visitors_by_person_type_in_roi[person_type] = max(
                        peak_unique_visitors_by_person_type_in_roi[person_type],
                        len(visitor_keys),
                    )
                processed_frames += 1
                if processed_frames % 30 == 0:
                    _print_progress(processed_frames, total_frames_estimated, time.time() - start_time)

                if args.max_frames > 0 and processed_frames >= args.max_frames:
                    break

        elapsed = time.time() - start_time
        unique_visitors_by_person_type = {"CUSTOMER": 0, "EMPLOYEE": 0, "UNKNOWN": 0}
        for visitor_profile in visitor_profiles.values():
            unique_visitors_by_person_type[_person_type_bucket(visitor_profile.get("person_type"))] += 1

        active_unique_visitors_last_frame = len(last_frame_unique_visitors)
        active_unique_visitors_in_roi_last_frame = len(last_frame_unique_visitors_in_roi)
        active_unique_visitors_by_person_type_last_frame = {
            person_type: len(visitor_keys)
            for person_type, visitor_keys in last_frame_unique_visitors_by_person_type.items()
        }
        cumulative_unique_visitors_by_person_type = dict(unique_visitors_by_person_type)
        visitors_inside_roi_at_end = active_unique_visitors_in_roi_last_frame
        visitors_outside_roi_at_end = max(0, active_unique_visitors_last_frame - active_unique_visitors_in_roi_last_frame)
        unique_visitors_entered_roi = len(unique_event_visitors["enter_roi"])
        unique_visitors_exited_roi = len(unique_event_visitors["exit_roi"])
        repeat_entry_events = max(0, event_counts["enter_roi"] - unique_visitors_entered_roi)
        repeat_exit_events = max(0, event_counts["exit_roi"] - unique_visitors_exited_roi)

        summary = {
            "input_video": str(input_path),
            "model_label": model_label,
            "model_output_dir": str(model_output_dir),
            "output_video": str(video_path),
            "output_csv": str(csv_path),
            "tracker_backend": tracker_backend_runtime,
            "yolo_backend": active_backend,
            "weights": active_weights,
            "reid_match_threshold": float(os.getenv("REID_MATCH_THRESHOLD", "0.77")),
            "device": os.getenv("YOLOV5_DEVICE", "auto"),
            "face_recognition_enabled": bool(face_recognizer.enabled and face_recognizer.available),
            "face_recognition_reason": getattr(face_recognizer, "reason", ""),
            "source_fps": round(source_fps, 3),
            "output_fps": round(writer_fps, 3),
            "source_size": [source_width, source_height],
            "output_size": [frame_width, frame_height],
            "frames_processed": processed_frames,
            "frames_with_detections": frames_with_detections,
            "track_rows_written": csv_rows,
            "unique_visitors": peak_unique_visitors_visible,
            "unique_visitors_mode": "peak_visible",
            "cumulative_unique_visitors": len(seen_visitor_keys),
            "unique_track_ids": len(seen_track_ids),
            "visitor_summary": {
                "total_enter_events": event_counts["enter_roi"],
                "total_exit_events": event_counts["exit_roi"],
                "unique_visitors_detected": peak_unique_visitors_visible,
                "unique_visitors_detected_mode": "peak_visible",
                "cumulative_unique_visitors_detected": len(seen_visitor_keys),
                "active_unique_visitors_last_frame": active_unique_visitors_last_frame,
                "active_unique_visitors_in_roi_last_frame": active_unique_visitors_in_roi_last_frame,
                "unique_visitors_entered_roi": unique_visitors_entered_roi,
                "unique_visitors_exited_roi": unique_visitors_exited_roi,
                "repeat_entry_events": repeat_entry_events,
                "repeat_exit_events": repeat_exit_events,
                "unique_visitors_by_person_type": peak_unique_visitors_by_person_type_visible,
                "unique_visitors_by_person_type_mode": "peak_visible",
                "cumulative_unique_visitors_by_person_type": cumulative_unique_visitors_by_person_type,
                "active_unique_visitors_by_person_type_last_frame": active_unique_visitors_by_person_type_last_frame,
                "event_counts_by_person_type": event_counts_by_person_type,
                "visitors_inside_roi_at_end": visitors_inside_roi_at_end,
                "visitors_outside_roi_at_end": visitors_outside_roi_at_end,
                "peak_concurrent_tracks": peak_concurrent_tracks,
                "peak_tracks_in_roi": peak_tracks_in_roi,
                "peak_unique_visitors_visible": peak_unique_visitors_visible,
                "peak_unique_visitors_in_roi": peak_unique_visitors_in_roi,
                "peak_unique_visitors_by_person_type_visible": peak_unique_visitors_by_person_type_visible,
                "peak_unique_visitors_by_person_type_in_roi": peak_unique_visitors_by_person_type_in_roi,
            },
            "roi": roi,
            "duration_seconds": round(elapsed, 3),
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        print(f"[done] frames  : {processed_frames}")
        print(f"[done] rows    : {csv_rows}")
        print(f"[done] enter   : {event_counts['enter_roi']}")
        print(f"[done] exit    : {event_counts['exit_roi']}")
        print(f"[done] peak    : {peak_unique_visitors_visible}")
        print(f"[done] unique  : {len(seen_visitor_keys)} cumulative")
        print(f"[done] summary : {summary_path}")
        return 0
    finally:
        capture.release()
        try:
            writer.release()
        except UnboundLocalError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
