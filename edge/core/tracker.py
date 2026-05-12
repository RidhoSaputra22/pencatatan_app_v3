"""
DeepSORT Tracker dengan ReID embedding
Lebih stabil daripada CentroidTracker karena menggunakan:
1. Kalman Filter untuk motion prediction
2. Deep appearance features (ReID) untuk re-identification
3. Hungarian algorithm untuk optimal assignment
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
import numpy as np

from .logger import get_logger

log = get_logger("tracker")

try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    DEEPSORT_AVAILABLE = True
except ImportError:
    DEEPSORT_AVAILABLE = False
    import logging as _logging
    _logging.getLogger("edge.tracker").warning(
        "deep-sort-realtime not installed. Using fallback CentroidTracker."
    )

try:
    from scipy.optimize import linear_sum_assignment
except ImportError:  # pragma: no cover - scipy is optional at runtime
    linear_sum_assignment = None


def _disable_mkldnn_backend() -> bool:
    """Disable MKLDNN as a workaround for some CPU primitive creation failures."""
    try:
        import torch
    except ImportError:
        return False

    if not getattr(torch.backends, "mkldnn", None):
        return False
    if not torch.backends.mkldnn.enabled:
        return False

    torch.backends.mkldnn.enabled = False
    log.warning("MKLDNN disabled for DeepSORT embedder compatibility")
    return True


@dataclass
class Track:
    """Track object untuk menyimpan informasi tracking"""
    tid: int
    centroid: Tuple[float, float]
    bbox: Tuple[float, float, float, float]  # x1,y1,x2,y2
    embedding: Optional[np.ndarray] = None  # ReID embedding
    confidence: float = 0.0
    disappeared: int = 0
    hits: int = 1
    age: int = 1
    in_roi: bool = False
    is_new: bool = True
    last_direction: Optional[str] = None
    velocity: Tuple[float, float] = (0.0, 0.0)


def _bbox_centroid(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((float(x1) + float(x2)) / 2.0, (float(y1) + float(y2)) / 2.0)


def _bbox_bottom_center(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    x1, _, x2, y2 = bbox
    return ((float(x1) + float(x2)) / 2.0, float(y2))


def _bbox_size(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return max(1.0, float(x2) - float(x1)), max(1.0, float(y2) - float(y1))


def _bbox_area(bbox: Tuple[float, float, float, float]) -> float:
    width, height = _bbox_size(bbox)
    return width * height


def _bbox_iou(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(float(ax1), float(bx1))
    inter_y1 = max(float(ay1), float(by1))
    inter_x2 = min(float(ax2), float(bx2))
    inter_y2 = min(float(ay2), float(by2))
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    union = _bbox_area(box_a) + _bbox_area(box_b) - inter_area
    return inter_area / union if union > 0 else 0.0


def _point_distance(
    point_a: Tuple[float, float],
    point_b: Tuple[float, float],
) -> float:
    return float(np.linalg.norm(np.array(point_a, dtype=np.float32) - np.array(point_b, dtype=np.float32)))


def _blend_bbox(
    old_bbox: Tuple[float, float, float, float],
    new_bbox: Tuple[float, float, float, float],
    new_weight: float,
) -> Tuple[float, float, float, float]:
    old_arr = np.array(old_bbox, dtype=np.float32)
    new_arr = np.array(new_bbox, dtype=np.float32)
    blended = old_arr * (1.0 - new_weight) + new_arr * new_weight
    return tuple(float(v) for v in blended)


def _predict_bbox(track: Track) -> Tuple[float, float, float, float]:
    lookahead = min(int(track.disappeared or 0) + 1, 8)
    dx = float(track.velocity[0]) * lookahead
    dy = float(track.velocity[1]) * lookahead
    x1, y1, x2, y2 = track.bbox
    return (float(x1) + dx, float(y1) + dy, float(x2) + dx, float(y2) + dy)


def _linear_assignment(
    cost_matrix: np.ndarray,
    max_cost: float,
) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    if cost_matrix.size == 0:
        rows = list(range(cost_matrix.shape[0])) if cost_matrix.ndim == 2 else []
        cols = list(range(cost_matrix.shape[1])) if cost_matrix.ndim == 2 else []
        return [], rows, cols

    row_count, col_count = cost_matrix.shape
    unmatched_rows = set(range(row_count))
    unmatched_cols = set(range(col_count))
    matches: List[Tuple[int, int]] = []

    if linear_sum_assignment is not None:
        safe_costs = np.where(np.isfinite(cost_matrix), cost_matrix, max_cost + 1.0)
        row_indices, col_indices = linear_sum_assignment(safe_costs)
        for row_idx, col_idx in zip(row_indices, col_indices):
            if safe_costs[row_idx, col_idx] > max_cost:
                continue
            matches.append((int(row_idx), int(col_idx)))
            unmatched_rows.discard(int(row_idx))
            unmatched_cols.discard(int(col_idx))
        return matches, sorted(unmatched_rows), sorted(unmatched_cols)

    candidates = [
        (float(cost_matrix[row_idx, col_idx]), row_idx, col_idx)
        for row_idx in range(row_count)
        for col_idx in range(col_count)
        if np.isfinite(cost_matrix[row_idx, col_idx]) and cost_matrix[row_idx, col_idx] <= max_cost
    ]
    candidates.sort(key=lambda item: item[0])
    for _, row_idx, col_idx in candidates:
        if row_idx not in unmatched_rows or col_idx not in unmatched_cols:
            continue
        matches.append((row_idx, col_idx))
        unmatched_rows.remove(row_idx)
        unmatched_cols.remove(col_idx)

    return matches, sorted(unmatched_rows), sorted(unmatched_cols)


class DeepSORTTracker:
    """
    DeepSORT Tracker dengan ReID untuk visitor identification.
    Menggunakan deep appearance features untuk tracking yang lebih stabil.
    """
    
    def __init__(self, max_age: int = 30, n_init: int = 3, max_cosine_distance: float = 0.3):
        """
        Initialize DeepSORT tracker.
        
        Args:
            max_age: Maximum frames to keep track alive without detection
            n_init: Minimum detections before track is confirmed
            max_cosine_distance: Maximum cosine distance for appearance matching
        """
        self.max_age = max_age
        self.n_init = n_init
        self.max_cosine_distance = max_cosine_distance
        self.tracker = None
        self._fallback_tracker = CentroidTrackerFallback(max_disappeared=max_age)
        self.tracks: Dict[int, Track] = self._fallback_tracker.tracks
        self.using_fallback = True

        if not DEEPSORT_AVAILABLE:
            log.warning("Using fallback CentroidTracker")
            return

        try:
            self.tracker = self._create_deepsort_tracker()
        except RuntimeError as exc:
            error_message = str(exc)
            if "could not create a primitive" in error_message.lower() and _disable_mkldnn_backend():
                try:
                    self.tracker = self._create_deepsort_tracker()
                except Exception as retry_exc:
                    self._activate_fallback(f"DeepSORT retry failed after disabling MKLDNN: {retry_exc}")
            else:
                self._activate_fallback(f"DeepSORT init failed: {exc}")
        except Exception as exc:
            self._activate_fallback(f"DeepSORT init failed: {exc}")

        if self.tracker is not None:
            self.tracks = {}
            self.using_fallback = False
            log.info("DeepSORT initialized (max_age=%d, n_init=%d)", max_age, n_init)

    def _create_deepsort_tracker(self):
        return DeepSort(
            max_iou_distance=0.7,
            max_age=self.max_age,
            n_init=self.n_init,
            nms_max_overlap=0.85,
            max_cosine_distance=self.max_cosine_distance,
            embedder="mobilenet",
            half=False,
            embedder_gpu=False,
        )

    def _activate_fallback(self, reason: str):
        self.tracker = None
        self.using_fallback = True
        self.tracks = self._fallback_tracker.tracks
        log.warning("%s", reason)
        log.warning("Falling back to CentroidTracker")
    
    def update(self, frame: np.ndarray, detections: List[Tuple[float, float, float, float, float]]) -> Dict[int, Track]:
        """
        Update tracker dengan deteksi baru.
        
        Args:
            frame: Current video frame (untuk ReID feature extraction)
            detections: List of (x1, y1, x2, y2, confidence)
        
        Returns:
            Dict of track_id -> Track
        """
        if not DEEPSORT_AVAILABLE or self.tracker is None:
            # Fallback to centroid tracker
            bboxes = [(d[0], d[1], d[2], d[3]) for d in detections]
            self.tracks = self._fallback_tracker.update(bboxes)
            return self.tracks
        
        if len(detections) == 0:
            # Keep DeepSORT/Kalman predictions alive during short detector misses.
            tracks = self.tracker.update_tracks([], frame=frame)
            self._update_tracks_from_deepsort(tracks)
            return self.tracks
        
        # Format detections for DeepSORT: [[x1, y1, w, h], conf, class]
        ds_detections = []
        for det in detections:
            x1, y1, x2, y2, conf = det
            w = x2 - x1
            h = y2 - y1
            ds_detections.append(([x1, y1, w, h], conf, 'person'))

        # Update DeepSORT
        try:
            tracks = self.tracker.update_tracks(ds_detections, frame=frame)
        except Exception as exc:
            self._activate_fallback(f"DeepSORT update failed: {exc}")
            bboxes = [(d[0], d[1], d[2], d[3]) for d in detections]
            self.tracks = self._fallback_tracker.update(bboxes)
            return self.tracks
        
        # Convert to our Track format
        self._update_tracks_from_deepsort(tracks)
        
        return self.tracks
    
    def _update_tracks_from_deepsort(self, ds_tracks=None):
        """Convert DeepSORT tracks to our Track format"""
        if ds_tracks is None:
            ds_tracks = []
        
        active_ids = set()
        
        for track in ds_tracks:
            if not track.is_confirmed():
                continue
            
            tid = track.track_id
            
            # Get bounding box
            ltrb = track.to_ltrb(orig=True, orig_strict=False)  # [x1, y1, x2, y2]
            if ltrb is None:
                continue
            active_ids.add(tid)
            bbox = (float(ltrb[0]), float(ltrb[1]), float(ltrb[2]), float(ltrb[3]))
            
            # Calculate centroid
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            
            # Get embedding if available
            embedding = None
            if hasattr(track, 'get_feature') and callable(track.get_feature):
                try:
                    embedding = track.get_feature()
                except (IndexError, TypeError):
                    embedding = None
            elif hasattr(track, 'features') and track.features is not None and len(track.features) > 0:
                embedding = np.array(track.features[-1])

            det_conf = None
            if hasattr(track, 'get_det_conf') and callable(track.get_det_conf):
                det_conf = track.get_det_conf()
            time_since_update = int(getattr(track, "time_since_update", 0) or 0)
            hits = int(getattr(track, "hits", 1) or 1)
            age = int(getattr(track, "age", hits) or hits)
            
            # Update or create track
            if tid in self.tracks:
                self.tracks[tid].centroid = (cx, cy)
                self.tracks[tid].bbox = bbox
                if embedding is not None:
                    self.tracks[tid].embedding = embedding
                if det_conf is not None:
                    self.tracks[tid].confidence = float(det_conf)
                self.tracks[tid].disappeared = time_since_update
                self.tracks[tid].hits = hits
                self.tracks[tid].age = age
                self.tracks[tid].is_new = False
            else:
                self.tracks[tid] = Track(
                    tid=tid,
                    centroid=(cx, cy),
                    bbox=bbox,
                    embedding=embedding,
                    confidence=float(det_conf) if det_conf is not None else 0.0,
                    disappeared=time_since_update,
                    hits=hits,
                    age=age,
                    is_new=True
                )
        
        # Remove tracks that are no longer active
        to_remove = [tid for tid in self.tracks if tid not in active_ids]
        for tid in to_remove:
            del self.tracks[tid]
    
    def get_embedding(self, track_id: int) -> Optional[np.ndarray]:
        """Get embedding for a specific track"""
        if track_id in self.tracks:
            return self.tracks[track_id].embedding
        return None


class ByteTrackTracker:
    """ByteTrack-style tracker using high/low confidence association."""

    def __init__(
        self,
        max_age: int = 30,
        n_init: int = 3,
        high_thresh: float = 0.45,
        low_thresh: float = 0.1,
        match_thresh: float = 0.8,
        new_track_thresh: Optional[float] = None,
        min_box_area: float = 10.0,
    ):
        self.max_age = max(0, int(max_age))
        self.n_init = max(1, int(n_init))
        self.high_thresh = min(1.0, max(0.0, float(high_thresh)))
        self.low_thresh = min(self.high_thresh, max(0.0, float(low_thresh)))
        self.match_thresh = min(1.0, max(0.0, float(match_thresh)))
        self.new_track_thresh = (
            self.high_thresh
            if new_track_thresh is None
            else min(1.0, max(0.0, float(new_track_thresh)))
        )
        self.min_box_area = max(0.0, float(min_box_area))
        self.next_id = 1
        self.tracks: Dict[int, Track] = {}
        log.info(
            (
                "ByteTrack initialized (max_age=%d, n_init=%d, high=%.2f, "
                "low=%.2f, match=%.2f, new=%.2f)"
            ),
            self.max_age,
            self.n_init,
            self.high_thresh,
            self.low_thresh,
            self.match_thresh,
            self.new_track_thresh,
        )

    def _valid_detection(self, detection: Tuple[float, float, float, float, float]) -> bool:
        bbox = detection[:4]
        return _bbox_area(bbox) >= self.min_box_area and float(detection[4]) >= self.low_thresh

    def _adaptive_max_distance(
        self,
        track: Track,
        bbox: Tuple[float, float, float, float],
    ) -> float:
        track_w, track_h = _bbox_size(track.bbox)
        det_w, det_h = _bbox_size(bbox)
        object_scale = max(track_w, track_h, det_w, det_h)
        base = max(48.0, object_scale * 0.55)
        gap_allowance = min(int(track.disappeared or 0), 12) * max(10.0, base * 0.14)
        return min(base + gap_allowance, max(280.0, base * 3.5))

    def _association_cost(
        self,
        track: Track,
        detection: Tuple[float, float, float, float, float],
    ) -> float:
        bbox = detection[:4]
        predicted_bbox = _predict_bbox(track)
        iou = max(_bbox_iou(track.bbox, bbox), _bbox_iou(predicted_bbox, bbox))

        track_w, track_h = _bbox_size(track.bbox)
        det_w, det_h = _bbox_size(bbox)
        track_scale = max(track_w, track_h)
        det_scale = max(det_w, det_h)
        scale_ratio = max(track_scale / det_scale, det_scale / track_scale)
        if scale_ratio > 3.8 and iou < 0.04:
            return float("inf")

        max_distance = self._adaptive_max_distance(track, bbox)
        center_dist = _point_distance(_bbox_centroid(predicted_bbox), _bbox_centroid(bbox))
        feet_dist = _point_distance(_bbox_bottom_center(predicted_bbox), _bbox_bottom_center(bbox))
        best_motion_dist = min(center_dist, (center_dist * 0.65) + (feet_dist * 0.35))
        if best_motion_dist > max_distance and iou < 0.03:
            return float("inf")

        motion_score = max(0.0, 1.0 - (best_motion_dist / max(max_distance, 1.0))) * 0.12
        confidence_bonus = min(0.05, max(0.0, float(detection[4]) - self.high_thresh) * 0.10)
        association_score = min(1.0, iou + motion_score + confidence_bonus)
        return 1.0 - association_score

    def _match_tracks(
        self,
        track_ids: List[int],
        detections: List[Tuple[float, float, float, float, float]],
        max_cost: Optional[float] = None,
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        if not track_ids or not detections:
            return [], list(track_ids), list(range(len(detections)))

        threshold = self.match_thresh if max_cost is None else max_cost
        cost_matrix = np.full((len(track_ids), len(detections)), np.inf, dtype=np.float32)
        for row_idx, track_id in enumerate(track_ids):
            track = self.tracks[track_id]
            for col_idx, detection in enumerate(detections):
                cost_matrix[row_idx, col_idx] = self._association_cost(track, detection)

        match_positions, unmatched_rows, unmatched_cols = _linear_assignment(cost_matrix, threshold)
        matches = [(track_ids[row_idx], col_idx) for row_idx, col_idx in match_positions]
        unmatched_track_ids = [track_ids[row_idx] for row_idx in unmatched_rows]
        return matches, unmatched_track_ids, unmatched_cols

    def _register(self, detection: Tuple[float, float, float, float, float]) -> None:
        bbox = tuple(float(v) for v in detection[:4])
        tid = self.next_id
        self.next_id += 1
        self.tracks[tid] = Track(
            tid=tid,
            centroid=_bbox_centroid(bbox),
            bbox=bbox,
            confidence=float(detection[4]),
        )

    def _update_track(self, track: Track, detection: Tuple[float, float, float, float, float]) -> None:
        bbox = tuple(float(v) for v in detection[:4])
        centroid = _bbox_centroid(bbox)
        gap = max(1, int(track.disappeared or 0) + 1)
        observed_velocity = (
            (float(centroid[0]) - float(track.centroid[0])) / float(gap),
            (float(centroid[1]) - float(track.centroid[1])) / float(gap),
        )
        bbox_w, bbox_h = _bbox_size(bbox)
        max_speed = max(10.0, min(100.0, max(bbox_w, bbox_h) * 0.42))
        velocity = (
            (float(track.velocity[0]) * 0.50) + (observed_velocity[0] * 0.50),
            (float(track.velocity[1]) * 0.50) + (observed_velocity[1] * 0.50),
        )
        speed = float(np.linalg.norm(np.array(velocity, dtype=np.float32)))
        if speed > max_speed:
            scale = max_speed / speed
            velocity = (velocity[0] * scale, velocity[1] * scale)

        track.velocity = velocity
        track.centroid = centroid
        track.bbox = _blend_bbox(track.bbox, bbox, 0.90 if gap > 1 else 0.78)
        track.confidence = float(detection[4])
        track.disappeared = 0
        track.hits += 1
        track.age += 1
        track.is_new = track.hits < self.n_init

    def _mark_missed(self, track_id: int) -> bool:
        track = self.tracks[track_id]
        track.disappeared += 1
        track.age += 1
        track.velocity = (float(track.velocity[0]) * 0.88, float(track.velocity[1]) * 0.88)
        return track.disappeared > self.max_age

    def _should_register_detection(self, detection: Tuple[float, float, float, float, float]) -> bool:
        bbox = detection[:4]
        centroid = _bbox_centroid(bbox)
        det_scale = max(_bbox_size(bbox))
        for track in self.tracks.values():
            compare_bbox = _predict_bbox(track) if int(track.disappeared or 0) > 0 else track.bbox
            compare_centroid = _bbox_centroid(compare_bbox)
            iou = _bbox_iou(compare_bbox, bbox)
            distance = _point_distance(compare_centroid, centroid)
            track_scale = max(_bbox_size(compare_bbox))
            duplicate_distance = max(24.0, min(140.0, max(track_scale, det_scale) * 0.32))
            if iou >= 0.35 or (iou >= 0.08 and distance <= duplicate_distance):
                return False
        return True

    def update(
        self,
        detections: List[Tuple[float, float, float, float, float]],
    ) -> Dict[int, Track]:
        valid_detections = [det for det in detections if self._valid_detection(det)]
        high_detections = [det for det in valid_detections if float(det[4]) >= self.high_thresh]
        low_detections = [
            det
            for det in valid_detections
            if self.low_thresh <= float(det[4]) < self.high_thresh
        ]

        if not self.tracks:
            for detection in high_detections:
                if float(detection[4]) >= self.new_track_thresh:
                    self._register(detection)
            return self.tracks

        track_ids = list(self.tracks.keys())

        high_matches, unmatched_track_ids, unmatched_high_indices = self._match_tracks(
            track_ids,
            high_detections,
        )
        for track_id, det_idx in high_matches:
            self._update_track(self.tracks[track_id], high_detections[det_idx])

        second_cost = min(0.95, self.match_thresh + 0.08)
        low_matches, unmatched_track_ids, _ = self._match_tracks(
            unmatched_track_ids,
            low_detections,
            max_cost=second_cost,
        )
        for track_id, det_idx in low_matches:
            self._update_track(self.tracks[track_id], low_detections[det_idx])

        to_remove = []
        for track_id in unmatched_track_ids:
            if self._mark_missed(track_id):
                to_remove.append(track_id)
        for track_id in to_remove:
            del self.tracks[track_id]

        for det_idx in unmatched_high_indices:
            detection = high_detections[det_idx]
            if float(detection[4]) < self.new_track_thresh:
                continue
            if self._should_register_detection(detection):
                self._register(detection)

        return self.tracks


class CentroidTrackerFallback:
    """Fallback centroid tracker jika DeepSORT tidak tersedia"""
    
    def __init__(self, max_disappeared: int = 30, max_distance: float = 80.0):
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.next_id = 1
        self.tracks: Dict[int, Track] = {}

    def _register(
        self,
        bbox: Tuple[float, float, float, float],
        centroid: Tuple[float, float],
    ) -> None:
        tid = self.next_id
        self.next_id += 1
        self.tracks[tid] = Track(tid=tid, centroid=centroid, bbox=bbox)

    def _predicted_centroid(self, track: Track) -> Tuple[float, float]:
        lookahead = min(int(track.disappeared or 0) + 1, 8)
        return (
            float(track.centroid[0]) + float(track.velocity[0]) * lookahead,
            float(track.centroid[1]) + float(track.velocity[1]) * lookahead,
        )

    def _predicted_bottom_center(self, track: Track) -> Tuple[float, float]:
        bottom_x, bottom_y = _bbox_bottom_center(track.bbox)
        lookahead = min(int(track.disappeared or 0) + 1, 8)
        return (
            bottom_x + float(track.velocity[0]) * lookahead,
            bottom_y + float(track.velocity[1]) * lookahead,
        )

    def _adaptive_max_distance(
        self,
        track: Track,
        bbox: Tuple[float, float, float, float],
    ) -> float:
        track_w, track_h = _bbox_size(track.bbox)
        det_w, det_h = _bbox_size(bbox)
        object_scale = max(track_w, track_h, det_w, det_h)
        base = max(float(self.max_distance), object_scale * 0.42)
        gap_allowance = min(int(track.disappeared or 0), 12) * max(8.0, base * 0.12)
        return min(base + gap_allowance, max(float(self.max_distance) * 3.0, 260.0))

    def _candidate_cost(
        self,
        track: Track,
        bbox: Tuple[float, float, float, float],
        centroid: Tuple[float, float],
    ) -> float:
        max_distance = self._adaptive_max_distance(track, bbox)
        center_dist = _point_distance(self._predicted_centroid(track), centroid)
        feet_dist = _point_distance(self._predicted_bottom_center(track), _bbox_bottom_center(bbox))
        iou = _bbox_iou(track.bbox, bbox)

        track_w, track_h = _bbox_size(track.bbox)
        det_w, det_h = _bbox_size(bbox)
        track_scale = max(track_w, track_h)
        det_scale = max(det_w, det_h)
        scale_ratio = max(track_scale / det_scale, det_scale / track_scale)
        if scale_ratio > 3.5 and iou < 0.05:
            return float("inf")

        best_motion_dist = min(center_dist, (center_dist * 0.7) + (feet_dist * 0.3))
        if best_motion_dist > max_distance and iou < 0.04:
            return float("inf")

        normalized_motion = best_motion_dist / max(max_distance, 1.0)
        gap_penalty = min(int(track.disappeared or 0), 10) * 0.015
        return normalized_motion - (iou * 0.75) + gap_penalty

    def _update_track(
        self,
        track: Track,
        bbox: Tuple[float, float, float, float],
        centroid: Tuple[float, float],
    ) -> None:
        gap = max(1, int(track.disappeared or 0) + 1)
        old_centroid = track.centroid
        observed_velocity = (
            (float(centroid[0]) - float(old_centroid[0])) / float(gap),
            (float(centroid[1]) - float(old_centroid[1])) / float(gap),
        )

        bbox_w, bbox_h = _bbox_size(bbox)
        max_speed = max(8.0, min(85.0, max(bbox_w, bbox_h) * 0.35))
        velocity = (
            (float(track.velocity[0]) * 0.55) + (observed_velocity[0] * 0.45),
            (float(track.velocity[1]) * 0.55) + (observed_velocity[1] * 0.45),
        )
        speed = float(np.linalg.norm(np.array(velocity, dtype=np.float32)))
        if speed > max_speed:
            scale = max_speed / speed
            velocity = (velocity[0] * scale, velocity[1] * scale)

        track.velocity = velocity
        track.centroid = centroid
        track.bbox = _blend_bbox(track.bbox, bbox, 0.82 if gap > 1 else 0.68)
        track.disappeared = 0
        track.hits += 1
        track.age += 1
        track.is_new = False

    def _mark_missed(self, track_id: int) -> bool:
        track = self.tracks[track_id]
        track.disappeared += 1
        track.age += 1
        track.velocity = (float(track.velocity[0]) * 0.86, float(track.velocity[1]) * 0.86)
        return track.disappeared > self.max_disappeared

    def _should_register_detection(
        self,
        bbox: Tuple[float, float, float, float],
        centroid: Tuple[float, float],
        used_tracks: set,
    ) -> bool:
        det_scale = max(_bbox_size(bbox))
        for tid, track in self.tracks.items():
            if tid in used_tracks:
                compare_bbox = track.bbox
                compare_point = track.centroid
            elif int(track.disappeared or 0) <= min(8, self.max_disappeared):
                compare_bbox = track.bbox
                compare_point = self._predicted_centroid(track)
            else:
                continue

            iou = _bbox_iou(compare_bbox, bbox)
            dist = _point_distance(compare_point, centroid)
            track_scale = max(_bbox_size(compare_bbox))
            suppression_distance = max(24.0, min(float(self.max_distance), max(track_scale, det_scale) * 0.30))
            if iou >= 0.30 or (iou >= 0.08 and dist <= suppression_distance):
                return False
        return True

    def update(self, detections: List[Tuple[float, float, float, float]]) -> Dict[int, Track]:
        """Update tracker with new detections"""
        if len(detections) == 0:
            to_del = []
            for tid in list(self.tracks.keys()):
                if self._mark_missed(tid):
                    to_del.append(tid)
            for tid in to_del:
                del self.tracks[tid]
            return self.tracks

        det_centroids = [_bbox_centroid(bbox) for bbox in detections]

        if len(self.tracks) == 0:
            for i, bbox in enumerate(detections):
                self._register(bbox, det_centroids[i])
            return self.tracks

        track_ids = list(self.tracks.keys())
        candidates = []
        for t_idx, tid in enumerate(track_ids):
            track = self.tracks[tid]
            for d_idx, bbox in enumerate(detections):
                cost = self._candidate_cost(track, bbox, det_centroids[d_idx])
                if np.isfinite(cost):
                    candidates.append((cost, t_idx, d_idx))
        candidates.sort(key=lambda item: item[0])

        used_tracks = set()
        used_dets = set()
        for _, t_idx, d_idx in candidates:
            tid = track_ids[t_idx]
            if tid in used_tracks or d_idx in used_dets:
                continue

            self._update_track(self.tracks[tid], detections[d_idx], det_centroids[d_idx])
            used_tracks.add(tid)
            used_dets.add(d_idx)

        to_del = []
        for tid in track_ids:
            if tid not in used_tracks:
                if self._mark_missed(tid):
                    to_del.append(tid)
        for tid in to_del:
            del self.tracks[tid]

        for i, bbox in enumerate(detections):
            if i in used_dets:
                continue
            if self._should_register_detection(bbox, det_centroids[i], used_tracks):
                self._register(bbox, det_centroids[i])

        return self.tracks


# Legacy alias for backward compatibility
CentroidTracker = CentroidTrackerFallback
