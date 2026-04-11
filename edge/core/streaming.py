"""
Flask streaming server for processed video feed.

Arsitektur:
  - Edge worker mendeteksi + tracking manusia dari kamera sumber
  - Frame yang sudah di-overlay (bounding box, ROI, info) disimpan ke `latest_frame`
  - Flask server menyajikan frame tersebut sebagai MJPEG stream di /video_feed
  - Frontend dashboard menggunakan endpoint ini untuk live preview

Ini BUKAN server kamera mentah. Ini server video yang sudah diproses YOLO.
Untuk kamera mentah (webcam), edge worker langsung membaca dari OpenCV
tanpa perlu server terpisah (rstp_webcam_server.py).
"""
import time
import threading
from flask import Flask, Response, jsonify
from flask_cors import CORS

from .config import (
    EDGE_STREAM_ALLOW_ORIGIN,
    EDGE_STREAM_HOST,
    EDGE_STREAM_JPEG_QUALITY,
    EDGE_STREAM_MAX_FPS,
    EDGE_STREAM_PORT,
    EDGE_STREAM_URL,
)
from .logger import get_logger

log = get_logger("stream")

# Global variable for sharing latest frame with stream server
latest_frame = None        # processed frame (with ROI, bboxes, info overlay)
latest_frame_raw = None     # raw frame (no overlay) for ROI editor
_latest_jpeg = None         # pre-encoded JPEG bytes (processed)
_latest_jpeg_raw = None     # pre-encoded JPEG bytes (raw)
frame_lock = threading.Lock()
frame_condition = threading.Condition(frame_lock)
_frame_count = 0
_last_frame_time = 0.0
_frame_version = 0
_processed_clients = 0
_raw_clients = 0

# Flask app for streaming
flask_app = Flask(__name__)
CORS(flask_app, resources={
    r"/*": {
        "origins": EDGE_STREAM_ALLOW_ORIGIN,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": False,
        "max_age": 3600
    }
})


def gen_frames(raw=False):
    """Generate MJPEG stream frames from pre-encoded JPEG bytes"""
    label = "raw" if raw else "processed"
    log.debug("Client connected to video feed (%s)", label)
    target_interval = 1.0 / EDGE_STREAM_MAX_FPS if EDGE_STREAM_MAX_FPS > 0 else 0.0
    next_send_at = 0.0
    last_version = -1

    global _processed_clients, _raw_clients
    with frame_condition:
        if raw:
            _raw_clients += 1
        else:
            _processed_clients += 1

    try:
        while True:
            with frame_condition:
                frame_condition.wait_for(
                    lambda: (
                        (_latest_jpeg_raw if raw else _latest_jpeg) is not None
                        and _frame_version != last_version
                    ),
                    timeout=1.0,
                )
                jpeg_bytes = _latest_jpeg_raw if raw else _latest_jpeg
                version = _frame_version

            if jpeg_bytes is None or version == last_version:
                continue

            if target_interval > 0.0:
                now = time.monotonic()
                if next_send_at > now:
                    time.sleep(next_send_at - now)
                next_send_at = max(next_send_at, time.monotonic()) + target_interval

            last_version = version
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
            )
    finally:
        with frame_condition:
            if raw:
                _raw_clients = max(0, _raw_clients - 1)
            else:
                _processed_clients = max(0, _processed_clients - 1)
        log.debug("Client disconnected from video feed (%s)", label)


@flask_app.route('/video_feed')
def video_feed():
    """MJPEG stream endpoint — frame sudah diproses YOLO+tracking"""
    response = Response(
        gen_frames(raw=False),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )
    response.headers["Access-Control-Allow-Origin"] = EDGE_STREAM_ALLOW_ORIGIN
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@flask_app.route('/video_feed_raw')
def video_feed_raw():
    """MJPEG stream endpoint — frame TANPA overlay (untuk ROI editor)"""
    response = Response(
        gen_frames(raw=True),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )
    response.headers["Access-Control-Allow-Origin"] = EDGE_STREAM_ALLOW_ORIGIN
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@flask_app.route('/health')
def health():
    """Health check endpoint untuk frontend"""
    global _frame_count, _last_frame_time
    has_frame = latest_frame is not None
    age_ms = int(max(0.0, time.time() - _last_frame_time) * 1000) if has_frame else None
    return jsonify({
        "status": "ok" if has_frame else "waiting",
        "camera_source": EDGE_STREAM_URL or "not configured",
        "has_frame": has_frame,
        "stream_endpoint": "/video_feed",
        "frame_age_ms": age_ms,
        "jpeg_quality": EDGE_STREAM_JPEG_QUALITY,
        "max_fps": EDGE_STREAM_MAX_FPS or "worker-rate",
        "processed_clients": _processed_clients,
        "raw_clients": _raw_clients,
    })


@flask_app.route('/health', methods=['OPTIONS'])
@flask_app.route('/video_feed', methods=['OPTIONS'])
@flask_app.route('/video_feed_raw', methods=['OPTIONS'])
def handle_options():
    """Handle CORS preflight requests"""
    response = flask_app.make_default_options_response()
    response.headers['Access-Control-Allow-Origin'] = EDGE_STREAM_ALLOW_ORIGIN
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


def start_flask_server():
    """Start Flask server in background thread"""
    log.info(
        "Starting processed video server on http://%s:%d/video_feed",
        EDGE_STREAM_HOST, EDGE_STREAM_PORT,
    )
    flask_app.run(
        host=EDGE_STREAM_HOST,
        port=EDGE_STREAM_PORT,
        threaded=True,
        debug=False,
        use_reloader=False,
    )


def update_latest_frame(frame, raw_frame=None):
    """Update the global latest frame (thread-safe)
    
    Pre-encodes JPEG once so all streaming clients share the same bytes
    instead of each client encoding independently.
    
    Args:
        frame: Processed frame with ROI, bboxes, info overlay
        raw_frame: Raw frame without any overlay (for ROI editor)
    """
    import cv2
    global latest_frame, latest_frame_raw, _latest_jpeg, _latest_jpeg_raw
    global _frame_count, _last_frame_time, _frame_version

    encode_params = [cv2.IMWRITE_JPEG_QUALITY, EDGE_STREAM_JPEG_QUALITY]

    # Pre-encode processed frame
    ret, buf = cv2.imencode(".jpg", frame, encode_params)
    jpeg = buf.tobytes() if ret else None

    # Pre-encode raw frame if provided
    jpeg_raw = None
    if raw_frame is not None:
        ret_raw, buf_raw = cv2.imencode(".jpg", raw_frame, encode_params)
        jpeg_raw = buf_raw.tobytes() if ret_raw else None

    with frame_condition:
        latest_frame = frame
        _latest_jpeg = jpeg
        if raw_frame is not None:
            latest_frame_raw = raw_frame
            _latest_jpeg_raw = jpeg_raw
        _frame_count += 1
        _last_frame_time = time.time()
        _frame_version += 1
        frame_condition.notify_all()


def has_raw_stream_clients() -> bool:
    """Return whether the raw feed currently has any connected clients."""
    with frame_lock:
        return _raw_clients > 0
