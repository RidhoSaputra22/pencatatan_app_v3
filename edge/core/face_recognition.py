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
    FACE_UNKNOWN_TIMEOUT,
)

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
        self._last_registry_refresh = 0.0

        if not self.enabled:
            self.reason = "disabled by config"
            return

        if not INSIGHTFACE_AVAILABLE:
            self.reason = _IMPORT_ERROR or "InsightFace unavailable"
            print(f"[face] Recognition disabled: {self.reason}")
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
            print("[face] InsightFace initialized for employee recognition")
        except Exception as exc:  # pragma: no cover - depends on runtime
            self.reason = str(exc)
            print(f"[face] Failed to initialize InsightFace: {self.reason}")

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
        self._last_registry_refresh = now
        print(f"[face] Loaded {len(registry)} employee face embeddings")

    def reset_daily(self) -> None:
        """Reset active track classifications on date rollover."""
        self._track_states = {}

    def cleanup(self, active_track_ids: List[int]) -> None:
        stale_ids = [tid for tid in self._track_states if tid not in active_track_ids]
        for tid in stale_ids:
            del self._track_states[tid]

    @property
    def registry_size(self) -> int:
        return len(self._employee_registry)

    def classify_track(self, frame: np.ndarray, track_id: int, bbox) -> Dict[str, Any]:
        """Classify a track. Returns UNKNOWN until a face is matched or timeout fallback occurs."""
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
        if self._app is None:
            return None

        x1, y1, x2, y2 = bbox
        frame_h, frame_w = frame.shape[:2]
        w = max(1, int(x2 - x1))
        h = max(1, int(y2 - y1))
        pad_x = int(w * 0.15)
        pad_y = int(h * 0.15)

        crop_x1 = max(0, int(x1) - pad_x)
        crop_y1 = max(0, int(y1) - pad_y)
        crop_x2 = min(frame_w, int(x2) + pad_x)
        crop_y2 = min(frame_h, int(y2) + pad_y)
        if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
            return None

        crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
        if crop.size == 0:
            return None

        faces = self._app.get(crop)
        if not faces:
            return None

        face = max(
            faces,
            key=lambda item: float(getattr(item, "det_score", 0.0)),
        )
        embedding = getattr(face, "embedding", None)
        if embedding is None or len(embedding) == 0:
            return None
        return _normalize_embedding(np.asarray(embedding, dtype=np.float32))

    def _match_employee(self, embedding: np.ndarray) -> Optional[Dict[str, Any]]:
        best_match = None
        best_score = -1.0
        for employee in self._employee_registry:
            score = float(np.dot(embedding, employee["embedding"]))
            if score > best_score:
                best_score = score
                best_match = employee

        if best_match is None:
            return None

        return {
            "employee_id": best_match["employee_id"],
            "employee_code": best_match["employee_code"],
            "employee_name": best_match["employee_name"],
            "score": best_score,
        }
