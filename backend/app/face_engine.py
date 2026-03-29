"""Utilities for employee face enrollment using InsightFace."""
from pathlib import Path
import re
from typing import Any, Dict, Tuple

import cv2
import numpy as np

from .settings import BASE_DIR, settings

try:
    from insightface.app import FaceAnalysis

    INSIGHTFACE_AVAILABLE = True
    _IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - optional dependency path
    FaceAnalysis = None
    INSIGHTFACE_AVAILABLE = False
    _IMPORT_ERROR = str(exc)


_face_app = None


def face_engine_status() -> Tuple[bool, str]:
    """Return current availability status for employee face enrollment."""
    if INSIGHTFACE_AVAILABLE:
        return True, ""
    return False, _IMPORT_ERROR or "InsightFace is not installed"


def get_face_app():
    """Lazily initialize InsightFace application."""
    global _face_app

    if not INSIGHTFACE_AVAILABLE:
        raise RuntimeError(
            "InsightFace belum tersedia di backend. Install dependency backend untuk fitur pegawai."
        )

    if _face_app is None:
        app = FaceAnalysis(
            name=settings.insightface_model_name,
            providers=settings.insightface_provider_list(),
        )
        det_size = (settings.insightface_det_size, settings.insightface_det_size)
        app.prepare(ctx_id=-1, det_size=det_size)
        _face_app = app
    return _face_app


def _normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(embedding)
    if norm <= 0:
        return embedding
    return embedding / norm


def extract_face_embedding(image_bytes: bytes) -> Dict[str, Any]:
    """
    Extract a single normalized face embedding from an uploaded employee photo.
    Rejects images that contain zero or multiple faces to avoid ambiguous enrolment.
    """
    if not image_bytes:
        raise ValueError("Foto pegawai kosong")

    image_np = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("File foto pegawai tidak valid")

    faces = get_face_app().get(image)
    if len(faces) == 0:
        raise ValueError("Wajah pegawai tidak terdeteksi. Gunakan foto frontal yang lebih jelas.")
    if len(faces) > 1:
        raise ValueError("Foto pegawai harus berisi tepat satu wajah.")

    face = faces[0]
    embedding = getattr(face, "embedding", None)
    if embedding is None or len(embedding) == 0:
        raise ValueError("Embedding wajah tidak berhasil dibuat.")

    embedding = _normalize_embedding(np.asarray(embedding, dtype=np.float32))
    bbox = [float(v) for v in getattr(face, "bbox", [])]
    det_score = float(getattr(face, "det_score", 0.0))

    return {
        "embedding": embedding.tolist(),
        "det_score": det_score,
        "bbox": bbox,
    }


def _safe_extension(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return ext
    return ".jpg"


def store_employee_photo(employee_id: int, employee_code: str, image_bytes: bytes, filename: str) -> str:
    """Persist the uploaded reference photo and return a backend-relative path."""
    storage_dir = Path(settings.employee_faces_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    safe_code = re.sub(r"[^a-zA-Z0-9_-]+", "_", employee_code).strip("_") or "employee"
    ext = _safe_extension(filename)
    file_path = storage_dir / f"employee_{employee_id}_{safe_code}{ext}"
    file_path.write_bytes(image_bytes)

    try:
        return str(file_path.relative_to(BASE_DIR))
    except ValueError:
        return str(file_path)
