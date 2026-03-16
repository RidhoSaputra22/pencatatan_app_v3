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

from .config import EDGE_STREAM_PORT, EDGE_STREAM_URL

# Global variable for sharing latest frame with stream server
latest_frame = None        # processed frame (with ROI, bboxes, info overlay)
latest_frame_raw = None     # raw frame (no overlay) for ROI editor
frame_lock = threading.Lock()
_frame_count = 0
_last_frame_time = 0.0

# Flask app for streaming
flask_app = Flask(__name__)
CORS(flask_app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": False,
        "max_age": 3600
    }
})


def gen_frames(raw=False):
    """Generate MJPEG stream frames from shared worker frame"""
    import cv2
    label = "raw" if raw else "processed"
    print(f"[stream] Client connected to video feed ({label})")
    while True:
        with frame_lock:
            if raw:
                frame = latest_frame_raw.copy() if latest_frame_raw is not None else None
            else:
                frame = latest_frame.copy() if latest_frame is not None else None

        if frame is None:
            time.sleep(0.05)
            continue

        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        # ~25 fps max to save bandwidth
        time.sleep(0.04)


@flask_app.route('/video_feed')
def video_feed():
    """MJPEG stream endpoint — frame sudah diproses YOLO+tracking"""
    response = Response(gen_frames(raw=False),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@flask_app.route('/video_feed_raw')
def video_feed_raw():
    """MJPEG stream endpoint — frame TANPA overlay (untuk ROI editor)"""
    response = Response(gen_frames(raw=True),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@flask_app.route('/health')
def health():
    """Health check endpoint untuk frontend"""
    global _frame_count, _last_frame_time
    has_frame = latest_frame is not None
    return jsonify({
        'status': 'ok' if has_frame else 'waiting',
        'camera_source': EDGE_STREAM_URL or 'not configured',
        'has_frame': has_frame,
        'stream_endpoint': '/video_feed',
    })


@flask_app.route('/health', methods=['OPTIONS'])
@flask_app.route('/video_feed', methods=['OPTIONS'])
@flask_app.route('/video_feed_raw', methods=['OPTIONS'])
def handle_options():
    """Handle CORS preflight requests"""
    response = flask_app.make_default_options_response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


def start_flask_server():
    """Start Flask server in background thread"""
    print(f"[stream] Starting processed video server on http://0.0.0.0:{EDGE_STREAM_PORT}/video_feed")
    flask_app.run(host='0.0.0.0', port=EDGE_STREAM_PORT, threaded=True, debug=False)


def update_latest_frame(frame, raw_frame=None):
    """Update the global latest frame (thread-safe)
    
    Args:
        frame: Processed frame with ROI, bboxes, info overlay
        raw_frame: Raw frame without any overlay (for ROI editor)
    """
    global latest_frame, latest_frame_raw, _frame_count, _last_frame_time
    with frame_lock:
        latest_frame = frame.copy()
        if raw_frame is not None:
            latest_frame_raw = raw_frame.copy()
        _frame_count += 1
        _last_frame_time = time.time()
