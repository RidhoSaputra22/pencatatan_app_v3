"""Async capture utilities that keep only the freshest camera frame."""
import threading
from typing import Optional, Tuple

import cv2
import numpy as np


def open_video_capture(source: str):
    """
    Open video capture for webcam index, HTTP stream, or RTSP stream.
    Applies a small buffer where supported.
    """
    if source.isdigit():
        idx = int(source)
        print(f"[capture] Opening webcam index {idx} directly")
        for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
            capture = cv2.VideoCapture(idx, backend)
            if capture.isOpened():
                print(f"[capture] Webcam opened with backend: {backend}")
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                return capture
        capture = cv2.VideoCapture(idx)
    else:
        capture = cv2.VideoCapture(source)

    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


class LatestFrameCapture:
    """Background reader that continually replaces buffered frames with the newest one."""

    def __init__(self, source: str):
        self.source = source
        self._capture = None
        self._thread = None
        self._frame = None
        self._frame_id = 0
        self._running = False
        self._read_failed = False
        self._condition = threading.Condition()

    def start(self) -> bool:
        """Open the source and start the reader thread."""
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
        self._thread = threading.Thread(
            target=self._reader_loop,
            name="latest-frame-capture",
            daemon=True,
        )
        self._thread.start()
        return True

    def isOpened(self) -> bool:
        """Mirror the cv2.VideoCapture API used by the worker loop."""
        return bool(
            self._capture is not None
            and self._capture.isOpened()
            and self._running
            and not self._read_failed
        )

    def read(
        self,
        last_frame_id: int = 0,
        timeout: float = 1.0,
    ) -> Tuple[bool, Optional[np.ndarray], int]:
        """
        Wait for a newer frame than `last_frame_id` and return it.
        Old buffered frames are skipped automatically because only the latest one is retained.
        """
        with self._condition:
            self._condition.wait_for(
                lambda: (
                    self._frame_id != last_frame_id
                    or self._read_failed
                    or not self._running
                ),
                timeout=timeout,
            )

            if self._frame_id == last_frame_id or self._frame is None:
                return False, None, last_frame_id

            return True, self._frame, self._frame_id

    def release(self) -> None:
        """Stop the reader thread and release the underlying capture."""
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
            self._condition.notify_all()

        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass

        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

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
                    self._read_failed = True
                    self._condition.notify_all()
                    return

                self._frame = frame
                self._frame_id += 1
                self._condition.notify_all()
