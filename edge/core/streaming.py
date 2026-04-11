"""
WebRTC-first streaming server for processed video feed.

Arsitektur:
  - Edge worker membaca frame kamera dan menggambar overlay YOLO/tracking.
  - Frame terbaru disimpan di memori sebagai numpy array.
  - Browser menerima hasil proses utama lewat WebRTC video track.
  - Endpoint MJPEG tetap disediakan sebagai fallback dan untuk ROI editor.
"""
import asyncio
import contextlib
import json
import threading
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import (
    EDGE_STREAM_ALLOW_ORIGIN,
    EDGE_STREAM_HOST,
    EDGE_STREAM_JPEG_QUALITY,
    EDGE_STREAM_MAX_FPS,
    EDGE_STREAM_PORT,
    EDGE_STREAM_URL,
    EDGE_WEBRTC_ENABLED,
    EDGE_WEBRTC_ICE_SERVERS,
)
from .logger import get_logger

try:
    from aiortc import (
        RTCConfiguration,
        RTCIceServer,
        RTCPeerConnection,
        RTCSessionDescription,
        VideoStreamTrack,
    )
    from av import VideoFrame

    AIORTC_AVAILABLE = True
    AIORTC_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - depends on optional runtime package
    RTCConfiguration = None
    RTCIceServer = None
    RTCPeerConnection = None
    RTCSessionDescription = None
    VideoStreamTrack = object
    VideoFrame = None
    AIORTC_AVAILABLE = False
    AIORTC_IMPORT_ERROR = str(exc)

log = get_logger("stream")
DEFAULT_ICE_SERVER_URLS = ("stun:stun.l.google.com:19302",)


def _parse_allow_origins(raw_value: str) -> List[str]:
    value = (raw_value or "*").strip()
    if value == "*":
        return ["*"]
    return [item.strip() for item in value.split(",") if item.strip()] or ["*"]


def _parse_ice_server_payloads(raw_value: str) -> List[Dict[str, object]]:
    value = (raw_value or "").strip()
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [{"urls": item.strip()} for item in value.split(",") if item.strip()]

    if isinstance(parsed, str):
        return [{"urls": parsed}]

    if isinstance(parsed, list):
        payloads: List[Dict[str, object]] = []
        for item in parsed:
            if isinstance(item, str):
                payloads.append({"urls": item})
            elif isinstance(item, dict) and item.get("urls"):
                payloads.append(
                    {
                        "urls": item["urls"],
                        "username": item.get("username"),
                        "credential": item.get("credential"),
                    }
                )
        return payloads

    return []


def _build_rtc_ice_servers(payloads: List[Dict[str, object]]) -> List["RTCIceServer"]:
    if not AIORTC_AVAILABLE:
        return []

    ice_servers = []
    for item in payloads:
        kwargs = {"urls": item["urls"]}
        if item.get("username"):
            kwargs["username"] = item["username"]
        if item.get("credential"):
            kwargs["credential"] = item["credential"]
        ice_servers.append(RTCIceServer(**kwargs))
    return ice_servers


def _default_ice_server_payloads() -> List[Dict[str, object]]:
    return [{"urls": url} for url in DEFAULT_ICE_SERVER_URLS]


def _sanitize_offer_sdp(sdp: str) -> Tuple[str, int]:
    """Drop mDNS `.local` candidates which aiortc cannot reliably resolve on many hosts."""
    removed = 0
    filtered_lines = []

    for line in sdp.replace("\r\n", "\n").split("\n"):
        candidate = line.strip().lower()
        if candidate.startswith("a=candidate:") and ".local" in candidate:
            removed += 1
            continue
        filtered_lines.append(line)

    sanitized = "\r\n".join(filtered_lines).strip()
    if sanitized:
        sanitized += "\r\n"
    return sanitized, removed


_allow_origins = _parse_allow_origins(EDGE_STREAM_ALLOW_ORIGIN)
_ice_server_payloads = _parse_ice_server_payloads(EDGE_WEBRTC_ICE_SERVERS)
_ice_server_source = "env"
if not _ice_server_payloads:
    _ice_server_payloads = _default_ice_server_payloads()
    _ice_server_source = "default"
_rtc_ice_servers = _build_rtc_ice_servers(_ice_server_payloads)


# Shared frame state
latest_frame: Optional[np.ndarray] = None
latest_frame_raw: Optional[np.ndarray] = None
_latest_jpeg: Optional[bytes] = None
_latest_jpeg_raw: Optional[bytes] = None
frame_lock = threading.Lock()
frame_condition = threading.Condition(frame_lock)
_frame_count = 0
_last_frame_time = 0.0
_frame_version = 0
_processed_clients = 0
_raw_clients = 0
_webrtc_viewers = 0
_peer_connections: set = set()


def _webrtc_disabled_reason() -> str:
    if not EDGE_WEBRTC_ENABLED:
        return "disabled by EDGE_WEBRTC_ENABLED"
    if not AIORTC_AVAILABLE:
        return f"aiortc unavailable: {AIORTC_IMPORT_ERROR}"
    return ""


def webrtc_available() -> bool:
    return not _webrtc_disabled_reason()


def _mjpeg_headers() -> Dict[str, str]:
    return {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Accel-Buffering": "no",
    }


def _wait_for_jpeg(last_version: int, raw: bool, timeout: float) -> Tuple[Optional[bytes], int]:
    with frame_condition:
        frame_condition.wait_for(
            lambda: (
                (_latest_jpeg_raw if raw else _latest_jpeg) is not None
                and _frame_version != last_version
            ),
            timeout=timeout,
        )
        jpeg = _latest_jpeg_raw if raw else _latest_jpeg
        version = _frame_version
    return jpeg, version


def _wait_for_frame(last_version: int, timeout: float = 1.0) -> Tuple[Optional[np.ndarray], int]:
    with frame_condition:
        frame_condition.wait_for(
            lambda: latest_frame is not None and _frame_version != last_version,
            timeout=timeout,
        )
        frame = latest_frame
        version = _frame_version
    return frame, version


def gen_frames(raw: bool = False):
    """Generate MJPEG stream frames from pre-encoded JPEG bytes."""
    label = "raw" if raw else "processed"
    log.debug("Client connected to MJPEG feed (%s)", label)
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
            jpeg_bytes, version = _wait_for_jpeg(last_version=last_version, raw=raw, timeout=1.0)
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
        log.debug("Client disconnected from MJPEG feed (%s)", label)


if AIORTC_AVAILABLE:

    class LatestProcessedVideoTrack(VideoStreamTrack):
        """WebRTC track that always sends the freshest processed frame."""

        def __init__(self):
            super().__init__()
            self._last_version = -1

        async def recv(self):
            pts, time_base = await self.next_timestamp()
            frame, version = await asyncio.to_thread(_wait_for_frame, self._last_version, 1.0)
            if frame is None:
                frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            else:
                frame = np.ascontiguousarray(frame)

            self._last_version = version
            video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
            video_frame.pts = pts
            video_frame.time_base = time_base
            return video_frame

else:

    class LatestProcessedVideoTrack:  # pragma: no cover - only used if aiortc missing
        pass


class WebRTCOffer(BaseModel):
    sdp: str
    type: str


stream_app = FastAPI(title="Edge Video Server", version="2.0.0")
stream_app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@stream_app.get("/video_feed")
def video_feed():
    """MJPEG fallback endpoint for processed YOLO+tracking frames."""
    return StreamingResponse(
        gen_frames(raw=False),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=_mjpeg_headers(),
    )


@stream_app.get("/video_feed_raw")
def video_feed_raw():
    """MJPEG endpoint for raw frames without overlay (used by ROI editor)."""
    return StreamingResponse(
        gen_frames(raw=True),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=_mjpeg_headers(),
    )


@stream_app.post("/webrtc/offer")
async def webrtc_offer(payload: WebRTCOffer):
    """Create a recvonly WebRTC session for the processed video track."""
    global _webrtc_viewers

    if not webrtc_available():
        raise HTTPException(status_code=503, detail=_webrtc_disabled_reason())

    if payload.type != "offer":
        raise HTTPException(status_code=400, detail="Expected SDP offer")

    configuration = RTCConfiguration(iceServers=_rtc_ice_servers)
    pc = RTCPeerConnection(configuration=configuration)
    pc_id = f"viewer-{id(pc)}"
    _peer_connections.add(pc)
    _webrtc_viewers = len(_peer_connections)
    log.info("WebRTC viewer connected: %s", pc_id)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        global _webrtc_viewers
        log.info("WebRTC state %s -> %s", pc_id, pc.connectionState)
        if pc.connectionState in {"failed", "closed", "disconnected"}:
            _peer_connections.discard(pc)
            _webrtc_viewers = len(_peer_connections)
            with contextlib.suppress(Exception):
                await pc.close()

    try:
        remote_sdp, removed_mdns = _sanitize_offer_sdp(payload.sdp)
        if removed_mdns:
            log.info(
                "Stripped %d mDNS ICE candidate(s) from browser offer; STUN/TURN candidate(s) will be used instead.",
                removed_mdns,
            )

        pc.addTrack(LatestProcessedVideoTrack())
        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=remote_sdp, type=payload.type)
        )
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        local = pc.localDescription
        if local is None:
            raise HTTPException(status_code=500, detail="Failed to create WebRTC answer")

        return {"sdp": local.sdp, "type": local.type}
    except Exception:
        _peer_connections.discard(pc)
        _webrtc_viewers = len(_peer_connections)
        with contextlib.suppress(Exception):
            await pc.close()
        raise


@stream_app.get("/health")
def health():
    """Health check endpoint for frontend stream negotiation."""
    with frame_condition:
        has_frame = latest_frame is not None
        age_ms = int(max(0.0, time.time() - _last_frame_time) * 1000) if has_frame else None
        frame_count = _frame_count
        mjpeg_processed_clients = _processed_clients
        mjpeg_raw_clients = _raw_clients

    return {
        "status": "ok" if has_frame else "waiting",
        "camera_source": EDGE_STREAM_URL or "not configured",
        "has_frame": has_frame,
        "frame_age_ms": age_ms,
        "frame_count": frame_count,
        "mjpeg_fallback_endpoint": "/video_feed",
        "raw_stream_endpoint": "/video_feed_raw",
        "jpeg_quality": EDGE_STREAM_JPEG_QUALITY,
        "max_fps": EDGE_STREAM_MAX_FPS or "worker-rate",
        "mjpeg_processed_clients": mjpeg_processed_clients,
        "mjpeg_raw_clients": mjpeg_raw_clients,
        "webrtc_enabled": webrtc_available(),
        "webrtc_offer_endpoint": "/webrtc/offer",
        "webrtc_ice_servers": _ice_server_payloads,
        "webrtc_ice_source": _ice_server_source,
        "webrtc_viewers": _webrtc_viewers,
        "webrtc_disabled_reason": _webrtc_disabled_reason() or None,
    }


@stream_app.on_event("shutdown")
async def shutdown_event():
    """Close any remaining peer connections during server shutdown."""
    global _webrtc_viewers
    for pc in list(_peer_connections):
        with contextlib.suppress(Exception):
            await pc.close()
    _peer_connections.clear()
    _webrtc_viewers = 0


def start_flask_server():
    """Backward-compatible entry point for the edge video server."""
    log.info(
        "Starting edge video server on http://%s:%d (WebRTC offer: /webrtc/offer, MJPEG fallback: /video_feed)",
        EDGE_STREAM_HOST,
        EDGE_STREAM_PORT,
    )
    uvicorn.run(
        stream_app,
        host=EDGE_STREAM_HOST,
        port=EDGE_STREAM_PORT,
        log_level="info",
        access_log=False,
    )


def update_latest_frame(frame, raw_frame=None):
    """Update the shared frame buffers for WebRTC and MJPEG clients."""
    import cv2

    global latest_frame, latest_frame_raw, _latest_jpeg, _latest_jpeg_raw
    global _frame_count, _last_frame_time, _frame_version

    encode_params = [cv2.IMWRITE_JPEG_QUALITY, EDGE_STREAM_JPEG_QUALITY]
    with frame_condition:
        processed_clients = _processed_clients
        raw_clients = _raw_clients

    processed_jpeg = None
    raw_jpeg = None

    if processed_clients > 0:
        ret, buf = cv2.imencode(".jpg", frame, encode_params)
        processed_jpeg = buf.tobytes() if ret else None

    if raw_frame is not None and raw_clients > 0:
        ret_raw, buf_raw = cv2.imencode(".jpg", raw_frame, encode_params)
        raw_jpeg = buf_raw.tobytes() if ret_raw else None

    with frame_condition:
        latest_frame = frame
        _latest_jpeg = processed_jpeg

        if raw_frame is not None:
            latest_frame_raw = raw_frame
        _latest_jpeg_raw = raw_jpeg

        _frame_count += 1
        _last_frame_time = time.time()
        _frame_version += 1
        frame_condition.notify_all()


def has_raw_stream_clients() -> bool:
    """Return whether the raw MJPEG feed currently has any connected clients."""
    with frame_condition:
        return _raw_clients > 0
