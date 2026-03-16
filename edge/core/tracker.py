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

try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    DEEPSORT_AVAILABLE = True
except ImportError:
    DEEPSORT_AVAILABLE = False
    print("[tracker] Warning: deep-sort-realtime not installed. Using fallback CentroidTracker.")


@dataclass
class Track:
    """Track object untuk menyimpan informasi tracking"""
    tid: int
    centroid: Tuple[float, float]
    bbox: Tuple[float, float, float, float]  # x1,y1,x2,y2
    embedding: Optional[np.ndarray] = None  # ReID embedding
    confidence: float = 0.0
    disappeared: int = 0
    in_roi: bool = False
    is_new: bool = True
    last_direction: Optional[str] = None


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
        
        if DEEPSORT_AVAILABLE:
            self.tracker = DeepSort(
                max_age=max_age,
                n_init=n_init,
                max_cosine_distance=max_cosine_distance,
                embedder="mobilenet",  # Built-in ReID model
                half=False,
                embedder_gpu=False  # Use CPU for compatibility
            )
            print(f"[tracker] DeepSORT initialized (max_age={max_age}, n_init={n_init})")
        else:
            self.tracker = None
            self._fallback_tracker = CentroidTrackerFallback(max_disappeared=max_age)
            print("[tracker] Using fallback CentroidTracker")
        
        self.tracks: Dict[int, Track] = {}
    
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
            return self._fallback_tracker.update(bboxes)
        
        if len(detections) == 0:
            # No detections - update tracker with empty list
            self.tracker.update_tracks([], frame=frame)
            self._update_tracks_from_deepsort()
            return self.tracks
        
        # Format detections for DeepSORT: [[x1, y1, w, h], conf, class]
        ds_detections = []
        for det in detections:
            x1, y1, x2, y2, conf = det
            w = x2 - x1
            h = y2 - y1
            ds_detections.append(([x1, y1, w, h], conf, 'person'))
        
        # Update DeepSORT
        tracks = self.tracker.update_tracks(ds_detections, frame=frame)
        
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
            active_ids.add(tid)
            
            # Get bounding box
            ltrb = track.to_ltrb()  # [x1, y1, x2, y2]
            bbox = (float(ltrb[0]), float(ltrb[1]), float(ltrb[2]), float(ltrb[3]))
            
            # Calculate centroid
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            
            # Get embedding if available
            embedding = None
            if hasattr(track, 'get_feature') and callable(track.get_feature):
                embedding = track.get_feature()
            elif hasattr(track, 'features') and track.features is not None and len(track.features) > 0:
                embedding = np.array(track.features[-1])
            
            # Update or create track
            if tid in self.tracks:
                self.tracks[tid].centroid = (cx, cy)
                self.tracks[tid].bbox = bbox
                if embedding is not None:
                    self.tracks[tid].embedding = embedding
                self.tracks[tid].disappeared = 0
            else:
                self.tracks[tid] = Track(
                    tid=tid,
                    centroid=(cx, cy),
                    bbox=bbox,
                    embedding=embedding,
                    confidence=0.0,
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


class CentroidTrackerFallback:
    """Fallback centroid tracker jika DeepSORT tidak tersedia"""
    
    def __init__(self, max_disappeared: int = 30, max_distance: float = 80.0):
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.next_id = 1
        self.tracks: Dict[int, Track] = {}

    def update(self, detections: List[Tuple[float, float, float, float]]) -> Dict[int, Track]:
        """Update tracker with new detections"""
        if len(detections) == 0:
            to_del = []
            for tid, tr in self.tracks.items():
                tr.disappeared += 1
                if tr.disappeared > self.max_disappeared:
                    to_del.append(tid)
            for tid in to_del:
                del self.tracks[tid]
            return self.tracks

        det_centroids = []
        for (x1, y1, x2, y2) in detections:
            det_centroids.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
        det_centroids = np.array(det_centroids, dtype=np.float32)

        if len(self.tracks) == 0:
            for i, bbox in enumerate(detections):
                c = tuple(det_centroids[i])
                tid = self.next_id
                self.next_id += 1
                self.tracks[tid] = Track(tid=tid, centroid=c, bbox=bbox)
            return self.tracks

        track_ids = list(self.tracks.keys())
        track_centroids = np.array([self.tracks[tid].centroid for tid in track_ids], dtype=np.float32)

        dists = np.linalg.norm(track_centroids[:, None, :] - det_centroids[None, :, :], axis=2)

        used_tracks = set()
        used_dets = set()

        for _ in range(min(dists.shape[0], dists.shape[1])):
            t_idx, d_idx = np.unravel_index(np.argmin(dists), dists.shape)
            min_dist = dists[t_idx, d_idx]
            if min_dist > self.max_distance:
                break

            tid = track_ids[t_idx]
            if tid in used_tracks or d_idx in used_dets:
                dists[t_idx, d_idx] = np.inf
                continue

            self.tracks[tid].centroid = tuple(det_centroids[d_idx])
            self.tracks[tid].bbox = detections[d_idx]
            self.tracks[tid].disappeared = 0

            used_tracks.add(tid)
            used_dets.add(d_idx)

            dists[t_idx, :] = np.inf
            dists[:, d_idx] = np.inf

        to_del = []
        for tid in track_ids:
            if tid not in used_tracks:
                self.tracks[tid].disappeared += 1
                if self.tracks[tid].disappeared > self.max_disappeared:
                    to_del.append(tid)
        for tid in to_del:
            del self.tracks[tid]

        for i, bbox in enumerate(detections):
            if i in used_dets:
                continue
            c = tuple(det_centroids[i])
            tid = self.next_id
            self.next_id += 1
            self.tracks[tid] = Track(tid=tid, centroid=c, bbox=bbox)

        return self.tracks


# Legacy alias for backward compatibility
CentroidTracker = CentroidTrackerFallback
