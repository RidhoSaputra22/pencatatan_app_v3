"""API client for backend communication"""
import hashlib
from typing import Optional, Dict, Any, List
import numpy as np
import requests

from .config import BACKEND_URL, AUTH_USER, AUTH_PASS, CAMERA_ID, INGEST_URL


def generate_visitor_key(camera_id: int, track_id: int, date_str: str) -> str:
    """
    Generate visitor_key untuk identifikasi pengunjung unik (fallback).
    Format: hash dari camera_id + track_id + date
    Untuk lebih akurat, gunakan generate_visitor_key_from_embedding.
    """
    raw = f"{camera_id}_{track_id}_{date_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def generate_visitor_key_from_embedding(
    embedding: Optional[np.ndarray], 
    camera_id: int, 
    track_id: int, 
    date_str: str
) -> str:
    """
    Generate visitor_key dari ReID embedding untuk identifikasi visitor yang stabil.
    
    Jika embedding tersedia:
    - Normalize dan quantize embedding
    - Hash embedding untuk visitor_key yang konsisten
    
    Fallback ke track-based jika tidak ada embedding.
    
    Args:
        embedding: ReID embedding vector dari DeepSORT
        camera_id: Camera ID
        track_id: Track ID (fallback)
        date_str: Date string untuk grouping harian
    
    Returns:
        visitor_key: 32 character hash string
    """
    if embedding is None or len(embedding) == 0:
        # Fallback ke track-based key
        return generate_visitor_key(camera_id, track_id, date_str)
    
    # Normalize embedding
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    
    # Quantize to 8-bit untuk tolerance terhadap noise
    quantized = np.clip((embedding * 127 + 128), 0, 255).astype(np.uint8)
    
    # Hash the quantized embedding
    return hashlib.sha256(quantized.tobytes()).hexdigest()[:32]


def login_token() -> Optional[str]:
    """Login ke backend dan dapatkan JWT token"""
    try:
        r = requests.post(
            f"{BACKEND_URL}/api/auth/login",
            json={"username": AUTH_USER, "password": AUTH_PASS},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()["access_token"]
    except Exception as e:
        print(f"[edge] Login failed: {e}")
    return None


def get_camera_config(token: Optional[str]) -> Dict[str, Any]:
    """Get camera configuration from backend"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = requests.get(f"{BACKEND_URL}/api/cameras/{CAMERA_ID}", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[edge] Failed to get camera config: {e}")
    return {}


def get_counting_areas(token: Optional[str]) -> List[Dict[str, Any]]:
    """Get counting areas for camera from backend"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = requests.get(f"{BACKEND_URL}/api/cameras/{CAMERA_ID}/areas", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[edge] Failed to get counting areas: {e}")
    return []


def get_employee_registry(token: Optional[str]) -> Dict[str, Any]:
    """Fetch active employee face embeddings from backend."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = requests.get(f"{BACKEND_URL}/api/employees/registry", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[edge] Failed to get employee registry: {e}")
    return {"items": []}


def send_visitor_event(payload: Dict[str, Any], token: Optional[str]) -> Dict[str, Any]:
    """Send visitor event to backend"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = requests.post(INGEST_URL, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            return {"success": True, "data": r.json(), "status_code": r.status_code}
        else:
            return {"success": False, "error": r.text, "status_code": r.status_code}
    except Exception as e:
        return {"success": False, "error": str(e), "status_code": 0}
