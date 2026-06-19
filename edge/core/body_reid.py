"""Tracker-agnostic body ReID helpers for visitor identity."""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from .config import (
    REID_CROP_PADDING_RATIO,
    REID_FRAME_INTERVAL,
    REID_MIN_CROP_HEIGHT,
    REID_MIN_CROP_WIDTH,
)
from .logger import get_logger

log = get_logger("body_reid")

try:
    from deep_sort_realtime.embedder.embedder_pytorch import MobileNetv2_Embedder

    DEEPSORT_EMBEDDER_AVAILABLE = True
    _IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - optional runtime path
    MobileNetv2_Embedder = None
    DEEPSORT_EMBEDDER_AVAILABLE = False
    _IMPORT_ERROR = str(exc)


@dataclass
class TrackEmbeddingState:
    embedding: Optional[np.ndarray] = None
    last_frame_id: int = -1_000_000
    last_extracted_at: float = 0.0
    backend: str = ""


def _normalize_embedding(embedding: Optional[np.ndarray]) -> Optional[np.ndarray]:
    if embedding is None:
        return None
    vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
    if vector.size == 0:
        return None
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        return None
    return vector / norm


class BodyReidentifier:
    """Extract person appearance embeddings without coupling identity to a tracker."""

    def __init__(self):
        self.available = True
        self.backend = "appearance_fallback"
        self.reason = ""
        self._embedder = None
        self._track_states: Dict[int, TrackEmbeddingState] = {}

        if DEEPSORT_EMBEDDER_AVAILABLE:
            try:
                self._embedder = MobileNetv2_Embedder(
                    half=False,
                    gpu=False,
                    max_batch_size=16,
                    bgr=True,
                )
                self.backend = "deep_sort_mobilenet"
                log.info("Body ReID initialized with DeepSORT MobileNet embedder")
                return
            except Exception as exc:  # pragma: no cover - depends on runtime packages
                self.reason = str(exc)
                log.warning(
                    "Body ReID MobileNet embedder unavailable, fallback to handcrafted appearance embedding: %s",
                    self.reason,
                )
        elif _IMPORT_ERROR:
            self.reason = _IMPORT_ERROR
            log.info(
                "deep_sort_realtime embedder not available, using handcrafted appearance embedding: %s",
                self.reason,
            )

        log.info("Body ReID initialized with handcrafted appearance embedding")

    def reset_daily(self) -> None:
        self._track_states = {}

    def cleanup(self, active_track_ids) -> None:
        stale_ids = [tid for tid in self._track_states if tid not in active_track_ids]
        for tid in stale_ids:
            del self._track_states[tid]

    def describe(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "backend": self.backend,
            "reason": self.reason or None,
            "active_tracks": len(self._track_states),
        }

    def extract_track_embedding(
        self,
        frame: np.ndarray,
        track_id: int,
        bbox: Tuple[float, float, float, float],
        *,
        frame_id: int = 0,
    ) -> Dict[str, Any]:
        state = self._track_states.get(track_id)
        if state is None:
            state = TrackEmbeddingState()
            self._track_states[track_id] = state

        cached_embedding = state.embedding.copy() if state.embedding is not None else None
        if cached_embedding is not None and frame_id == state.last_frame_id:
            return {
                "embedding": cached_embedding,
                "fresh": False,
                "backend": state.backend or self.backend,
            }

        if (
            cached_embedding is not None
            and REID_FRAME_INTERVAL > 1
            and frame_id - state.last_frame_id < REID_FRAME_INTERVAL
        ):
            return {
                "embedding": cached_embedding,
                "fresh": False,
                "backend": state.backend or self.backend,
            }

        crop = self._extract_person_crop(frame, bbox)
        if crop is None:
            return {
                "embedding": cached_embedding,
                "fresh": False,
                "backend": state.backend or self.backend,
            }

        embedding = None
        backend = self.backend
        if self._embedder is not None:
            embedding = self._predict_mobilenet_embedding(crop)
            backend = "deep_sort_mobilenet"

        if embedding is None:
            embedding = self._predict_appearance_embedding(crop)
            backend = "appearance_fallback"

        normalized = _normalize_embedding(embedding)
        if normalized is None:
            return {
                "embedding": cached_embedding,
                "fresh": False,
                "backend": state.backend or backend,
            }

        state.embedding = normalized.copy()
        state.last_frame_id = frame_id
        state.last_extracted_at = time.time()
        state.backend = backend
        return {
            "embedding": normalized.copy(),
            "fresh": True,
            "backend": backend,
        }

    def _extract_person_crop(
        self,
        frame: np.ndarray,
        bbox: Tuple[float, float, float, float],
    ) -> Optional[np.ndarray]:
        if frame is None or frame.size == 0:
            return None

        frame_h, frame_w = frame.shape[:2]
        x1, y1, x2, y2 = [float(v) for v in bbox]
        width = max(0.0, x2 - x1)
        height = max(0.0, y2 - y1)
        if width < REID_MIN_CROP_WIDTH or height < REID_MIN_CROP_HEIGHT:
            return None

        pad_x = width * REID_CROP_PADDING_RATIO
        pad_y = height * REID_CROP_PADDING_RATIO
        crop_x1 = max(0, int(round(x1 - pad_x)))
        crop_y1 = max(0, int(round(y1 - pad_y)))
        crop_x2 = min(frame_w, int(round(x2 + pad_x)))
        crop_y2 = min(frame_h, int(round(y2 + pad_y)))
        if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
            return None

        crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
        if crop.size == 0:
            return None
        return crop

    def _predict_mobilenet_embedding(self, crop: np.ndarray) -> Optional[np.ndarray]:
        if self._embedder is None:
            return None
        try:
            embeddings = self._embedder.predict([crop])
        except Exception as exc:  # pragma: no cover - depends on runtime packages
            log.warning("Body ReID MobileNet inference failed, switching to fallback appearance embedding: %s", exc)
            self._embedder = None
            self.backend = "appearance_fallback"
            if not self.reason:
                self.reason = str(exc)
            return None
        if not embeddings:
            return None
        return np.asarray(embeddings[0], dtype=np.float32)

    def _predict_appearance_embedding(self, crop: np.ndarray) -> Optional[np.ndarray]:
        try:
            resized = cv2.resize(crop, (64, 128), interpolation=cv2.INTER_LINEAR)
        except Exception:
            return None

        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(resized, cv2.COLOR_BGR2LAB)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

        features = []
        stripes = np.array_split(np.arange(resized.shape[0]), 3)
        for stripe_idx in stripes:
            stripe_hsv = hsv[stripe_idx, :, :]
            stripe_lab = lab[stripe_idx, :, :]
            hist = cv2.calcHist([stripe_hsv], [0, 1], None, [12, 8], [0, 180, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            features.append(hist)
            features.append(np.mean(stripe_lab, axis=(0, 1), dtype=np.float32) / 255.0)
            features.append(np.std(stripe_lab, axis=(0, 1), dtype=np.float32) / 255.0)

        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude, angle = cv2.cartToPolar(grad_x, grad_y, angleInDegrees=True)
        cell_h = gray.shape[0] // 4
        cell_w = gray.shape[1] // 2
        for row in range(4):
            for col in range(2):
                y_start = row * cell_h
                y_end = gray.shape[0] if row == 3 else (row + 1) * cell_h
                x_start = col * cell_w
                x_end = gray.shape[1] if col == 1 else (col + 1) * cell_w
                cell_mag = magnitude[y_start:y_end, x_start:x_end]
                cell_angle = angle[y_start:y_end, x_start:x_end]
                hist, _ = np.histogram(
                    cell_angle,
                    bins=8,
                    range=(0.0, 360.0),
                    weights=cell_mag,
                )
                features.append(hist.astype(np.float32))

        vector = np.concatenate([np.asarray(feature, dtype=np.float32).reshape(-1) for feature in features])
        return _normalize_embedding(vector)
