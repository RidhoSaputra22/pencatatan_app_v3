"""
UDP Stream Receiver & MJPEG Relay.

Menerima frame JPEG dari client via UDP dan menyajikannya sebagai
HTTP MJPEG stream agar edge worker (YOLOv5) bisa membacanya.

Arsitektur:
  Client (UDP) ──→ Backend (module ini) ──→ /stream/relay (MJPEG)
                                                  ↓
                                          Edge Worker (YOLO)
"""
import struct
import socket
import threading
import time
from typing import Optional

import cv2
import numpy as np

# ---------- Shared frame state ----------
_latest_frame: Optional[np.ndarray] = None
_latest_jpeg: Optional[bytes] = None
_frame_version = 0
_last_frame_time = 0.0
_receiver_running = False
_lock = threading.Lock()
_condition = threading.Condition(_lock)


def get_relay_state():
    """Return current receiver state for health-checks."""
    with _lock:
        has_frame = _latest_frame is not None
        age_ms = int((time.time() - _last_frame_time) * 1000) if has_frame else None
        return {
            "receiving": _receiver_running,
            "has_frame": has_frame,
            "frame_age_ms": age_ms,
            "frame_version": _frame_version,
        }


def get_latest_relay_frame():
    """Return latest JPEG bytes (or None)."""
    with _lock:
        return _latest_jpeg


# ---------- UDP Receiver ----------

# Buffer for reassembling chunked frames
_frame_buffers: dict = {}
_BUFFER_TTL = 2.0  # seconds — drop incomplete frames older than this


def _cleanup_stale_buffers(now: float):
    """Remove frame buffers that are too old to avoid memory leaks."""
    stale = [fid for fid, info in _frame_buffers.items() if now - info["ts"] > _BUFFER_TTL]
    for fid in stale:
        del _frame_buffers[fid]


def _udp_receiver(host: str, port: int, stop_event: threading.Event):
    """
    Receive UDP frames from client and decode into numpy/JPEG.
    
    Packet format from client:
      [frame_id: uint32][total_chunks: uint16][chunk_idx: uint16][jpeg_data...]
    """
    global _latest_frame, _latest_jpeg, _frame_version, _last_frame_time, _receiver_running

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)  # 4MB buffer
    sock.settimeout(1.0)
    sock.bind((host, port))

    print(f"[stream-relay] UDP receiver listening on {host}:{port}")
    _receiver_running = True

    header_size = struct.calcsize("!IHH")  # 8 bytes
    last_cleanup = time.time()

    try:
        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue

            if len(data) < header_size:
                continue

            frame_id, total_chunks, chunk_idx = struct.unpack("!IHH", data[:header_size])
            chunk_data = data[header_size:]

            now = time.time()

            # Periodic cleanup of stale buffers
            if now - last_cleanup > 1.0:
                _cleanup_stale_buffers(now)
                last_cleanup = now

            if total_chunks == 1:
                # Single-chunk frame — fast path
                jpeg_data = chunk_data
            else:
                # Multi-chunk frame — reassemble
                if frame_id not in _frame_buffers:
                    _frame_buffers[frame_id] = {
                        "chunks": {},
                        "total": total_chunks,
                        "ts": now,
                    }

                buf = _frame_buffers[frame_id]
                buf["chunks"][chunk_idx] = chunk_data

                if len(buf["chunks"]) < total_chunks:
                    continue  # Not all chunks received yet

                # All chunks received — reassemble
                jpeg_data = b""
                for i in range(total_chunks):
                    if i not in buf["chunks"]:
                        jpeg_data = None
                        break
                    jpeg_data += buf["chunks"][i]

                del _frame_buffers[frame_id]

                if jpeg_data is None:
                    continue

            # Decode JPEG to numpy
            np_arr = np.frombuffer(jpeg_data, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is None:
                continue

            with _condition:
                _latest_frame = frame
                _latest_jpeg = jpeg_data
                _frame_version += 1
                _last_frame_time = time.time()
                _condition.notify_all()

    except Exception as e:
        print(f"[stream-relay] UDP receiver error: {e}")
    finally:
        _receiver_running = False
        sock.close()
        print("[stream-relay] UDP receiver stopped.")


# ---------- MJPEG Generator ----------

def generate_relay_frames():
    """Generate MJPEG frames for HTTP streaming to edge worker."""
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


# ---------- Start / Stop ----------

_stop_event: Optional[threading.Event] = None
_receiver_thread: Optional[threading.Thread] = None


def start_udp_receiver(host: str = "0.0.0.0", port: int = 9999):
    """Start UDP receiver in a background thread."""
    global _stop_event, _receiver_thread

    if _receiver_thread is not None and _receiver_thread.is_alive():
        print("[stream-relay] UDP receiver already running.")
        return

    _stop_event = threading.Event()
    _receiver_thread = threading.Thread(
        target=_udp_receiver,
        args=(host, port, _stop_event),
        daemon=True,
        name="udp-stream-receiver",
    )
    _receiver_thread.start()


def stop_udp_receiver():
    """Signal the receiver to stop."""
    global _stop_event
    if _stop_event is not None:
        _stop_event.set()
