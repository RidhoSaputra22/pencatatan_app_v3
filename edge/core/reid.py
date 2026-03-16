"""
ReID (Re-Identification) module untuk visitor identification
Menggunakan deep appearance features untuk identifikasi visitor yang lebih stabil
"""
import hashlib
from typing import Optional, List, Dict, Any, Tuple
import numpy as np

# Embedding cache untuk menyimpan rata-rata embedding per visitor
# Key: track_id, Value: {'embedding': np.array, 'count': int, 'visitor_key': str}
_embedding_cache: Dict[int, Dict[str, Any]] = {}

# Global registry untuk menyimpan semua embedding hari ini
# Untuk matching visitor yang re-enter
_daily_embeddings: Dict[str, np.ndarray] = {}  # visitor_key -> embedding
_current_date: str = ""


def reset_daily_cache(date_str: str):
    """Reset daily embedding cache jika hari berubah"""
    global _daily_embeddings, _current_date
    if date_str != _current_date:
        _daily_embeddings = {}
        _current_date = date_str
        print(f"[reid] Reset daily embedding cache for {date_str}")


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


def find_similar_embedding(embedding: np.ndarray, threshold: float = 0.7) -> Optional[str]:
    """
    Cari embedding yang mirip di daily cache.
    Returns visitor_key jika ditemukan, None jika tidak.
    """
    if embedding is None or len(embedding) == 0:
        return None
    
    # Normalize input embedding
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    
    best_match = None
    best_similarity = threshold
    
    for visitor_key, cached_emb in _daily_embeddings.items():
        # Cosine similarity
        cached_norm = np.linalg.norm(cached_emb)
        if cached_norm > 0:
            similarity = np.dot(embedding, cached_emb / cached_norm)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = visitor_key
    
    return best_match


def update_track_embedding(track_id: int, embedding: np.ndarray, camera_id: int, date_str: str) -> str:
    """
    Update atau create embedding untuk track.
    Returns visitor_key yang stabil berdasarkan embedding.
    """
    global _embedding_cache, _daily_embeddings
    
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
        print(f"[reid] Track {track_id} matched to existing visitor {visitor_key[:8]}...")
    else:
        # New visitor today
        visitor_key = embedding_to_hash(embedding)
        # Store in daily cache
        _daily_embeddings[visitor_key] = embedding.copy()
        print(f"[reid] New visitor detected: {visitor_key[:8]}...")
    
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
