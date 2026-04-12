"""Employee face recognition utilities for the edge worker."""
from dataclasses import dataclass
import time
from typing import Any, Dict, List, Optional

import numpy as np

from .config import (
    FACE_RECOGNITION_ENABLED,
    INSIGHTFACE_DET_SIZE,
    INSIGHTFACE_MODEL_NAME,
    INSIGHTFACE_PROVIDERS,
    EMPLOYEE_MATCH_THRESHOLD,
    EMPLOYEE_REGISTRY_REFRESH_SECONDS,
    FACE_RECHECK_SECONDS,
    FACE_DETECTION_FRAME_INTERVAL,
    FACE_UNKNOWN_TIMEOUT,
)
from .logger import get_logger

log = get_logger("face")

try:
    from insightface.app import FaceAnalysis

    INSIGHTFACE_AVAILABLE = True
    _IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - optional dependency path
    FaceAnalysis = None
    INSIGHTFACE_AVAILABLE = False
    _IMPORT_ERROR = str(exc)


@dataclass
class TrackClassification:
    person_type: str = "UNKNOWN"
    employee_id: Optional[int] = None
    employee_code: Optional[str] = None
    employee_name: Optional[str] = None
    match_score: Optional[float] = None
    recognition_source: str = "insightface"
    first_seen_at: float = 0.0
    last_checked_at: float = 0.0
    face_seen: bool = False
    stable: bool = False


def _normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(embedding)
    if norm <= 0:
        return embedding
    return embedding / norm


class EmployeeFaceRecognizer:
    """Classify tracked people as EMPLOYEE or CUSTOMER using face embeddings."""

    def __init__(self):
        self.enabled = FACE_RECOGNITION_ENABLED
        self.available = False
        self.reason = ""
        self._app = None
        self._track_states: Dict[int, TrackClassification] = {}
        self._employee_registry: List[Dict[str, Any]] = []
        self._employee_matrix: Optional[np.ndarray] = None  # (N, D) stacked embeddings
        self._last_registry_refresh = 0.0
        # Batch face detection cache: populated once per frame
        self._frame_faces: Optional[list] = None
        self._frame_id: Optional[int] = None
        self._last_detected_frame_id: Optional[int] = None

        if not self.enabled:
            self.reason = "disabled by config"
            return

        if not INSIGHTFACE_AVAILABLE:
            self.reason = _IMPORT_ERROR or "InsightFace unavailable"
            log.warning("Recognition disabled: %s", self.reason)
            return

        try:
            self._app = FaceAnalysis(
                name=INSIGHTFACE_MODEL_NAME,
                providers=INSIGHTFACE_PROVIDERS,
            )
            self._app.prepare(
                ctx_id=-1,
                det_size=(INSIGHTFACE_DET_SIZE, INSIGHTFACE_DET_SIZE),
            )
            self.available = True
            log.info("InsightFace initialized for employee recognition")
        except Exception as exc:  # pragma: no cover - depends on runtime
            self.reason = str(exc)
            log.error("Failed to initialize InsightFace: %s", self.reason)

    def refresh_registry(self, fetch_fn, token: Optional[str], force: bool = False) -> None:
        """Refresh employee embeddings from backend."""
        now = time.time()
        if not force and now - self._last_registry_refresh < EMPLOYEE_REGISTRY_REFRESH_SECONDS:
            return

        payload = fetch_fn(token)
        items = payload.get("items", []) if isinstance(payload, dict) else []
        registry: List[Dict[str, Any]] = []
        for item in items:
            embedding = item.get("face_embedding")
            if not embedding:
                continue
            emb = _normalize_embedding(np.asarray(embedding, dtype=np.float32))
            registry.append(
                {
                    "employee_id": item.get("employee_id"),
                    "employee_code": item.get("employee_code"),
                    "employee_name": item.get("full_name"),
                    "embedding": emb,
                }
            )

        self._employee_registry = registry
        # Pre-build matrix for vectorized matching
        if registry:
            self._employee_matrix = np.stack(
                [emp["embedding"] for emp in registry], axis=0
            )
        else:
            self._employee_matrix = None
        self._last_registry_refresh = now
        log.info("Loaded %d employee face embeddings", len(registry))

    def reset_daily(self) -> None:
        """Reset active track classifications on date rollover."""
        self._track_states = {}
        self._frame_faces = None
        self._frame_id = None
        self._last_detected_frame_id = None

    def cleanup(self, active_track_ids: List[int]) -> None:
        stale_ids = [tid for tid in self._track_states if tid not in active_track_ids]
        for tid in stale_ids:
            del self._track_states[tid]

    @property
    def registry_size(self) -> int:
        return len(self._employee_registry)

    def needs_detection(self, active_track_ids: List[int]) -> bool:
        """Return True when at least one active track still needs face classification."""
        if not self.enabled or not self.available or not self._employee_registry or not active_track_ids:
            return False

        for track_id in active_track_ids:
            state = self._track_states.get(track_id)
            if state is None or not state.stable:
                return True
        return False

    def detect_faces_batch(self, frame: np.ndarray, frame_id: int = 0) -> None:
        """Run InsightFace once on full frame and cache results.

        Call this once per frame BEFORE iterating over tracks with classify_track.
        """
        if not self.enabled or not self.available or self._app is None:
            self._frame_faces = None
            self._frame_id = frame_id
            return

        if self._frame_id == frame_id and self._frame_faces is not None:
            return  # Already detected for this frame

        if (
            self._last_detected_frame_id is not None
            and frame_id - self._last_detected_frame_id < FACE_DETECTION_FRAME_INTERVAL
        ):
            self._frame_faces = None
            self._frame_id = frame_id
            return

        self._frame_id = frame_id
        try:
            self._frame_faces = self._app.get(frame)
            self._last_detected_frame_id = frame_id
        except Exception:
            self._frame_faces = None

    def classify_track(self, frame: np.ndarray, track_id: int, bbox) -> Dict[str, Any]:
        """Classify a track using pre-computed batch face detections."""
        now = time.time()
        state = self._track_states.get(track_id)
        if state is None:
            state = TrackClassification(first_seen_at=now, last_checked_at=0.0)
            self._track_states[track_id] = state

        if not self.enabled or not self.available:
            state.person_type = "CUSTOMER"
            state.recognition_source = "disabled"
            state.stable = True
            return self._serialize(state)

        if not self._employee_registry:
            state.person_type = "CUSTOMER"
            state.recognition_source = "no_registry"
            state.stable = True
            return self._serialize(state)

        if state.stable:
            return self._serialize(state)

        if now - state.last_checked_at < FACE_RECHECK_SECONDS:
            if now - state.first_seen_at >= FACE_UNKNOWN_TIMEOUT:
                state.person_type = "CUSTOMER"
                state.recognition_source = "timeout_fallback"
                state.stable = True
            return self._serialize(state)

        state.last_checked_at = now
        embedding = self._extract_face_embedding(frame, bbox)
        if embedding is None:
            if now - state.first_seen_at >= FACE_UNKNOWN_TIMEOUT:
                state.person_type = "CUSTOMER"
                state.recognition_source = "timeout_fallback"
                state.stable = True
            return self._serialize(state)

        state.face_seen = True
        best_match = self._match_employee(embedding)
        if best_match and best_match["score"] >= EMPLOYEE_MATCH_THRESHOLD:
            state.person_type = "EMPLOYEE"
            state.employee_id = best_match["employee_id"]
            state.employee_code = best_match["employee_code"]
            state.employee_name = best_match["employee_name"]
            state.match_score = best_match["score"]
            state.recognition_source = "insightface"
            state.stable = True
        else:
            state.person_type = "CUSTOMER"
            state.match_score = best_match["score"] if best_match else None
            state.recognition_source = "insightface"
            state.stable = True

        return self._serialize(state)

    def _serialize(self, state: TrackClassification) -> Dict[str, Any]:
        return {
            "person_type": state.person_type,
            "employee_id": state.employee_id,
            "employee_code": state.employee_code,
            "employee_name": state.employee_name,
            "match_score": state.match_score,
            "recognition_source": state.recognition_source,
            "face_seen": state.face_seen,
            "stable": state.stable,
        }

    def _extract_face_embedding(self, frame: np.ndarray, bbox) -> Optional[np.ndarray]:
        """Match a pre-detected face from batch cache to the given track bbox using IoU."""
        if self._frame_faces is None or len(self._frame_faces) == 0:
            return None

        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        best_face = None
        best_iou = 0.1  # minimum IoU threshold to consider a match

        for face in self._frame_faces:
            fb = getattr(face, "bbox", None)
            if fb is None or len(fb) < 4:
                continue
            fx1, fy1, fx2, fy2 = float(fb[0]), float(fb[1]), float(fb[2]), float(fb[3])

            # Check if face center is inside track bbox (fast pre-filter)
            fcx = (fx1 + fx2) / 2.0
            fcy = (fy1 + fy2) / 2.0
            if fcx < x1 or fcx > x2 or fcy < y1 or fcy > y2:
                continue

            # Compute IoU between face bbox and track bbox
            inter_x1 = max(x1, fx1)
            inter_y1 = max(y1, fy1)
            inter_x2 = min(x2, fx2)
            inter_y2 = min(y2, fy2)
            inter_area = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)
            face_area = (fx2 - fx1) * (fy2 - fy1)
            if face_area <= 0:
                continue
            # Use face coverage ratio (how much of face is inside track)
            iou = inter_area / face_area
            if iou > best_iou:
                best_iou = iou
                best_face = face

        if best_face is None:
            return None
        embedding = getattr(best_face, "embedding", None)
        if embedding is None or len(embedding) == 0:
            return None
        return _normalize_embedding(np.asarray(embedding, dtype=np.float32))

    def _match_employee(self, embedding: np.ndarray) -> Optional[Dict[str, Any]]:
        if self._employee_matrix is None or len(self._employee_registry) == 0:
            return None

        # Vectorized cosine similarity: (N,D) @ (D,) -> (N,)
        scores = self._employee_matrix @ embedding
        max_idx = int(np.argmax(scores))
        best = self._employee_registry[max_idx]

        return {
            "employee_id": best["employee_id"],
            "employee_code": best["employee_code"],
            "employee_name": best["employee_name"],
            "score": float(scores[max_idx]),
        }
