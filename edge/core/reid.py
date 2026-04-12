"""
ReID (Re-Identification) module untuk visitor identification.

Tuning utama:
- visitor_key tidak langsung dikunci di frame pertama track
- embedding visitor harian diperbarui terus agar prototype makin stabil
- provisional key bisa di-alias ke canonical visitor_key untuk hitungan kumulatif
"""
import hashlib
from typing import Optional, List, Dict, Any

import numpy as np

from .config import (
    REID_AMBIGUITY_MARGIN,
    REID_MATCH_THRESHOLD,
    REID_MIN_TRACK_FRAMES,
    REID_PROTOTYPE_ALPHA,
    REID_STRONG_MATCH_THRESHOLD,
)
from .logger import get_logger

log = get_logger("reid")

# Key: track_id, Value: metadata embedding + identity decision
_embedding_cache: Dict[int, Dict[str, Any]] = {}

# Global registry untuk menyimpan canonical visitor embeddings hari ini
_daily_embeddings: Dict[str, np.ndarray] = {}  # visitor_key -> embedding
_daily_embedding_counts: Dict[str, int] = {}   # visitor_key -> sample count
_daily_keys: List[str] = []                    # ordered keys for matrix lookup
_daily_matrix: Optional[np.ndarray] = None     # stacked normalized embeddings (N x D)
_daily_matrix_dirty: bool = False              # flag to rebuild matrix
_visitor_aliases: Dict[str, str] = {}          # provisional/raw key -> canonical key
_current_date: str = ""


def reset_daily_cache(date_str: str):
    """Reset daily embedding cache jika hari berubah."""
    global _embedding_cache
    global _daily_embeddings, _daily_embedding_counts, _current_date
    global _daily_keys, _daily_matrix, _daily_matrix_dirty, _visitor_aliases
    if date_str != _current_date:
        _embedding_cache = {}
        _daily_embeddings = {}
        _daily_embedding_counts = {}
        _daily_keys = []
        _daily_matrix = None
        _daily_matrix_dirty = False
        _visitor_aliases = {}
        _current_date = date_str
        log.info("Reset daily embedding cache for %s", date_str)


def _normalize_embedding(embedding: Optional[np.ndarray]) -> Optional[np.ndarray]:
    if embedding is None or len(embedding) == 0:
        return None

    vector = np.asarray(embedding, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        return None
    return vector / norm


def _track_fallback_key(camera_id: int, track_id: int, date_str: str) -> str:
    raw = f"{camera_id}_{track_id}_{date_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _provisional_track_key(camera_id: int, track_id: int, date_str: str) -> str:
    raw = f"pending_{camera_id}_{track_id}_{date_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def embedding_to_hash(embedding: np.ndarray) -> str:
    """
    Convert embedding vector ke hash string untuk visitor_key.
    Menggunakan quantization untuk tolerance terhadap noise.
    """
    normalized = _normalize_embedding(embedding)
    if normalized is None:
        return ""

    quantized = np.clip((normalized * 127 + 128), 0, 255).astype(np.uint8)
    return hashlib.sha256(quantized.tobytes()).hexdigest()[:32]


def canonicalize_visitor_key(visitor_key: Optional[str]) -> str:
    """Resolve alias chain ke canonical visitor_key."""
    key = (visitor_key or "").strip()
    if not key:
        return ""

    seen: set[str] = set()
    while key in _visitor_aliases and key not in seen:
        seen.add(key)
        key = _visitor_aliases[key]
    return key


def _register_alias(source_key: Optional[str], target_key: Optional[str]) -> None:
    source = canonicalize_visitor_key(source_key)
    target = canonicalize_visitor_key(target_key)
    if not source or not target or source == target:
        return
    _visitor_aliases[source] = target


def _rebuild_daily_matrix():
    """Rebuild the stacked embedding matrix from _daily_embeddings."""
    global _daily_keys, _daily_matrix, _daily_matrix_dirty
    _daily_keys = list(_daily_embeddings.keys())
    if _daily_keys:
        _daily_matrix = np.stack([_daily_embeddings[k] for k in _daily_keys], axis=0)
    else:
        _daily_matrix = None
    _daily_matrix_dirty = False


def _update_daily_embedding(visitor_key: str, embedding: np.ndarray) -> None:
    """Blend embedding baru ke prototype visitor canonical."""
    global _daily_matrix_dirty
    canonical_key = canonicalize_visitor_key(visitor_key)
    normalized = _normalize_embedding(embedding)
    if not canonical_key or normalized is None:
        return

    existing = _daily_embeddings.get(canonical_key)
    if existing is None:
        _daily_embeddings[canonical_key] = normalized.copy()
        _daily_embedding_counts[canonical_key] = 1
        _daily_matrix_dirty = True
        return

    alpha = float(max(0.01, min(1.0, REID_PROTOTYPE_ALPHA)))
    blended = existing * (1.0 - alpha) + normalized * alpha
    blended = _normalize_embedding(blended)
    if blended is None:
        blended = normalized.copy()

    _daily_embeddings[canonical_key] = blended
    _daily_embedding_counts[canonical_key] = _daily_embedding_counts.get(canonical_key, 1) + 1
    _daily_matrix_dirty = True


def _remove_daily_embedding(visitor_key: Optional[str]) -> None:
    global _daily_matrix_dirty
    canonical_key = canonicalize_visitor_key(visitor_key)
    if not canonical_key:
        return
    removed = False
    if canonical_key in _daily_embeddings:
        del _daily_embeddings[canonical_key]
        removed = True
    if canonical_key in _daily_embedding_counts:
        del _daily_embedding_counts[canonical_key]
    if removed:
        _daily_matrix_dirty = True


def find_similar_embedding(embedding: np.ndarray, threshold: float = 0.7) -> Dict[str, Any]:
    """
    Cari embedding yang mirip di daily cache.
    Menggunakan batch matrix dot product (O(1) numpy op) bukan loop Python O(n).
    """
    global _daily_matrix_dirty

    normalized = _normalize_embedding(embedding)
    if normalized is None:
        return {
            "visitor_key": None,
            "similarity": 0.0,
            "second_similarity": 0.0,
            "margin": 0.0,
            "confident": False,
        }

    if not _daily_embeddings:
        return {
            "visitor_key": None,
            "similarity": 0.0,
            "second_similarity": 0.0,
            "margin": 0.0,
            "confident": False,
        }

    if _daily_matrix_dirty or _daily_matrix is None:
        _rebuild_daily_matrix()

    if _daily_matrix is None or not _daily_keys:
        return {
            "visitor_key": None,
            "similarity": 0.0,
            "second_similarity": 0.0,
            "margin": 0.0,
            "confident": False,
        }

    similarities = _daily_matrix @ normalized
    order = np.argsort(similarities)[::-1]
    best_idx = int(order[0])
    best_similarity = float(similarities[best_idx])
    second_similarity = float(similarities[int(order[1])]) if len(order) > 1 else 0.0
    margin = best_similarity - second_similarity
    confident = best_similarity >= threshold and (
        best_similarity >= REID_STRONG_MATCH_THRESHOLD or margin >= REID_AMBIGUITY_MARGIN
    )

    return {
        "visitor_key": _daily_keys[best_idx],
        "similarity": best_similarity,
        "second_similarity": second_similarity,
        "margin": margin,
        "confident": confident,
    }


def _serialize_identity(cache: Dict[str, Any]) -> Dict[str, Any]:
    visitor_key = canonicalize_visitor_key(cache.get("visitor_key"))
    similarity = cache.get("match_similarity")
    margin = cache.get("match_margin")
    return {
        "visitor_key": visitor_key,
        "identity_status": cache.get("identity_status", "PENDING"),
        "reid_source": cache.get("reid_source", "pending_track"),
        "embedding_samples": int(cache.get("count", 0)),
        "match_similarity": round(float(similarity), 4) if similarity is not None else None,
        "match_margin": round(float(margin), 4) if margin is not None else None,
    }


def _new_track_cache(track_id: int, camera_id: int, date_str: str) -> Dict[str, Any]:
    provisional_key = _provisional_track_key(camera_id, track_id, date_str)
    return {
        "embedding": None,
        "count": 0,
        "visitor_key": provisional_key,
        "provisional_key": provisional_key,
        "fallback_key": _track_fallback_key(camera_id, track_id, date_str),
        "identity_status": "PENDING",
        "reid_source": "pending_track",
        "match_similarity": None,
        "match_margin": None,
    }


def _bind_track_to_existing(cache: Dict[str, Any], visitor_key: str, similarity: float, margin: float) -> None:
    previous_key = cache.get("visitor_key")
    canonical_key = canonicalize_visitor_key(visitor_key)
    cache["visitor_key"] = canonical_key
    cache["identity_status"] = "CONFIRMED"
    cache["reid_source"] = "matched_existing"
    cache["match_similarity"] = similarity
    cache["match_margin"] = margin

    _register_alias(cache.get("provisional_key"), canonical_key)
    _register_alias(previous_key, canonical_key)

    embedding = cache.get("embedding")
    if embedding is not None:
        _update_daily_embedding(canonical_key, embedding)


def _bind_track_as_new(cache: Dict[str, Any]) -> None:
    previous_key = cache.get("visitor_key")
    embedding = cache.get("embedding")
    if embedding is None:
        cache["visitor_key"] = cache.get("fallback_key", previous_key)
        cache["identity_status"] = "FALLBACK"
        cache["reid_source"] = "fallback_track_id"
        cache["match_similarity"] = None
        cache["match_margin"] = None
        return

    visitor_key = embedding_to_hash(embedding)
    if not visitor_key:
        cache["visitor_key"] = cache.get("fallback_key", previous_key)
        cache["identity_status"] = "FALLBACK"
        cache["reid_source"] = "fallback_track_id"
        cache["match_similarity"] = None
        cache["match_margin"] = None
        return

    cache["visitor_key"] = visitor_key
    cache["identity_status"] = "CONFIRMED"
    cache["reid_source"] = "new_visitor"
    cache["match_similarity"] = None
    cache["match_margin"] = None

    _register_alias(cache.get("provisional_key"), visitor_key)
    _register_alias(previous_key, visitor_key)
    _update_daily_embedding(visitor_key, embedding)


def _refresh_track_average(cache: Dict[str, Any], embedding: np.ndarray) -> None:
    old_embedding = cache.get("embedding")
    count = int(cache.get("count", 0))
    if old_embedding is None or count <= 0:
        cache["embedding"] = embedding.copy()
        cache["count"] = 1
        return

    averaged = (old_embedding * count + embedding) / float(count + 1)
    normalized = _normalize_embedding(averaged)
    cache["embedding"] = normalized if normalized is not None else embedding.copy()
    cache["count"] = count + 1


def _finalize_stale_track(cache: Dict[str, Any]) -> None:
    if cache.get("identity_status") == "CONFIRMED":
        return
    embedding = cache.get("embedding")
    if embedding is None:
        cache["visitor_key"] = cache.get("fallback_key", cache.get("visitor_key"))
        cache["identity_status"] = "FALLBACK"
        cache["reid_source"] = "fallback_track_id"
        cache["match_similarity"] = None
        cache["match_margin"] = None
        return

    match = find_similar_embedding(embedding, threshold=REID_MATCH_THRESHOLD)
    if match["visitor_key"] and match["confident"]:
        _bind_track_to_existing(cache, match["visitor_key"], match["similarity"], match["margin"])
        return
    _bind_track_as_new(cache)


def update_track_identity(track_id: int, embedding: np.ndarray, camera_id: int, date_str: str) -> Dict[str, Any]:
    """
    Update atau create embedding untuk track.
    Returns metadata identity yang lebih kaya daripada sekadar visitor_key.
    """
    reset_daily_cache(date_str)

    cache = _embedding_cache.get(track_id)
    if cache is None:
        cache = _new_track_cache(track_id, camera_id, date_str)
        _embedding_cache[track_id] = cache

    normalized = _normalize_embedding(embedding)
    if normalized is None:
        cache["visitor_key"] = cache.get("fallback_key", cache.get("visitor_key"))
        cache["identity_status"] = "FALLBACK"
        cache["reid_source"] = "fallback_track_id"
        cache["match_similarity"] = None
        cache["match_margin"] = None
        return _serialize_identity(cache)

    _refresh_track_average(cache, normalized)
    averaged_embedding = cache.get("embedding")
    if averaged_embedding is None:
        cache["visitor_key"] = cache.get("fallback_key", cache.get("visitor_key"))
        cache["identity_status"] = "FALLBACK"
        cache["reid_source"] = "fallback_track_id"
        cache["match_similarity"] = None
        cache["match_margin"] = None
        return _serialize_identity(cache)

    match = find_similar_embedding(averaged_embedding, threshold=REID_MATCH_THRESHOLD)
    enough_samples = int(cache.get("count", 0)) >= REID_MIN_TRACK_FRAMES

    if match["visitor_key"] and match["confident"]:
        if canonicalize_visitor_key(match["visitor_key"]) != canonicalize_visitor_key(cache.get("visitor_key")):
            if cache.get("reid_source") == "new_visitor":
                _remove_daily_embedding(cache.get("visitor_key"))
            _bind_track_to_existing(cache, match["visitor_key"], match["similarity"], match["margin"])
        else:
            cache["identity_status"] = "CONFIRMED"
            cache["reid_source"] = cache.get("reid_source", "matched_existing")
            cache["match_similarity"] = match["similarity"]
            cache["match_margin"] = match["margin"]
            _update_daily_embedding(cache["visitor_key"], averaged_embedding)
        return _serialize_identity(cache)

    if cache.get("identity_status") == "CONFIRMED":
        _update_daily_embedding(cache["visitor_key"], averaged_embedding)
        return _serialize_identity(cache)

    if enough_samples:
        _bind_track_as_new(cache)
        return _serialize_identity(cache)

    cache["visitor_key"] = cache.get("provisional_key", cache.get("visitor_key"))
    cache["identity_status"] = "PENDING"
    cache["reid_source"] = "pending_track"
    cache["match_similarity"] = match["similarity"] if match["visitor_key"] else None
    cache["match_margin"] = match["margin"] if match["visitor_key"] else None
    return _serialize_identity(cache)


def update_track_embedding(track_id: int, embedding: np.ndarray, camera_id: int, date_str: str) -> str:
    """Backward-compatible wrapper: return current canonical visitor_key."""
    return update_track_identity(track_id, embedding, camera_id, date_str)["visitor_key"]


def get_visitor_key_for_track(track_id: int, camera_id: int, date_str: str) -> Optional[str]:
    """Get cached visitor_key for a track if exists."""
    reset_daily_cache(date_str)
    if track_id in _embedding_cache:
        return canonicalize_visitor_key(_embedding_cache[track_id].get("visitor_key"))
    return None


def cleanup_old_tracks(active_track_ids: List[int]):
    """Remove tracks that are no longer active from cache."""
    global _embedding_cache
    to_remove = [tid for tid in _embedding_cache if tid not in active_track_ids]
    for tid in to_remove:
        _finalize_stale_track(_embedding_cache[tid])
        del _embedding_cache[tid]


def get_cache_stats() -> Dict[str, int]:
    """Get statistics about the embedding cache."""
    return {
        "active_tracks": len(_embedding_cache),
        "daily_visitors": len(_daily_embeddings),
        "alias_count": len(_visitor_aliases),
    }


def get_reid_config() -> Dict[str, float]:
    """Expose active ReID tuning for summaries/diagnostics."""
    return {
        "match_threshold": float(REID_MATCH_THRESHOLD),
        "strong_match_threshold": float(REID_STRONG_MATCH_THRESHOLD),
        "ambiguity_margin": float(REID_AMBIGUITY_MARGIN),
        "min_track_frames": float(REID_MIN_TRACK_FRAMES),
        "prototype_alpha": float(REID_PROTOTYPE_ALPHA),
    }
