"""Async capture utilities that keep only the freshest camera frame."""
import os
import threading
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np

from .logger import get_logger

log = get_logger("capture")


def is_video_file(source: str) -> bool:
    """Check if the source is a local video file (not a stream or webcam index)."""
    if source.isdigit():
        return False
    if source.startswith(("rtsp://", "http://", "https://")):
        return False
    return os.path.isfile(source)


def open_video_capture(source: str):
    """
    Open video capture for webcam index, HTTP stream, RTSP stream, or video file.
    Applies a small buffer where supported.
    """
    if source.isdigit():
        idx = int(source)
        log.info("Opening webcam index %d directly", idx)
        for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
            capture = cv2.VideoCapture(idx, backend)
            if capture.isOpened():
                log.info("Webcam opened with backend: %s", backend)
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                return capture
        capture = cv2.VideoCapture(idx)
    elif is_video_file(source):
        log.info("Opening video file: %s", source)
        capture = cv2.VideoCapture(source)
    else:
        # Network stream (HTTP/RTSP): set timeouts so capture.read() never blocks
        # indefinitely. Without these, calling capture.release() while the reader
        # thread is blocked in capture.read() causes a SIGSEGV in FFmpeg internals.
        capture = cv2.VideoCapture(source)
        capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10_000)  # 10 s connect timeout
        capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3_000)   # 3 s per-frame timeout

    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


class LatestFrameCapture:
    """Background reader that continually replaces buffered frames with the newest one."""

    def __init__(self, source: str):
        self.source = source
        self._is_file = is_video_file(source)
        self._capture = None
        self._thread = None
        self._frame = None
        self._frame_id = 0
        self._running = False
        self._read_failed = False
        self._file_ended = False
        self._condition = threading.Condition()
        self._pending_releases: List[Tuple[threading.Thread, Any]] = []

    def start(self) -> bool:
        """Open the source and start the reader thread."""
        self._reap_pending_releases()
        self.release()

        capture = open_video_capture(self.source)
        if not capture.isOpened():
            try:
                capture.release()
            except Exception:
                pass
            return False

        self._capture = capture
        self._frame = None
        self._frame_id = 0
        self._running = True
        self._read_failed = False
        self._file_ended = False
        self._thread = threading.Thread(
            target=self._reader_loop,
            name="latest-frame-capture",
            daemon=True,
        )
        self._thread.start()
        return True

    def isOpened(self) -> bool:
        """Mirror the cv2.VideoCapture API used by the worker loop."""
        self._reap_pending_releases()
        return bool(
            self._capture is not None
            and self._capture.isOpened()
            and self._running
            and not self._read_failed
        )

    @property
    def file_ended(self) -> bool:
        """Return True if a video file reached the end."""
        return self._file_ended

    def read(
        self,
        last_frame_id: int = 0,
        timeout: float = 1.0,
    ) -> Tuple[bool, Optional[np.ndarray], int]:
        """
        Wait for a newer frame than `last_frame_id` and return it.
        Old buffered frames are skipped automatically because only the latest one is retained.
        """
        self._reap_pending_releases()
        with self._condition:
            self._condition.wait_for(
                lambda: (
                    self._frame_id != last_frame_id
                    or self._read_failed
                    or self._file_ended
                    or not self._running
                ),
                timeout=timeout,
            )

            if self._frame_id == last_frame_id or self._frame is None:
                return False, None, last_frame_id

            return True, self._frame, self._frame_id

    def release(self) -> None:
        """Stop the reader thread and release the underlying capture."""
        self._reap_pending_releases()
        capture = None
        thread = None
        with self._condition:
            if self._capture is None and self._thread is None:
                return
            self._running = False
            capture = self._capture
            thread = self._thread
            self._capture = None
            self._thread = None
            self._frame = None
            self._read_failed = False
            self._file_ended = False
            self._condition.notify_all()

        # Join the reader thread BEFORE releasing the capture.
        # If the thread is blocked inside capture.read() (e.g. waiting on an HTTP
        # relay), calling capture.release() concurrently tears down FFmpeg's internal
        # state and causes a SIGSEGV. With CAP_PROP_READ_TIMEOUT_MSEC set on network
        # sources the blocked read() returns within that window, the thread sees
        # _running=False and exits cleanly — then we can safely release the capture.
        timed_out = False
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
            if thread.is_alive():
                timed_out = True
                log.warning(
                    "Reader thread did not exit in time; delaying capture release to avoid native crash"
                )

        if capture is not None and timed_out and thread is not None:
            self._pending_releases.append((thread, capture))
            return

        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass

    def _reap_pending_releases(self) -> None:
        """Release old captures only after their reader threads have actually exited."""
        if not self._pending_releases:
            return

        pending: List[Tuple[threading.Thread, Any]] = []
        for thread, capture in self._pending_releases:
            if thread.is_alive():
                pending.append((thread, capture))
                continue

            try:
                capture.release()
            except Exception:
                pass

        if pending and len(pending) != len(self._pending_releases):
            log.info("Released %d deferred capture(s)", len(self._pending_releases) - len(pending))
        elif pending and len(pending) >= 3:
            log.warning(
                "Still waiting for %d capture reader thread(s) to exit cleanly",
                len(pending),
            )

        self._pending_releases = pending

    def _reader_loop(self) -> None:
        capture = self._capture
        if capture is None:
            return

        while True:
            ok, frame = capture.read()
            with self._condition:
                if not self._running:
                    return

                if not ok or frame is None:
                    if self._is_file:
                        # Video file ended — signal file_ended and stop
                        self._file_ended = True
                        self._condition.notify_all()
                        log.info("Video file ended.")
                        return
                    self._read_failed = True
                    self._condition.notify_all()
                    return

                self._frame = frame
                self._frame_id += 1
                self._condition.notify_all()

            # For video files, pace the read to ~30fps to simulate real-time
            if self._is_file:
                import time
                fps = capture.get(cv2.CAP_PROP_FPS)
                if fps > 0:
                    time.sleep(1.0 / fps)
                else:
                    time.sleep(1.0 / 30.0)
