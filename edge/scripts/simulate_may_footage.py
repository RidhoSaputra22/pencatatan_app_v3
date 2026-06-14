#!/usr/bin/env python3
"""Run a one-off local footage simulation for repaired local clips mapped by filename.

This helper assumes:
- backend is already running on http://127.0.0.1:8000
- edge worker is already running on http://127.0.0.1:5000
- repaired input clips exist under rstp/footage/merged_mp4_08_17/202606
- each filename follows `tanggal_jamMulai-jamSelesai.repaired.mp4`
  for May 2026, for example `08_08-17.repaired.mp4`

What it does:
1. Clear visitor tables and old recording files/previews.
2. Reconfigure the running edge worker via runtime_config.json to replay each
   local clip once with event posting enabled only for the first pass.
3. Wait for each batch to settle, then rewrite the new rows into the target
   May 2026 date and the hour window encoded in the filename.
4. Capture the processed preview stream with overlay into backend/storage/footage
   using the auto-recording filename pattern so it appears in the Rekaman CCTV panel.
5. Restore the original runtime config values that were changed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


PROJECT_DIR = Path(__file__).resolve().parents[2]
RUNTIME_CONFIG_PATH = PROJECT_DIR / "backend" / "storage" / "runtime_config.json"
DB_PATH = PROJECT_DIR / "backend" / "visitors.db"
FOOTAGE_DIR = PROJECT_DIR / "backend" / "storage" / "footage"
PREVIEW_DIR = PROJECT_DIR / "backend" / "storage" / "recording_previews"
PROGRESS_PATH = PROJECT_DIR / "backend" / "storage" / "simulate_may_footage_progress.json"
HEALTH_URL = "http://127.0.0.1:5000/health"
PROCESSED_STREAM_URL = "http://127.0.0.1:5000/video_feed"
RUNTIME_RELOAD_WAIT_SECONDS = 7
SOURCE_GROUP_DIR = PROJECT_DIR / "rstp" / "footage" / "merged_mp4_08_17" / "202606"
SIMULATION_TARGET_YEAR = 2026
SIMULATION_TARGET_MONTH = 6
HEALTH_POLL_SECONDS = 3
SOURCE_STOP_GRACE_SECONDS = 12
PROGRESS_LOG_INTERVAL_SECONDS = 60
CAPTURE_FINALIZE_TIMEOUT_SECONDS = 900
OVERLAY_CAPTURE_FPS = 10.0
OVERLAY_CAPTURE_START_TIMEOUT_SECONDS = 30.0
SIMULATION_TARGET_PATTERN = re.compile(
    r"(?P<day>\d{2})_(?P<start_hour>\d{2})-(?P<end_hour>\d{2})\.repaired\.mp4$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SimulationTarget:
    source_path: Path
    target_date: date
    recording_start_hms: tuple[int, int, int]
    recording_end_hms: tuple[int, int, int]

    @property
    def filename(self) -> str:
        return self.source_path.name

    @property
    def target_window_seconds(self) -> int:
        start_dt, end_dt = target_window_bounds(self)
        return max(int((end_dt - start_dt).total_seconds()), 1)


@dataclass
class OverlayCaptureJob:
    thread: threading.Thread
    stop_event: threading.Event
    temp_output: Path
    destination: Path
    output_name: str
    timeout_seconds: float
    state: dict[str, Any]


@dataclass(frozen=True)
class BatchWaitResult:
    got_new_events: bool
    reached_source_end: bool
    reason: str
    elapsed_seconds: float
    final_health_status: str
    final_health_detail: Optional[str]


def info(message: str) -> None:
    print(f"[simulate] {message}", flush=True)


def warn(message: str) -> None:
    print(f"[simulate] WARNING: {message}", file=sys.stderr, flush=True)


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"[simulate] ERROR: {message}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Simulasikan footage repaired ke data pengunjung dan rekaman "
            "berdasarkan pola nama file tanggal_jamMulai-jamSelesai untuk Mei 2026."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validasi target repaired dan tampilkan rencana tanpa menjalankan edge.",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Abaikan progress lama, hapus state simulasi, lalu mulai ulang dari clip pertama.",
    )
    return parser


def parse_filename_hour(raw_value: str, *, label: str, allow_24: bool = False) -> int:
    try:
        hour = int(raw_value)
    except ValueError as exc:
        fail(f"jam {label} tidak valid: {raw_value!r} ({exc})")
    max_hour = 24 if allow_24 else 23
    if hour < 0 or hour > max_hour:
        fail(f"jam {label} di luar rentang 00-{max_hour:02d}: {raw_value!r}")
    return hour


def discover_targets() -> list[SimulationTarget]:
    if not SOURCE_GROUP_DIR.exists():
        fail(f"folder source tidak ditemukan: {SOURCE_GROUP_DIR}")

    targets: list[SimulationTarget] = []

    for path in sorted(SOURCE_GROUP_DIR.glob("*.repaired.mp4")):
        match = SIMULATION_TARGET_PATTERN.fullmatch(path.name)
        if not match:
            continue

        day = int(match.group("day"))
        start_hour = parse_filename_hour(match.group("start_hour"), label="mulai")
        end_hour = parse_filename_hour(
            match.group("end_hour"),
            label="selesai",
            allow_24=True,
        )
        try:
            target_day = date(SIMULATION_TARGET_YEAR, SIMULATION_TARGET_MONTH, day)
        except ValueError as exc:
            fail(f"tanggal target tidak valid untuk {path.name}: {exc}")

        targets.append(
            SimulationTarget(
                source_path=path,
                target_date=target_day,
                recording_start_hms=(start_hour, 0, 0),
                recording_end_hms=(end_hour, 0, 0),
            )
        )

    if not targets:
        fail(
            "tidak ada file repaired yang cocok dengan pola "
            f"{SIMULATION_TARGET_PATTERN.pattern!r} di {SOURCE_GROUP_DIR}"
        )

    return targets


def read_runtime_config() -> Dict[str, Any]:
    try:
        with RUNTIME_CONFIG_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        fail(f"runtime config tidak ditemukan: {exc}")
    except json.JSONDecodeError as exc:
        fail(f"runtime config rusak: {exc}")


def write_runtime_config(payload: Dict[str, Any]) -> None:
    RUNTIME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = RUNTIME_CONFIG_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
    temp_path.replace(RUNTIME_CONFIG_PATH)


def load_video_duration_seconds(path: Path) -> float:
    if not path.exists():
        fail(f"file input tidak ditemukan: {path}")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        fail(f"ffprobe tidak tersedia: {exc}")

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or "unknown ffprobe error"
        fail(f"gagal membaca durasi {path.name}: {detail}")

    try:
        return float((result.stdout or "").strip())
    except ValueError as exc:
        fail(f"durasi video tidak valid untuk {path.name}: {exc}")


def probe_video_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "file tidak ditemukan"

    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        return False, f"ffprobe tidak tersedia: {exc}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or "unknown ffprobe error"
        return False, detail

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return False, f"output ffprobe tidak valid: {exc}"

    streams = payload.get("streams") or []
    codec_name = str((streams[0] or {}).get("codec_name") or "").strip() if streams else ""
    raw_duration = str((payload.get("format") or {}).get("duration") or "").strip()
    if not codec_name:
        return False, "stream video tidak terdeteksi"
    try:
        duration = float(raw_duration)
    except ValueError:
        return False, f"durasi ffprobe tidak valid: {raw_duration!r}"
    if duration <= 0:
        return False, f"durasi video tidak masuk akal: {duration}"
    return True, f"codec={codec_name}, duration={duration:.2f}s"


def parse_db_datetime(raw_value: Optional[str]) -> Optional[datetime]:
    if not raw_value:
        return None
    raw = str(raw_value).strip()
    if not raw:
        return None
    normalized = raw.replace("T", " ")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def format_db_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")


def target_window_bounds(target: SimulationTarget) -> tuple[datetime, datetime]:
    start_dt = datetime(
        target.target_date.year,
        target.target_date.month,
        target.target_date.day,
        target.recording_start_hms[0],
        target.recording_start_hms[1],
        target.recording_start_hms[2],
    )
    end_hour, end_minute, end_second = target.recording_end_hms
    if end_hour == 24:
        end_dt = datetime(
            target.target_date.year,
            target.target_date.month,
            target.target_date.day,
            0,
            end_minute,
            end_second,
        ) + timedelta(days=1)
    else:
        end_dt = datetime(
            target.target_date.year,
            target.target_date.month,
            target.target_date.day,
            end_hour,
            end_minute,
            end_second,
        )
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def remap_timestamp_to_target_window(
    original: Optional[str],
    *,
    source_start: Optional[datetime],
    source_end: Optional[datetime],
    target_start: datetime,
    target_end: datetime,
) -> Optional[str]:
    parsed = parse_db_datetime(original)
    if parsed is None:
        return original

    if source_start is None or source_end is None or source_end <= source_start:
        return format_db_datetime(target_start)

    source_span = max((source_end - source_start).total_seconds(), 1.0)
    target_span = max((target_end - target_start).total_seconds(), 1.0)
    position = (parsed - source_start).total_seconds() / source_span
    position = min(max(position, 0.0), 1.0)
    shifted = target_start + timedelta(seconds=target_span * position)
    return format_db_datetime(shifted)


def create_temp_capture_path(output_name: str) -> Path:
    FOOTAGE_DIR.parent.mkdir(parents=True, exist_ok=True)
    stem = Path(output_name).stem
    with tempfile.NamedTemporaryFile(
        prefix=f".{stem}_",
        suffix=".capture.mp4",
        dir=str(FOOTAGE_DIR.parent),
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
    temp_path.unlink(missing_ok=True)
    return temp_path


def fetch_edge_health() -> Dict[str, Any]:
    request = urllib.request.Request(HEALTH_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        data = response.read().decode("utf-8")
    return json.loads(data)


def require_edge_online() -> None:
    try:
        payload = fetch_edge_health()
    except urllib.error.URLError as exc:
        fail(f"edge worker tidak bisa diakses di {HEALTH_URL}: {exc}")
    status = str(payload.get("status") or "").lower()
    if not status:
        fail(f"payload health edge tidak punya status: {payload}")
    if status == "error":
        fail(f"status edge worker tidak siap: {payload}")
    info(f"health edge terjangkau dengan status={status}")


def wait_for_runtime_reload(delay_seconds: int = RUNTIME_RELOAD_WAIT_SECONDS) -> None:
    info(
        "menunggu edge worker memuat runtime config terbaru "
        f"({delay_seconds} detik)"
    )
    time.sleep(delay_seconds)


def clear_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for item in directory.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)


def with_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def reset_database() -> None:
    with with_connection() as connection:
        connection.execute("DELETE FROM visit_events")
        connection.execute("DELETE FROM visitor_daily")
        connection.execute("DELETE FROM daily_stats")
        connection.commit()


def current_max_id(connection: sqlite3.Connection, table: str, id_column: str) -> int:
    row = connection.execute(f"SELECT COALESCE(MAX({id_column}), 0) AS value FROM {table}").fetchone()
    return int(row["value"] or 0)


def wait_for_source(source_path: Path, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    wanted = str(source_path.resolve())
    replay_forced = False
    while time.time() < deadline:
        try:
            health = fetch_edge_health()
        except Exception:
            time.sleep(HEALTH_POLL_SECONDS)
            continue
        if str(health.get("camera_source") or "") == wanted:
            if health.get("has_frame"):
                info(f"edge sudah memproses {source_path.name}")
                return
            status = str(health.get("status") or "").strip().lower()
            if status == "stopped" and not replay_forced:
                replay_forced = True
                force_edge_source_replay(
                    source_path,
                    reason=(
                        f"edge masih berhenti di source yang sama ({source_path.name})"
                    ),
                )
                deadline = max(deadline, time.time() + timeout_seconds)
                continue
        time.sleep(HEALTH_POLL_SECONDS)
    fail(f"edge tidak beralih ke sumber {source_path.name} dalam {timeout_seconds} detik")


def force_edge_source_replay(source_path: Path, *, reason: str) -> None:
    wanted = str(source_path.resolve())
    info(f"{reason}; memaksa reset source lalu replay ulang")

    runtime_payload = read_runtime_config()
    runtime_payload.setdefault("values", {})["EDGE_STREAM_URL"] = ""
    write_runtime_config(runtime_payload)
    wait_for_runtime_reload()

    runtime_payload = read_runtime_config()
    runtime_payload.setdefault("values", {})["EDGE_STREAM_URL"] = wanted
    write_runtime_config(runtime_payload)
    wait_for_runtime_reload()


def _require_cv2():
    try:
        import cv2  # type: ignore
    except ModuleNotFoundError as exc:
        fail(
            "OpenCV (cv2) tidak tersedia di interpreter aktif. "
            "Jalankan script ini dengan Python environment edge yang sudah terpasang dependency-nya."
        )
        raise exc
    return cv2


def _open_overlay_writer(output_path: Path, frame):
    cv2 = _require_cv2()
    frame_size = (int(frame.shape[1]), int(frame.shape[0]))
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        OVERLAY_CAPTURE_FPS,
        frame_size,
    )
    if not writer.isOpened():
        raise RuntimeError(f"gagal membuka writer overlay untuk {output_path.name}")
    return writer


def _capture_overlay_stream(job: OverlayCaptureJob) -> None:
    cv2 = _require_cv2()
    capture = cv2.VideoCapture(PROCESSED_STREAM_URL)
    writer = None
    try:
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    try:
        capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10_000)
        capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10_000)
    except Exception:
        pass

    if not capture.isOpened():
        job.state["error"] = f"gagal membuka stream overlay {PROCESSED_STREAM_URL}"
        return

    try:
        while True:
            ok, frame = capture.read()
            if ok and frame is not None and getattr(frame, "size", 0) > 0:
                if writer is None:
                    writer = _open_overlay_writer(job.temp_output, frame)
                writer.write(frame)
                job.state["frame_count"] = int(job.state.get("frame_count", 0)) + 1
                if not job.state.get("started"):
                    job.state["started"] = True
                if job.stop_event.is_set():
                    break
                continue

            if job.stop_event.is_set():
                break

            time.sleep(0.05)
    except Exception as exc:
        job.state["error"] = str(exc)
    finally:
        if writer is not None:
            writer.release()
        capture.release()


def _transcode_overlay_capture(source_path: Path, destination_path: Path) -> None:
    temp_output = destination_path.with_suffix(".tmp.mp4")
    temp_output.unlink(missing_ok=True)
    command = [
        "ffmpeg",
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
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(temp_output),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        temp_output.unlink(missing_ok=True)
        fail(f"ffmpeg tidak tersedia untuk finalisasi overlay: {exc}")

    if result.returncode != 0 or not temp_output.exists():
        temp_output.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout or "").strip() or "unknown ffmpeg error"
        fail(f"gagal finalisasi overlay {destination_path.name}: {detail}")

    destination_path.unlink(missing_ok=True)
    temp_output.replace(destination_path)
    source_path.unlink(missing_ok=True)


def start_overlay_capture(target: SimulationTarget, duration_seconds: float) -> OverlayCaptureJob:
    output_name = recording_name_for(target)
    destination = FOOTAGE_DIR / output_name
    temp_output = create_temp_capture_path(output_name)
    timeout_seconds = max(
        CAPTURE_FINALIZE_TIMEOUT_SECONDS,
        min(int(duration_seconds * 0.03), 3600),
    )
    stop_event = threading.Event()
    state: dict[str, Any] = {"error": None, "frame_count": 0, "started": False}
    job = OverlayCaptureJob(
        thread=threading.current_thread(),
        stop_event=stop_event,
        temp_output=temp_output,
        destination=destination,
        output_name=output_name,
        timeout_seconds=timeout_seconds,
        state=state,
    )
    job.thread = threading.Thread(
        target=_capture_overlay_stream,
        args=(job,),
        name=f"overlay-capture-{Path(output_name).stem}",
        daemon=True,
    )
    job.thread.start()

    deadline = time.time() + OVERLAY_CAPTURE_START_TIMEOUT_SECONDS
    replay_forced = False
    while time.time() < deadline:
        if job.state.get("error"):
            job.stop_event.set()
            job.thread.join(timeout=5)
            job.temp_output.unlink(missing_ok=True)
            fail(f"capture overlay gagal memulai untuk {output_name}: {job.state['error']}")
        if int(job.state.get("frame_count", 0)) > 0:
            info(f"capture overlay dimulai untuk {output_name}")
            return job
        if not job.thread.is_alive():
            break
        time.sleep(0.2)

    if not replay_forced and int(job.state.get("frame_count", 0)) <= 0 and job.thread.is_alive():
        replay_forced = True
        force_edge_source_replay(
            target.source_path,
            reason=(
                f"capture overlay belum menerima frame dari stream untuk {output_name}"
            ),
        )
        deadline = time.time() + OVERLAY_CAPTURE_START_TIMEOUT_SECONDS
        while time.time() < deadline:
            if job.state.get("error"):
                job.stop_event.set()
                job.thread.join(timeout=5)
                job.temp_output.unlink(missing_ok=True)
                fail(f"capture overlay gagal memulai untuk {output_name}: {job.state['error']}")
            if int(job.state.get("frame_count", 0)) > 0:
                info(f"capture overlay dimulai untuk {output_name}")
                return job
            if not job.thread.is_alive():
                break
            time.sleep(0.2)

    job.stop_event.set()
    job.thread.join(timeout=5)
    job.temp_output.unlink(missing_ok=True)
    detail = str(job.state.get("error") or "stream overlay tidak mengirim frame")
    try:
        health = fetch_edge_health()
    except Exception:
        health = None
    if health:
        detail = (
            f"{detail} | status={health.get('status')} | "
            f"camera_source={health.get('camera_source')} | "
            f"has_frame={health.get('has_frame')}"
        )
    fail(f"capture overlay gagal memulai untuk {output_name}: {detail}")


def finish_overlay_capture(job: OverlayCaptureJob) -> str:
    info(f"menghentikan capture overlay untuk {job.output_name} dan menunggu flush writer")
    job.stop_event.set()
    job.thread.join(timeout=job.timeout_seconds)
    if job.thread.is_alive():
        fail(f"capture overlay timeout untuk {job.output_name}: writer tidak selesai ditutup")
    if job.state.get("error"):
        job.temp_output.unlink(missing_ok=True)
        fail(f"capture overlay gagal untuk {job.output_name}: {job.state['error']}")

    if not job.temp_output.exists() or job.temp_output.stat().st_size <= 0:
        job.temp_output.unlink(missing_ok=True)
        detail = "writer overlay tidak menghasilkan file"
        fail(f"capture overlay gagal untuk {job.output_name}: {detail}")

    is_valid_output, validation_detail = probe_video_file(job.temp_output)
    if not is_valid_output:
        fail(
            f"capture overlay menghasilkan file tidak valid untuk {job.output_name}: "
            f"validasi output gagal: {validation_detail}"
        )

    _transcode_overlay_capture(job.temp_output, job.destination)
    is_valid_destination, destination_detail = probe_video_file(job.destination)
    if not is_valid_destination:
        job.destination.unlink(missing_ok=True)
        fail(
            f"overlay recording final tidak valid untuk {job.output_name}: "
            f"{destination_detail}"
        )
    info(f"overlay recording tersimpan: {job.output_name}")
    return job.output_name


def wait_for_batch_completion(
    source_path: Path,
    baseline_event_id: int,
    expected_duration_seconds: float,
    stable_seconds: int = 30,
) -> BatchWaitResult:
    start_ts = time.time()
    max_wait = max(int(expected_duration_seconds * 1.25 + max(stable_seconds, 600)), 75)
    last_change_ts = start_ts
    last_progress_log_ts = start_ts
    seen_new_rows = False
    seen_source_frames = False
    previous_max_event_id = baseline_event_id
    source_stop_seen_at: Optional[float] = None
    wanted_source = str(source_path.resolve())
    final_health_status = "unknown"
    final_health_detail: Optional[str] = None

    while True:
        now = time.time()
        with with_connection() as connection:
            current_event_id = current_max_id(connection, "visit_events", "event_id")

        if current_event_id > previous_max_event_id:
            previous_max_event_id = current_event_id
            last_change_ts = now
            seen_new_rows = True

        try:
            health = fetch_edge_health()
        except Exception as exc:
            final_health_status = "unreachable"
            final_health_detail = str(exc)
        else:
            final_health_status = str(health.get("status") or "unknown")
            raw_detail = str(health.get("status_detail") or "").strip()
            final_health_detail = raw_detail or None
            if str(health.get("camera_source") or "") == wanted_source:
                if health.get("has_frame"):
                    seen_source_frames = True
                    source_stop_seen_at = None
                elif seen_source_frames and final_health_status.lower() == "stopped":
                    if source_stop_seen_at is None:
                        source_stop_seen_at = now
                        detail_suffix = (
                            f" ({final_health_detail})" if final_health_detail else ""
                        )
                        info(
                            f"sumber {source_path.name} mencapai EOF/stopped{detail_suffix}; "
                            f"menunggu {SOURCE_STOP_GRACE_SECONDS} detik untuk flush event terakhir"
                        )

        if source_stop_seen_at is not None:
            quiet_seconds = now - last_change_ts
            if now - source_stop_seen_at >= SOURCE_STOP_GRACE_SECONDS and (
                not seen_new_rows or quiet_seconds >= min(stable_seconds, SOURCE_STOP_GRACE_SECONDS)
            ):
                return BatchWaitResult(
                    got_new_events=seen_new_rows,
                    reached_source_end=True,
                    reason="source_stopped",
                    elapsed_seconds=now - start_ts,
                    final_health_status=final_health_status,
                    final_health_detail=final_health_detail,
                )

        if not seen_source_frames and seen_new_rows and now - last_change_ts >= stable_seconds:
            return BatchWaitResult(
                got_new_events=True,
                reached_source_end=False,
                reason="stable_without_source_health",
                elapsed_seconds=now - start_ts,
                final_health_status=final_health_status,
                final_health_detail=final_health_detail,
            )

        if now - last_progress_log_ts >= PROGRESS_LOG_INTERVAL_SECONDS:
            info(
                f"progress {source_path.name}: elapsed={int(now - start_ts)}s, "
                f"event_baru={max(current_event_id - baseline_event_id, 0)}, "
                f"status_edge={final_health_status}, "
                f"source_selesai={'ya' if source_stop_seen_at is not None else 'belum'}"
            )
            last_progress_log_ts = now

        if now - start_ts >= max_wait:
            return BatchWaitResult(
                got_new_events=seen_new_rows,
                reached_source_end=source_stop_seen_at is not None,
                reason="timeout",
                elapsed_seconds=now - start_ts,
                final_health_status=final_health_status,
                final_health_detail=final_health_detail,
            )

        time.sleep(HEALTH_POLL_SECONDS)


def redate_new_rows(
    target: SimulationTarget,
    baseline_event_id: int,
    baseline_visitor_daily_id: int,
    reserved_stat_dates: set[str],
) -> Dict[str, int]:
    updated = {
        "visit_events": 0,
        "visitor_daily": 0,
        "daily_stats": 0,
    }
    with with_connection() as connection:
        visit_events = connection.execute(
            "SELECT event_id, event_time FROM visit_events WHERE event_id > ? ORDER BY event_id",
            (baseline_event_id,),
        ).fetchall()
        target_start, target_end = target_window_bounds(target)
        source_times = [
            parsed
            for row in visit_events
            if (parsed := parse_db_datetime(row["event_time"])) is not None
        ]
        for row in visit_events:
            shifted = remap_timestamp_to_target_window(
                row["event_time"],
                source_start=source_times[0] if source_times else None,
                source_end=source_times[-1] if source_times else None,
                target_start=target_start,
                target_end=target_end,
            )
            connection.execute(
                "UPDATE visit_events SET event_time = ? WHERE event_id = ?",
                (shifted, row["event_id"]),
            )
        updated["visit_events"] = len(visit_events)

        visitors = connection.execute(
            (
                "SELECT visitor_daily_id, visit_date, first_seen_at, last_seen_at "
                "FROM visitor_daily WHERE visitor_daily_id > ? ORDER BY visitor_daily_id"
            ),
            (baseline_visitor_daily_id,),
        ).fetchall()
        visitor_times = [
            parsed
            for row in visitors
            for value in (row["first_seen_at"], row["last_seen_at"])
            if (parsed := parse_db_datetime(value)) is not None
        ]
        source_start = source_times[0] if source_times else (min(visitor_times) if visitor_times else None)
        source_end = source_times[-1] if source_times else (max(visitor_times) if visitor_times else None)
        for row in visitors:
            first_seen_at = remap_timestamp_to_target_window(
                row["first_seen_at"],
                source_start=source_start,
                source_end=source_end,
                target_start=target_start,
                target_end=target_end,
            )
            last_seen_at = remap_timestamp_to_target_window(
                row["last_seen_at"],
                source_start=source_start,
                source_end=source_end,
                target_start=target_start,
                target_end=target_end,
            )
            connection.execute(
                (
                    "UPDATE visitor_daily "
                    "SET visit_date = ?, first_seen_at = ?, last_seen_at = ? "
                    "WHERE visitor_daily_id = ?"
                ),
                (target.target_date.isoformat(), first_seen_at, last_seen_at, row["visitor_daily_id"]),
            )
        updated["visitor_daily"] = len(visitors)

        stats_rows = connection.execute(
            "SELECT stat_date, camera_id FROM daily_stats"
        ).fetchall()
        for row in stats_rows:
            stat_date = str(row["stat_date"] or "")
            if stat_date == target.target_date.isoformat():
                updated["daily_stats"] += 1
                continue
            if stat_date in reserved_stat_dates:
                continue
            connection.execute(
                "UPDATE daily_stats SET stat_date = ? WHERE stat_date = ? AND camera_id = ?",
                (target.target_date.isoformat(), stat_date, row["camera_id"]),
            )
            updated["daily_stats"] += 1

        if updated["daily_stats"] == 0:
            connection.execute(
                (
                    "INSERT INTO daily_stats "
                    "(stat_date, camera_id, total_events, unique_visitors, total_in, total_out, last_updated_at) "
                    "VALUES (?, ?, 0, 0, 0, 0, ?)"
                ),
                (
                    target.target_date.isoformat(),
                    1,
                    datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f"),
                ),
            )
            updated["daily_stats"] = 1

        connection.commit()
    return updated


def recording_name_for(target: SimulationTarget) -> str:
    start_dt, end_dt = target_window_bounds(target)
    return (
        "cctv_recording_cam1_"
        f"{start_dt.strftime('%Y%m%d_%H%M%S')}_"
        f"{end_dt.strftime('%Y%m%d_%H%M%S')}.mp4"
    )


def recording_preview_path_for(recording_name: str) -> Path:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    return PREVIEW_DIR / f"{Path(recording_name).stem}.browser.mp4"


def link_or_copy(source_path: Path, destination_path: Path) -> str:
    try:
        os.link(source_path, destination_path)
        return "hardlink"
    except OSError:
        shutil.copy2(source_path, destination_path)
        return "copy"


def save_overlay_preview(recording_path: Path) -> Path:
    if not recording_path.exists():
        fail(f"file rekaman overlay tidak ditemukan untuk preview: {recording_path}")

    preview_path = recording_preview_path_for(recording_path.name)
    temp_preview_path = preview_path.with_suffix(".tmp.mp4")
    temp_preview_path.unlink(missing_ok=True)

    try:
        mode = link_or_copy(recording_path, temp_preview_path)
        temp_preview_path.replace(preview_path)
    except Exception:
        temp_preview_path.unlink(missing_ok=True)
        raise

    info(f"preview overlay tersimpan: {preview_path.name} ({mode})")
    return preview_path


def query_daily_stats() -> list[sqlite3.Row]:
    with with_connection() as connection:
        return connection.execute(
            (
                "SELECT stat_date, camera_id, total_events, unique_visitors, total_in, total_out "
                "FROM daily_stats ORDER BY stat_date"
            )
        ).fetchall()


def query_recording_names() -> list[str]:
    return sorted(item.name for item in FOOTAGE_DIR.glob("*.mp4"))


def empty_progress_state() -> dict[str, Any]:
    return {
        "version": 1,
        "source_group_dir": str(SOURCE_GROUP_DIR.resolve()),
        "target_year": SIMULATION_TARGET_YEAR,
        "target_month": SIMULATION_TARGET_MONTH,
        "completed_targets": {},
    }


def read_progress_state() -> dict[str, Any]:
    if not PROGRESS_PATH.exists():
        return empty_progress_state()

    try:
        with PROGRESS_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        warn(f"gagal membaca progress file {PROGRESS_PATH}: {exc}; state akan diabaikan")
        return empty_progress_state()

    if not isinstance(payload, dict):
        warn(f"progress file {PROGRESS_PATH} tidak berbentuk object JSON; state akan diabaikan")
        return empty_progress_state()

    state = empty_progress_state()
    state.update(payload)
    completed_targets = payload.get("completed_targets")
    state["completed_targets"] = completed_targets if isinstance(completed_targets, dict) else {}
    return state


def write_progress_state(payload: dict[str, Any]) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = PROGRESS_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
    temp_path.replace(PROGRESS_PATH)


def delete_progress_state() -> None:
    PROGRESS_PATH.unlink(missing_ok=True)


def query_existing_target_dates() -> set[str]:
    with with_connection() as connection:
        rows = []
        rows.extend(connection.execute("SELECT DISTINCT date(event_time) AS value FROM visit_events").fetchall())
        rows.extend(connection.execute("SELECT DISTINCT visit_date AS value FROM visitor_daily").fetchall())
        rows.extend(connection.execute("SELECT DISTINCT stat_date AS value FROM daily_stats").fetchall())
    return {str(row["value"]) for row in rows if row["value"]}


def infer_completed_targets(targets: Iterable[SimulationTarget]) -> dict[str, dict[str, Any]]:
    existing_dates = query_existing_target_dates()
    existing_recordings = set(query_recording_names())
    inferred: dict[str, dict[str, Any]] = {}

    for target in targets:
        recording_name = recording_name_for(target)
        target_date = target.target_date.isoformat()
        if target_date not in existing_dates or recording_name not in existing_recordings:
            continue
        inferred[target.filename] = {
            "target_date": target_date,
            "source": target.filename,
            "recording_name": recording_name,
            "completed_at": None,
            "inferred_from_existing_data": True,
        }

    return inferred


def prune_to_completed_state(completed_targets: dict[str, dict[str, Any]]) -> None:
    allowed_dates = sorted(
        {
            str(record.get("target_date") or "").strip()
            for record in completed_targets.values()
            if str(record.get("target_date") or "").strip()
        }
    )
    allowed_recordings = {
        str(record.get("recording_name") or "").strip()
        for record in completed_targets.values()
        if str(record.get("recording_name") or "").strip()
    }

    if not allowed_dates:
        reset_database()
    else:
        placeholders = ", ".join("?" for _ in allowed_dates)
        with with_connection() as connection:
            connection.execute(
                f"DELETE FROM visit_events WHERE date(event_time) NOT IN ({placeholders})",
                tuple(allowed_dates),
            )
            connection.execute(
                f"DELETE FROM visitor_daily WHERE visit_date NOT IN ({placeholders})",
                tuple(allowed_dates),
            )
            connection.execute(
                f"DELETE FROM daily_stats WHERE stat_date NOT IN ({placeholders})",
                tuple(allowed_dates),
            )
            connection.commit()

    FOOTAGE_DIR.mkdir(parents=True, exist_ok=True)
    for item in FOOTAGE_DIR.iterdir():
        if item.name in allowed_recordings:
            continue
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)

    clear_directory(PREVIEW_DIR)
    for recording_name in sorted(allowed_recordings):
        recording_path = FOOTAGE_DIR / recording_name
        if recording_path.exists():
            save_overlay_preview(recording_path)


def update_runtime_values(runtime_payload: Dict[str, Any], values: Dict[str, str]) -> Dict[str, Optional[str]]:
    runtime_values = runtime_payload.setdefault("values", {})
    previous: Dict[str, Optional[str]] = {}
    for key, value in values.items():
        previous[key] = None if key not in runtime_values else str(runtime_values.get(key, ""))
        runtime_values[key] = value
    write_runtime_config(runtime_payload)
    return previous


def restore_runtime_values(runtime_payload: Dict[str, Any], original_values: Dict[str, Optional[str]]) -> None:
    runtime_values = runtime_payload.setdefault("values", {})
    for key, value in original_values.items():
        if value is None:
            runtime_values.pop(key, None)
        else:
            runtime_values[key] = value
    write_runtime_config(runtime_payload)


def validate_inputs(targets: Iterable[SimulationTarget]) -> None:
    missing = [str(target.source_path) for target in targets if not target.source_path.exists()]
    if missing:
        fail("ada file input yang hilang:\n" + "\n".join(missing))


def describe_targets(targets: Iterable[SimulationTarget]) -> list[dict[str, Any]]:
    descriptions: list[dict[str, Any]] = []
    for target in targets:
        source_duration_seconds = load_video_duration_seconds(target.source_path)
        target_start, target_end = target_window_bounds(target)
        descriptions.append(
            {
                "target_date": target.target_date.isoformat(),
                "source": target.filename,
                "source_path": str(target.source_path.resolve()),
                "parsed_time_window": (
                    f"{target_start.strftime('%Y-%m-%d %H:%M:%S')} -> "
                    f"{target_end.strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                "source_duration_seconds": round(source_duration_seconds, 2),
                "source_duration_hours": round(source_duration_seconds / 3600, 2),
                "simulated_window_seconds": target.target_window_seconds,
                "simulated_window_hours": round(target.target_window_seconds / 3600, 2),
                "recording_name": recording_name_for(target),
            }
        )
    return descriptions


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    targets = discover_targets()
    validate_inputs(targets)
    progress_state = read_progress_state()

    if args.restart:
        info("mode restart aktif: progress lama akan diabaikan dan simulasi dimulai ulang dari awal")
        if not args.dry_run:
            delete_progress_state()
        progress_state = empty_progress_state()

    completed_targets = progress_state.setdefault("completed_targets", {})
    inferred_targets = infer_completed_targets(targets)
    for target_name, payload in inferred_targets.items():
        completed_targets.setdefault(target_name, payload)
    if inferred_targets and not args.dry_run:
        write_progress_state(progress_state)

    pending_targets = [target for target in targets if target.filename not in completed_targets]

    if args.dry_run:
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": "dry-run",
                    "source_group_dir": str(SOURCE_GROUP_DIR.resolve()),
                    "progress_path": str(PROGRESS_PATH.resolve()),
                    "completed_targets": sorted(completed_targets.keys()),
                    "pending_targets": [target.filename for target in pending_targets],
                    "targets": describe_targets(targets),
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0

    if not pending_targets:
        info("semua target sudah tercatat complete; tidak ada clip yang perlu diproses ulang")
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": "resume-noop",
                    "progress_path": str(PROGRESS_PATH.resolve()),
                    "completed_targets": sorted(completed_targets.keys()),
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0

    require_edge_online()

    runtime_payload = read_runtime_config()
    runtime_overrides = {
        "EDGE_CONFIG_REFRESH_SECONDS": "5",
        "EDGE_LOCAL_FILE_STOP_ON_END": "true",
        "EDGE_LOCAL_FILE_REPLAY_POST_EVENTS": "false",
        "EDGE_RECORDING_ENABLED": "false",
    }
    original_override_values = update_runtime_values(runtime_payload, runtime_overrides)
    wait_for_runtime_reload()

    if completed_targets:
        info(
            f"mode resume: {len(completed_targets)} target sudah complete, "
            f"{len(pending_targets)} target tersisa"
        )
        prune_to_completed_state(completed_targets)
    else:
        info("mulai dari nol: menghapus data visitor lama")
        reset_database()
        info("mengosongkan backend/storage/footage dan recording_previews")
        clear_directory(FOOTAGE_DIR)
        clear_directory(PREVIEW_DIR)

    try:
        summaries: list[dict[str, Any]] = []
        reserved_stat_dates = {target.target_date.isoformat() for target in targets}
        total_pending = len(pending_targets)
        for index, target in enumerate(pending_targets, start=1):
            duration_seconds = load_video_duration_seconds(target.source_path)
            with with_connection() as connection:
                baseline_event_id = current_max_id(connection, "visit_events", "event_id")
                baseline_visitor_daily_id = current_max_id(connection, "visitor_daily", "visitor_daily_id")

            info(
                f"target {index}/{total_pending}: {target.filename} -> {target.target_date.isoformat()} "
                f"({duration_seconds / 3600:.2f} jam source)"
            )
            runtime_payload = read_runtime_config()
            runtime_payload.setdefault("values", {})["EDGE_STREAM_URL"] = str(target.source_path.resolve())
            write_runtime_config(runtime_payload)
            wait_for_source(target.source_path)

            info(
                f"memutar {target.filename} untuk simulasi tanggal {target.target_date.isoformat()} "
                f"(durasi {duration_seconds:.1f}s)"
            )
            capture_job = start_overlay_capture(target, duration_seconds)
            batch_result = wait_for_batch_completion(
                target.source_path,
                baseline_event_id=baseline_event_id,
                expected_duration_seconds=duration_seconds,
            )
            info(
                f"batch {target.filename} selesai ditunggu dengan reason={batch_result.reason}, "
                f"edge_status={batch_result.final_health_status}"
            )
            recording_name = finish_overlay_capture(capture_job)
            if batch_result.reason == "timeout" and not batch_result.reached_source_end:
                fail(
                    f"clip {target.filename} timeout sebelum edge melaporkan EOF. "
                    "Progress untuk target ini belum ditandai complete agar aman di-run ulang."
                )
            save_overlay_preview(capture_job.destination)
            shifted = redate_new_rows(
                target,
                baseline_event_id=baseline_event_id,
                baseline_visitor_daily_id=baseline_visitor_daily_id,
                reserved_stat_dates=reserved_stat_dates,
            )

            summary = {
                "target_date": target.target_date.isoformat(),
                "source": target.filename,
                "duration_seconds": round(duration_seconds, 2),
                "duration_hours": round(duration_seconds / 3600, 2),
                "simulated_window_seconds": target.target_window_seconds,
                "simulated_window_hours": round(target.target_window_seconds / 3600, 2),
                "got_new_events": batch_result.got_new_events,
                "batch_reason": batch_result.reason,
                "reached_source_end": batch_result.reached_source_end,
                "wait_elapsed_seconds": round(batch_result.elapsed_seconds, 2),
                "edge_status": batch_result.final_health_status,
                "edge_status_detail": batch_result.final_health_detail,
                "shifted": shifted,
                "recording_name": recording_name,
                "completed_at": datetime.now(UTC).isoformat(),
            }
            summaries.append(summary)
            completed_targets[target.filename] = summary
            write_progress_state(progress_state)
            info(
                f"selesai {target.filename}: "
                f"event={shifted['visit_events']}, unik={shifted['visitor_daily']}, "
                f"rekaman={recording_name}; progress disimpan, sisa {total_pending - index} target"
            )

        runtime_payload = read_runtime_config()
        restore_runtime_values(runtime_payload, original_override_values)

        daily_rows = query_daily_stats()
        recording_names = query_recording_names()

        info("ringkasan statistik harian:")
        for row in daily_rows:
            info(
                f"  {row['stat_date']} -> total={row['total_events']}, "
                f"masuk={row['total_in']}, keluar={row['total_out']}, unik={row['unique_visitors']}"
            )

        info("rekaman yang terdaftar:")
        for name in recording_names:
            info(f"  {name}")

        output = {
            "ok": True,
            "summaries": summaries,
            "progress_path": str(PROGRESS_PATH.resolve()),
            "completed_targets": sorted(completed_targets.keys()),
            "daily_stats": [
                {
                    "stat_date": row["stat_date"],
                    "camera_id": row["camera_id"],
                    "total_events": row["total_events"],
                    "unique_visitors": row["unique_visitors"],
                    "total_in": row["total_in"],
                    "total_out": row["total_out"],
                }
                for row in daily_rows
            ],
            "recordings": recording_names,
        }
        print(json.dumps(output, ensure_ascii=True, indent=2))
        return 0
    finally:
        runtime_payload = read_runtime_config()
        restore_runtime_values(runtime_payload, original_override_values)


if __name__ == "__main__":
    sys.exit(main())
