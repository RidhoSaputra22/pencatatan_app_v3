"""Recording utilities for processed YOLO footage."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from .logger import get_logger

log = get_logger("recording")
EPSILON = 1e-6
FFMPEG_BINARY = shutil.which("ffmpeg")
H264_OPTIMIZATION_ENABLED = (os.getenv("EDGE_RECORDING_H264_ENABLED", "true").strip().lower()
                             not in {"0", "false", "no", "off"})
H264_PRESET = os.getenv("EDGE_RECORDING_H264_PRESET", "veryfast").strip() or "veryfast"


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


H264_CRF = _bounded_env_int("EDGE_RECORDING_H264_CRF", 23, 18, 35)
H264_WORKERS = _bounded_env_int("EDGE_RECORDING_H264_WORKERS", 1, 1, 4)
H264_EXECUTOR = ThreadPoolExecutor(
    max_workers=H264_WORKERS,
    thread_name_prefix="recording-h264",
)


def _segment_stamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S")


def _optimizing_path(final_path: Path) -> Path:
    return final_path.with_name(f"{final_path.stem}.optimizing.mp4")


def _transcode_temp_path(final_path: Path) -> Path:
    return final_path.with_suffix(".transcode.tmp")


def _format_size_mb(size_bytes: int) -> float:
    return round(size_bytes / (1024 * 1024), 2)


def _finalize_recording_file(source_path: Path, final_path: Path) -> None:
    if not source_path.exists():
        return

    if not H264_OPTIMIZATION_ENABLED or not FFMPEG_BINARY:
        source_path.replace(final_path)
        log.info("Saved CCTV recording segment to %s", final_path)
        if H264_OPTIMIZATION_ENABLED and not FFMPEG_BINARY:
            log.warning("ffmpeg not found, saved original recording without H.264 optimization")
        return

    temp_output_path = _transcode_temp_path(final_path)
    temp_output_path.unlink(missing_ok=True)
    source_size = source_path.stat().st_size
    command = [
        FFMPEG_BINARY,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        H264_PRESET,
        "-crf",
        str(H264_CRF),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        str(temp_output_path),
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        temp_output_path.unlink(missing_ok=True)
        source_path.replace(final_path)
        log.warning(
            "Failed to start H.264 optimization for %s (%s). Keeping original file.",
            final_path.name,
            exc,
        )
        return

    if result.returncode != 0 or not temp_output_path.exists():
        temp_output_path.unlink(missing_ok=True)
        source_path.replace(final_path)
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        detail_msg = detail[-1] if detail else "Unknown ffmpeg error"
        log.warning(
            "H.264 optimization failed for %s (%s). Keeping original file.",
            final_path.name,
            detail_msg,
        )
        return

    if not source_path.exists():
        temp_output_path.unlink(missing_ok=True)
        log.info("Skipped H.264 optimization output for deleted recording %s", final_path.name)
        return

    temp_output_path.replace(final_path)
    source_path.unlink(missing_ok=True)

    optimized_size = final_path.stat().st_size
    savings_ratio = 0.0
    if source_size > 0:
        savings_ratio = max(0.0, 100.0 * (1.0 - (optimized_size / source_size)))

    log.info(
        "Saved CCTV recording segment to %s with H.264 optimization (%.2f MB -> %.2f MB, %.1f%% smaller)",
        final_path,
        _format_size_mb(source_size),
        _format_size_mb(optimized_size),
        savings_ratio,
    )


def _queue_recording_finalization(source_path: Path, final_path: Path) -> None:
    if not source_path.exists():
        return
    try:
        H264_EXECUTOR.submit(_finalize_recording_file, source_path, final_path)
    except RuntimeError:
        _finalize_recording_file(source_path, final_path)


@dataclass
class SegmentInfo:
    start_ts: float
    end_ts: Optional[float]
    temp_path: Path
    final_path: Optional[Path]
    optimizing_path: Optional[Path]


class SegmentedVideoRecorder:
    """Record processed frames as fixed segments or a full edge session."""

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
        recording_mode: str = "segment",
    ) -> None:
        self.output_dir = Path(output_dir)
        self.camera_id = camera_id
        self.segment_seconds = max(float(segment_seconds), 1.0)
        self.fps = max(float(fps), 1.0)
        self.enabled = bool(enabled)
        self.max_gap_seconds = max(float(max_gap_seconds), 1.0)
        self.file_prefix = file_prefix.strip() or "yolo_backup"
        self.recording_mode = "session" if str(recording_mode).strip().lower() == "session" else "segment"
        self.frame_interval = 1.0 / self.fps

        self._writer: Optional[cv2.VideoWriter] = None
        self._segment: Optional[SegmentInfo] = None
        self._next_emit_ts: Optional[float] = None
        self._frame_size: Optional[Tuple[int, int]] = None
        self._last_frame_ts: Optional[float] = None
        self._session_label_start_ts: Optional[float] = (
            time.time() if self.enabled and self.recording_mode == "session" else None
        )

        if self.enabled:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self._cleanup_stale_partial_segments()

    def _cleanup_stale_partial_segments(self) -> None:
        pattern = f"{self.file_prefix}_cam{self.camera_id}_*.partial.mp4"
        for partial_path in self.output_dir.glob(pattern):
            partial_path.unlink(missing_ok=True)
        optimize_pattern = f"{self.file_prefix}_cam{self.camera_id}_*.optimizing.mp4"
        for optimizing_path in self.output_dir.glob(optimize_pattern):
            final_name = optimizing_path.name.replace(".optimizing.mp4", ".mp4")
            _queue_recording_finalization(optimizing_path, optimizing_path.with_name(final_name))

    def _final_paths(self, start_ts: float, end_ts: float) -> Tuple[Path, Path]:
        stem = (
            f"{self.file_prefix}_cam{self.camera_id}_"
            f"{_segment_stamp(start_ts)}_{_segment_stamp(end_ts)}"
        )
        final_path = self.output_dir / f"{stem}.mp4"
        optimizing_path = _optimizing_path(final_path)
        return final_path, optimizing_path

    def _temp_path(self, start_ts: float) -> Path:
        suffix = "session" if self.recording_mode == "session" else "segment"
        stem = f"{self.file_prefix}_cam{self.camera_id}_{_segment_stamp(start_ts)}_{suffix}"
        return self.output_dir / f"{stem}.partial.mp4"

    def _open_segment(self, start_ts: float, frame: np.ndarray) -> bool:
        label_start_ts = (
            float(self._session_label_start_ts)
            if self.recording_mode == "session" and self._session_label_start_ts is not None
            else float(start_ts)
        )
        end_ts = label_start_ts + self.segment_seconds if self.recording_mode == "segment" else None
        final_path = None
        optimizing_path = None
        if end_ts is not None:
            final_path, optimizing_path = self._final_paths(label_start_ts, end_ts)
        temp_path = self._temp_path(label_start_ts)
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
            start_ts=label_start_ts,
            end_ts=float(end_ts) if end_ts is not None else None,
            final_path=final_path,
            temp_path=temp_path,
            optimizing_path=optimizing_path,
        )
        self._next_emit_ts = float(start_ts)
        self._frame_size = frame_size

        if self.recording_mode == "session":
            log.info(
                "Started YOLO backup session: %s (fps=%s)",
                temp_path.name,
                self.fps,
            )
        else:
            log.info(
                "Started YOLO backup segment: %s (duration=%ss, fps=%s)",
                final_path.name if final_path is not None else temp_path.name,
                int(self.segment_seconds),
                self.fps,
            )
        return True

    def _close_segment(self, *, complete: bool, reason: str, end_ts: Optional[float] = None) -> None:
        if self._writer is not None:
            self._writer.release()
        self._writer = None

        segment = self._segment
        if segment is not None:
            if complete:
                final_end_ts = float(end_ts if end_ts is not None else time.time())
                final_end_ts = max(final_end_ts, segment.start_ts)
                final_path = segment.final_path
                optimizing_path = segment.optimizing_path
                if final_path is None or optimizing_path is None:
                    final_path, optimizing_path = self._final_paths(segment.start_ts, final_end_ts)
                segment.end_ts = final_end_ts
                segment.final_path = final_path
                segment.optimizing_path = optimizing_path
                segment.temp_path.replace(optimizing_path)
                _queue_recording_finalization(optimizing_path, final_path)
                log.info("Queued CCTV recording optimization for %s", final_path.name)
            else:
                segment.temp_path.unlink(missing_ok=True)
                if segment.optimizing_path is not None:
                    segment.optimizing_path.unlink(missing_ok=True)
                log.info(
                    "Discarded incomplete YOLO backup segment %s (%s)",
                    segment.temp_path.name,
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

            if self._segment.end_ts is not None and self._next_emit_ts + EPSILON >= self._segment.end_ts:
                boundary_ts = self._segment.end_ts
                self._close_segment(complete=True, reason="segment completed", end_ts=boundary_ts)
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
            if self.recording_mode == "session":
                self._session_label_start_ts = time.time()
            return
        self._close_segment(
            complete=self.recording_mode == "session",
            reason=reason,
            end_ts=self._last_frame_ts,
        )
        self._last_frame_ts = None
        if self.recording_mode == "session":
            self._session_label_start_ts = time.time()

    def close(self) -> None:
        if not self.enabled:
            return
        if self._writer is not None or self._segment is not None:
            self._close_segment(
                complete=self.recording_mode == "session",
                reason="worker stopped",
                end_ts=self._last_frame_ts,
            )
        self._last_frame_ts = None
        if self.recording_mode == "session":
            self._session_label_start_ts = time.time()
