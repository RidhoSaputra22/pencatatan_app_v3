import os
import threading
import time
from pathlib import Path

import cv2
from flask import Flask, Response, jsonify

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
SOURCE_VALUE = os.getenv("RTSP_SOURCE", "cctv-footage-1.mp4").strip()
SERVER_PORT = int(os.getenv("RTSP_SERVER_PORT", "7000"))
JPEG_QUALITY = max(50, min(95, int(os.getenv("RTSP_JPEG_QUALITY", "75"))))
TARGET_FPS = float(os.getenv("RTSP_TARGET_FPS", "0") or "0")

_latest_frame = None
_latest_jpeg = None
_frame_version = 0
_last_frame_time = 0.0
_frame_condition = threading.Condition()


def _resolve_source(value: str):
    if value.isdigit():
        return int(value)

    source_path = Path(value)
    if not source_path.is_absolute():
        source_path = BASE_DIR / source_path

    return str(source_path) if source_path.exists() else value


def _is_file_source(source) -> bool:
    return isinstance(source, str) and Path(source).exists()


def _open_capture(source):
    capture = cv2.VideoCapture(source)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


def _source_interval(capture, source) -> float:
    if TARGET_FPS > 0:
        return 1.0 / TARGET_FPS

    if not _is_file_source(source):
        return 0.0

    fps = capture.get(cv2.CAP_PROP_FPS)
    if fps and 1.0 <= fps <= 120.0:
        return 1.0 / fps
    return 1.0 / 25.0


def _reader_loop():
    global _latest_frame, _latest_jpeg, _frame_version, _last_frame_time

    source = _resolve_source(SOURCE_VALUE)
    print(f"[rtsp] Opening source: {source}")

    capture = None
    frame_interval = 0.0

    while True:
        loop_started = time.monotonic()

        if capture is None or not capture.isOpened():
            capture = _open_capture(source)
            if not capture.isOpened():
                print("[rtsp] Failed to open source. Retrying in 2s...")
                capture.release()
                capture = None
                time.sleep(2)
                continue
            frame_interval = _source_interval(capture, source)
            print(
                f"[rtsp] Source ready. jpeg_quality={JPEG_QUALITY}, "
                f"target_fps={'source-rate' if frame_interval == 0.0 else round(1.0 / frame_interval, 2)}"
            )

        ok, frame = capture.read()
        if not ok or frame is None:
            if _is_file_source(source):
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            print("[rtsp] Frame read failed. Reconnecting...")
            capture.release()
            capture = None
            time.sleep(1)
            continue

        ok, buffer = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY],
        )
        if not ok:
            continue

        frame_bytes = buffer.tobytes()
        with _frame_condition:
            _latest_frame = frame
            _latest_jpeg = frame_bytes
            _frame_version += 1
            _last_frame_time = time.time()
            _frame_condition.notify_all()

        if frame_interval > 0.0:
            elapsed = time.monotonic() - loop_started
            sleep_for = frame_interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)


def generate_frames():
    last_version = -1

    while True:
        with _frame_condition:
            _frame_condition.wait_for(
                lambda: _latest_jpeg is not None and _frame_version != last_version,
                timeout=1.0,
            )
            frame_bytes = _latest_jpeg
            version = _frame_version

        if frame_bytes is None or version == last_version:
            continue

        last_version = version
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )


@app.route("/")
def index():
    return "Video Stream Server Running"


@app.route("/health")
def health():
    has_frame = _latest_frame is not None
    frame_age_ms = int(max(0.0, time.time() - _last_frame_time) * 1000) if has_frame else None
    return jsonify(
        {
            "status": "ok" if has_frame else "waiting",
            "source": str(_resolve_source(SOURCE_VALUE)),
            "has_frame": has_frame,
            "frame_age_ms": frame_age_ms,
            "jpeg_quality": JPEG_QUALITY,
            "target_fps": TARGET_FPS or "source-rate",
        }
    )


@app.route("/video")
def video():
    response = Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Accel-Buffering"] = "no"
    return response


if __name__ == "__main__":
    reader_thread = threading.Thread(target=_reader_loop, daemon=True)
    reader_thread.start()
    app.run(host="0.0.0.0", port=SERVER_PORT, debug=False, threaded=True, use_reloader=False)
