"""
Stream Capture Manager — mengelola capture video dari RTSP/webcam/file
langsung di server, menggantikan kebutuhan menjalankan script terpisah.

Arsitektur:
  Admin Panel (frontend) ──API──→ Backend (module ini) ──→ Capture Thread
                                                               ↓
                                                        /stream/capture (MJPEG)
                                                               ↓
                                                        Edge Worker (YOLO)
"""

import threading
import time
from typing import Optional

import cv2
import numpy as np

# ---------- Shared state ----------
_latest_frame: Optional[np.ndarray] = None
_latest_jpeg: Optional[bytes] = None
_frame_version = 0
_last_frame_time = 0.0
_capture_running = False
_capture_source: Optional[str] = None
_capture_error: Optional[str] = None
_capture_fps = 0.0
_capture_resolution = (0, 0)

_lock = threading.Lock()
_condition = threading.Condition(_lock)

# ---------- Config ----------
_config = {
    "quality": 80,       # JPEG quality 1-100
    "max_fps": 15,       # Maximum FPS to capture
    "max_width": 960,    # Resize frame if wider
}


def get_capture_state() -> dict:
    """Return current capture state for health-checks and UI."""
    with _lock:
        has_frame = _latest_frame is not None
        age_ms = int((time.time() - _last_frame_time) * 1000) if has_frame else None
        return {
            "running": _capture_running,
            "source": _capture_source,
            "has_frame": has_frame,
            "frame_age_ms": age_ms,
            "frame_version": _frame_version,
            "fps": round(_capture_fps, 1),
            "resolution": list(_capture_resolution),
            "error": _capture_error,
            "config": dict(_config),
        }


def get_latest_capture_jpeg() -> Optional[bytes]:
    """Return latest JPEG bytes (or None)."""
    with _lock:
        return _latest_jpeg


# ---------- Capture Thread ----------

def _capture_loop(source: str, stop_event: threading.Event):
    """
    Background thread: opens video source, reads frames, encodes to JPEG.
    Supports: RTSP URL, HTTP URL, webcam index (as string "0","1",...), file path.
    """
    global _latest_frame, _latest_jpeg, _frame_version, _last_frame_time
    global _capture_running, _capture_error, _capture_fps, _capture_resolution

    # Parse source: if it's a digit string, treat as webcam index
    if source.isdigit():
        cap_source = int(source)
    else:
        cap_source = source

    _capture_error = None
    _capture_running = True

    cap = None
    try:
        cap = cv2.VideoCapture(cap_source)
        if not cap.isOpened():
            with _lock:
                _capture_error = f"Gagal membuka sumber video: {source}"
                _capture_running = False
            return

        # Read source info
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        with _lock:
            _capture_resolution = (w, h)

        min_interval = 1.0 / _config["max_fps"] if _config["max_fps"] > 0 else 0
        fps_counter = 0
        fps_timer = time.time()
        is_file = _is_video_file(source)

        while not stop_event.is_set():
            frame_start = time.time()

            ret, frame = cap.read()
            if not ret:
                if is_file:
                    # Loop video file
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    # Stream ended or failed — try reconnecting
                    with _lock:
                        _capture_error = "Stream terputus, mencoba reconnect..."
                    cap.release()
                    time.sleep(2)
                    cap = cv2.VideoCapture(cap_source)
                    if not cap.isOpened():
                        with _lock:
                            _capture_error = "Reconnect gagal"
                            _capture_running = False
                        return
                    with _lock:
                        _capture_error = None
                    continue

            # Resize if needed
            max_w = _config["max_width"]
            if max_w and frame.shape[1] > max_w:
                scale = max_w / frame.shape[1]
                frame = cv2.resize(frame, (max_w, int(frame.shape[0] * scale)))

            # Encode to JPEG
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, _config["quality"]]
            ok, jpeg_buf = cv2.imencode(".jpg", frame, encode_params)
            if not ok:
                continue
            jpeg_bytes = jpeg_buf.tobytes()

            with _condition:
                _latest_frame = frame
                _latest_jpeg = jpeg_bytes
                _frame_version += 1
                _last_frame_time = time.time()
                _capture_error = None
                _condition.notify_all()

            # FPS tracking
            fps_counter += 1
            elapsed = time.time() - fps_timer
            if elapsed >= 1.0:
                with _lock:
                    _capture_fps = fps_counter / elapsed
                fps_counter = 0
                fps_timer = time.time()

            # FPS limiter
            frame_elapsed = time.time() - frame_start
            if frame_elapsed < min_interval:
                time.sleep(min_interval - frame_elapsed)

    except Exception as e:
        with _lock:
            _capture_error = str(e)
    finally:
        if cap is not None:
            cap.release()
        with _lock:
            _capture_running = False
            _latest_frame = None
            _latest_jpeg = None


def _is_video_file(source: str) -> bool:
    """Check if source is a local video file (not a stream URL)."""
    if source.isdigit():
        return False
    lower = source.lower()
    if lower.startswith(("rtsp://", "http://", "https://")):
        return False
    video_exts = {".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv", ".webm"}
    import os
    ext = os.path.splitext(lower)[1]
    return ext in video_exts


# ---------- MJPEG Generator ----------

def generate_capture_frames():
    """Generate MJPEG frames for HTTP streaming."""
    last_version = -1

    while True:
        with _condition:
            _condition.wait_for(
                lambda: _latest_jpeg is not None and _frame_version != last_version,
                timeout=2.0,
            )
            jpeg = _latest_jpeg
            version = _frame_version

        if jpeg is None or version == last_version:
            continue

        last_version = version
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        )


# ---------- Start / Stop / Update Config ----------

_stop_event: Optional[threading.Event] = None
_capture_thread: Optional[threading.Thread] = None


def start_capture(source: str, quality: int = 80, max_fps: int = 15, max_width: int = 960) -> dict:
    """Start capturing from the given source. Stops any existing capture first."""
    global _stop_event, _capture_thread, _capture_source

    # Stop existing if running
    stop_capture()

    # Update config
    _config["quality"] = max(1, min(100, quality))
    _config["max_fps"] = max(1, min(60, max_fps))
    _config["max_width"] = max(320, min(1920, max_width))

    _capture_source = source
    _stop_event = threading.Event()
    _capture_thread = threading.Thread(
        target=_capture_loop,
        args=(source, _stop_event),
        daemon=True,
        name="stream-capture",
    )
    _capture_thread.start()

    # Wait briefly for initial frame or error
    time.sleep(1.0)
    return get_capture_state()


def stop_capture() -> dict:
    """Stop current capture."""
    global _stop_event, _capture_thread, _capture_source, _capture_running

    if _stop_event is not None:
        _stop_event.set()
    if _capture_thread is not None and _capture_thread.is_alive():
        _capture_thread.join(timeout=5.0)

    _stop_event = None
    _capture_thread = None

    with _lock:
        _capture_source = None
        _capture_running = False

    return get_capture_state()


def update_capture_config(quality: Optional[int] = None, max_fps: Optional[int] = None, max_width: Optional[int] = None):
    """Update capture config on the fly."""
    if quality is not None:
        _config["quality"] = max(1, min(100, quality))
    if max_fps is not None:
        _config["max_fps"] = max(1, min(60, max_fps))
    if max_width is not None:
        _config["max_width"] = max(320, min(1920, max_width))
    return dict(_config)


def test_source(source: str, timeout: float = 5.0) -> dict:
    """Test if a video source can be opened successfully."""
    if source.isdigit():
        cap_source = int(source)
    else:
        cap_source = source

    try:
        cap = cv2.VideoCapture(cap_source)
        if not cap.isOpened():
            return {"ok": False, "error": "Tidak dapat membuka sumber video"}

        # Try to read a frame with timeout
        start = time.time()
        ret = False
        while time.time() - start < timeout:
            ret, frame = cap.read()
            if ret:
                break
            time.sleep(0.1)

        if not ret:
            cap.release()
            return {"ok": False, "error": "Tidak ada frame yang diterima"}

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        return {
            "ok": True,
            "resolution": [w, h],
            "fps": round(fps, 1) if fps > 0 else None,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
