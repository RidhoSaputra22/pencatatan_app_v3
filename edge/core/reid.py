"""
ReID (Re-Identification) module untuk visitor identification
Menggunakan deep appearance features untuk identifikasi visitor yang lebih stabil
"""
import hashlib
from typing import Optional, List, Dict, Any, Tuple
import numpy as np

from .logger import get_logger

log = get_logger("reid")

# Embedding cache untuk menyimpan rata-rata embedding per visitor
# Key: track_id, Value: {'embedding': np.array, 'count': int, 'visitor_key': str}
_embedding_cache: Dict[int, Dict[str, Any]] = {}

# Global registry untuk menyimpan semua embedding hari ini
# Untuk matching visitor yang re-enter
_daily_embeddings: Dict[str, np.ndarray] = {}  # visitor_key -> embedding
_daily_keys: List[str] = []          # ordered keys for matrix lookup
_daily_matrix: Optional[np.ndarray] = None  # stacked normalized embeddings (N x D)
_daily_matrix_dirty: bool = False     # flag to rebuild matrix
_current_date: str = ""


def reset_daily_cache(date_str: str):
    """Reset daily embedding cache jika hari berubah"""
    global _daily_embeddings, _current_date, _daily_keys, _daily_matrix, _daily_matrix_dirty
    if date_str != _current_date:
        _daily_embeddings = {}
        _daily_keys = []
        _daily_matrix = None
        _daily_matrix_dirty = False
        _current_date = date_str
        log.info("Reset daily embedding cache for %s", date_str)


def embedding_to_hash(embedding: np.ndarray) -> str:
    """
    Convert embedding vector ke hash string untuk visitor_key.
    Menggunakan quantization untuk tolerance terhadap noise.
    """
    if embedding is None or len(embedding) == 0:
        return ""
    
    # Normalize embedding
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    
    # Quantize ke 8-bit untuk tolerance
    quantized = np.clip((embedding * 127 + 128), 0, 255).astype(np.uint8)
    
    # Hash the quantized embedding
    return hashlib.sha256(quantized.tobytes()).hexdigest()[:32]


def _rebuild_daily_matrix():
    """Rebuild the stacked embedding matrix from _daily_embeddings."""
    global _daily_keys, _daily_matrix, _daily_matrix_dirty
    _daily_keys = list(_daily_embeddings.keys())
    if _daily_keys:
        _daily_matrix = np.stack(
            [_daily_embeddings[k] for k in _daily_keys], axis=0
        )
    else:
        _daily_matrix = None
    _daily_matrix_dirty = False


def find_similar_embedding(embedding: np.ndarray, threshold: float = 0.7) -> Optional[str]:
    """
    Cari embedding yang mirip di daily cache.
    Menggunakan batch matrix dot product (O(1) numpy op) bukan loop Python O(n).
    Returns visitor_key jika ditemukan, None jika tidak.
    """
    global _daily_matrix_dirty

    if embedding is None or len(embedding) == 0:
        return None

    if not _daily_embeddings:
        return None

    # Rebuild matrix jika ada perubahan sejak terakhir
    if _daily_matrix_dirty or _daily_matrix is None:
        _rebuild_daily_matrix()

    if _daily_matrix is None:
        return None

    # Normalize input embedding
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    # Batch cosine similarity: (N,D) @ (D,) -> (N,)
    similarities = _daily_matrix @ embedding
    max_idx = int(np.argmax(similarities))
    if similarities[max_idx] > threshold:
        return _daily_keys[max_idx]

    return None


def update_track_embedding(track_id: int, embedding: np.ndarray, camera_id: int, date_str: str) -> str:
    """
    Update atau create embedding untuk track.
    Returns visitor_key yang stabil berdasarkan embedding.
    """
    global _embedding_cache, _daily_embeddings, _daily_matrix_dirty
    
    # Reset cache jika hari berubah
    reset_daily_cache(date_str)
    
    if embedding is None or len(embedding) == 0:
        # Fallback ke track-based key jika tidak ada embedding
        raw = f"{camera_id}_{track_id}_{date_str}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
    
    # Normalize embedding
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    
    # Check if this track already exists
    if track_id in _embedding_cache:
        cache = _embedding_cache[track_id]
        # Update running average
        count = cache['count']
        old_emb = cache['embedding']
        new_emb = (old_emb * count + embedding) / (count + 1)
        cache['embedding'] = new_emb / np.linalg.norm(new_emb)  # Re-normalize
        cache['count'] = count + 1
        return cache['visitor_key']
    
    # New track - check if similar visitor already exists today
    existing_key = find_similar_embedding(embedding, threshold=0.65)
    
    if existing_key:
        # Same person re-entered - use existing visitor_key
        visitor_key = existing_key
        log.debug("Track %d matched to existing visitor %s...", track_id, visitor_key[:8])
    else:
        # New visitor today
        visitor_key = embedding_to_hash(embedding)
        # Store in daily cache and mark matrix for rebuild
        _daily_embeddings[visitor_key] = embedding.copy()
        _daily_matrix_dirty = True
        log.debug("New visitor detected: %s...", visitor_key[:8])
    
    # Cache this track
    _embedding_cache[track_id] = {
        'embedding': embedding.copy(),
        'count': 1,
        'visitor_key': visitor_key
    }
    
    return visitor_key


def get_visitor_key_for_track(track_id: int, camera_id: int, date_str: str) -> Optional[str]:
    """Get cached visitor_key for a track if exists"""
    if track_id in _embedding_cache:
        return _embedding_cache[track_id]['visitor_key']
    return None


def cleanup_old_tracks(active_track_ids: List[int]):
    """Remove tracks that are no longer active from cache"""
    global _embedding_cache
    to_remove = [tid for tid in _embedding_cache if tid not in active_track_ids]
    for tid in to_remove:
        del _embedding_cache[tid]


def get_cache_stats() -> Dict[str, int]:
    """Get statistics about the embedding cache"""
    return {
        'active_tracks': len(_embedding_cache),
        'daily_visitors': len(_daily_embeddings)
    }
