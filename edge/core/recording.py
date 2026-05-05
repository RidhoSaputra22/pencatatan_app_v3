"""Segmented recording utilities for processed YOLO footage."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .logger import get_logger

log = get_logger("recording")
EPSILON = 1e-6


def _segment_stamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S")


@dataclass
class SegmentInfo:
    start_ts: float
    end_ts: float
    final_path: Path
    temp_path: Path


class SegmentedVideoRecorder:
    """Record processed frames into fixed-duration MP4 segments."""

    def __init__(
        self,
        output_dir: str,
        camera_id: int,
        segment_seconds: float,
        fps: float,
        *,
        enabled: bool = True,
        max_gap_seconds: float = 5.0,
        file_prefix: str = "yolo_backup",
    ) -> None:
        self.output_dir = Path(output_dir)
        self.camera_id = camera_id
        self.segment_seconds = max(float(segment_seconds), 1.0)
        self.fps = max(float(fps), 1.0)
        self.enabled = bool(enabled)
        self.max_gap_seconds = max(float(max_gap_seconds), 1.0)
        self.file_prefix = file_prefix.strip() or "yolo_backup"
        self.frame_interval = 1.0 / self.fps

        self._writer: Optional[cv2.VideoWriter] = None
        self._segment: Optional[SegmentInfo] = None
        self._next_emit_ts: Optional[float] = None
        self._frame_size: Optional[Tuple[int, int]] = None
        self._last_frame_ts: Optional[float] = None

        if self.enabled:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self._cleanup_stale_partial_segments()

    def _cleanup_stale_partial_segments(self) -> None:
        pattern = f"{self.file_prefix}_cam{self.camera_id}_*.partial.mp4"
        for partial_path in self.output_dir.glob(pattern):
            partial_path.unlink(missing_ok=True)

    def _segment_paths(self, start_ts: float) -> Tuple[Path, Path, float]:
        end_ts = start_ts + self.segment_seconds
        stem = (
            f"{self.file_prefix}_cam{self.camera_id}_"
            f"{_segment_stamp(start_ts)}_{_segment_stamp(end_ts)}"
        )
        final_path = self.output_dir / f"{stem}.mp4"
        temp_path = self.output_dir / f"{stem}.partial.mp4"
        return final_path, temp_path, end_ts

    def _open_segment(self, start_ts: float, frame: np.ndarray) -> bool:
        final_path, temp_path, end_ts = self._segment_paths(start_ts)
        frame_size = (int(frame.shape[1]), int(frame.shape[0]))

        writer = cv2.VideoWriter(
            str(temp_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            self.fps,
            frame_size,
        )
        if not writer.isOpened():
            log.error("Failed to open YOLO backup writer for %s", temp_path)
            return False

        self._writer = writer
        self._segment = SegmentInfo(
            start_ts=float(start_ts),
            end_ts=float(end_ts),
            final_path=final_path,
            temp_path=temp_path,
        )
        self._next_emit_ts = float(start_ts)
        self._frame_size = frame_size

        log.info(
            "Started YOLO backup segment: %s (duration=%ss, fps=%s)",
            final_path.name,
            int(self.segment_seconds),
            self.fps,
        )
        return True

    def _close_segment(self, *, complete: bool, reason: str) -> None:
        if self._writer is not None:
            self._writer.release()
        self._writer = None

        if self._segment is not None:
            if complete:
                self._segment.temp_path.replace(self._segment.final_path)
                log.info("Saved YOLO backup segment to %s", self._segment.final_path)
            else:
                self._segment.temp_path.unlink(missing_ok=True)
                log.info(
                    "Discarded incomplete YOLO backup segment %s (%s)",
                    self._segment.temp_path.name,
                    reason,
                )

        self._segment = None
        self._next_emit_ts = None
        self._frame_size = None

    def write(self, frame: np.ndarray, frame_ts: Optional[float] = None) -> None:
        if not self.enabled or frame is None:
            return

        frame_ts = float(frame_ts if frame_ts is not None else time.time())
        current_size = (int(frame.shape[1]), int(frame.shape[0]))

        if self._last_frame_ts is not None:
            frame_gap = frame_ts - self._last_frame_ts
            if frame_gap > self.max_gap_seconds:
                self.reset(reason=f"stream gap {frame_gap:.2f}s")

        if self._writer is None:
            if not self._open_segment(frame_ts, frame):
                return
        elif self._frame_size != current_size:
            self.reset(reason="frame size changed")
            if not self._open_segment(frame_ts, frame):
                return

        while self._next_emit_ts is not None and frame_ts + EPSILON >= self._next_emit_ts:
            if self._segment is None:
                if not self._open_segment(frame_ts, frame):
                    return

            if self._next_emit_ts + EPSILON >= self._segment.end_ts:
                boundary_ts = self._segment.end_ts
                self._close_segment(complete=True, reason="segment completed")
                if not self._open_segment(boundary_ts, frame):
                    return
                continue

            self._writer.write(frame)
            self._next_emit_ts += self.frame_interval

        self._last_frame_ts = frame_ts

    def reset(self, reason: str = "reset requested") -> None:
        if not self.enabled:
            return
        if self._writer is None and self._segment is None:
            self._last_frame_ts = None
            return
        self._close_segment(complete=False, reason=reason)
        self._last_frame_ts = None

    def close(self) -> None:
        if not self.enabled:
            return
        if self._writer is not None or self._segment is not None:
            self._close_segment(complete=False, reason="worker stopped")
        self._last_frame_ts = None
