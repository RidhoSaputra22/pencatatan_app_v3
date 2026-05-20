#!/usr/bin/env python3
"""Run a one-off local footage simulation for 6, 7, 8, 11, and 12 May 2026.

This helper assumes:
- backend is already running on http://127.0.0.1:8000
- edge worker is already running on http://127.0.0.1:5000
- the five input clips exist under rstp/footage/may/

What it does:
1. Clear visitor tables and old recording files/previews.
2. Reconfigure the running edge worker via runtime_config.json to replay each
   local clip once with event posting enabled only for the first pass.
3. Wait for each batch to settle, then rewrite the new rows to the target date.
4. Capture the processed preview stream with overlay into backend/storage/footage
   using the auto-recording filename pattern so it appears in the Rekaman CCTV panel.
5. Restore the original runtime config values that were changed.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
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
HEALTH_URL = "http://127.0.0.1:5000/health"
PROCESSED_STREAM_URL = "http://127.0.0.1:5000/video_feed"
RUNTIME_RELOAD_WAIT_SECONDS = 7


@dataclass(frozen=True)
class SimulationTarget:
    filename: str
    target_date: date
    recording_start_hms: tuple[int, int, int]

    @property
    def source_path(self) -> Path:
        return PROJECT_DIR / "rstp" / "footage" / "may" / self.filename


@dataclass
class OverlayCaptureJob:
    process: subprocess.Popen
    temp_output: Path
    destination: Path
    output_name: str
    timeout_seconds: float


TARGETS = [
    SimulationTarget("6may.mp4", date(2026, 5, 6), (8, 0, 0)),
    SimulationTarget("7may.mp4", date(2026, 5, 7), (8, 0, 0)),
    SimulationTarget("8may.mp4", date(2026, 5, 8), (9, 0, 0)),
    SimulationTarget("11may.mp4", date(2026, 5, 11), (10, 0, 0)),
    SimulationTarget("12may.mp4", date(2026, 5, 12), (11, 0, 0)),
]


def info(message: str) -> None:
    print(f"[simulate] {message}", flush=True)


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"[simulate] ERROR: {message}")


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
    if status not in {"ok", "healthy", "waiting"}:
        fail(f"status edge worker tidak siap: {payload}")


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
    while time.time() < deadline:
        try:
            health = fetch_edge_health()
        except Exception:
            time.sleep(2)
            continue
        if str(health.get("camera_source") or "") == wanted:
            if health.get("has_frame"):
                info(f"edge sudah memproses {source_path.name}")
                return
        time.sleep(2)
    fail(f"edge tidak beralih ke sumber {source_path.name} dalam {timeout_seconds} detik")


def start_overlay_capture(target: SimulationTarget, duration_seconds: float) -> OverlayCaptureJob:
    output_name = recording_name_for(target, duration_seconds)
    destination = FOOTAGE_DIR / output_name
    temp_output = create_temp_capture_path(output_name)
    timeout_seconds = max(duration_seconds * 2 + 30, 60)
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-t",
        f"{max(duration_seconds, 1.0):.3f}",
        "-i",
        PROCESSED_STREAM_URL,
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
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        temp_output.unlink(missing_ok=True)
        fail(f"ffmpeg tidak tersedia untuk capture overlay: {exc}")

    info(f"capture overlay dimulai untuk {output_name}")
    return OverlayCaptureJob(
        process=process,
        temp_output=temp_output,
        destination=destination,
        output_name=output_name,
        timeout_seconds=timeout_seconds,
    )


def finish_overlay_capture(job: OverlayCaptureJob) -> str:
    try:
        stdout, stderr = job.process.communicate(timeout=job.timeout_seconds)
    except subprocess.TimeoutExpired:
        job.process.kill()
        stdout, stderr = job.process.communicate()
        job.temp_output.unlink(missing_ok=True)
        detail = (stderr or stdout or "").strip() or "capture timeout"
        fail(f"capture overlay timeout untuk {job.output_name}: {detail}")

    if job.process.returncode != 0 or not job.temp_output.exists():
        job.temp_output.unlink(missing_ok=True)
        detail = (stderr or stdout or "").strip() or "unknown ffmpeg error"
        fail(f"capture overlay gagal untuk {job.output_name}: {detail}")

    job.destination.unlink(missing_ok=True)
    job.temp_output.replace(job.destination)
    info(f"overlay recording tersimpan: {job.output_name}")
    return job.output_name


def wait_for_batch_to_settle(
    baseline_event_id: int,
    expected_duration_seconds: float,
    stable_seconds: int = 30,
) -> bool:
    start_ts = time.time()
    max_wait = max(int(expected_duration_seconds * 4 + 40), 75)
    last_change_ts = start_ts
    seen_new_rows = False
    previous_max_event_id = baseline_event_id

    while True:
        now = time.time()
        with with_connection() as connection:
            current_event_id = current_max_id(connection, "visit_events", "event_id")

        if current_event_id > previous_max_event_id:
            previous_max_event_id = current_event_id
            last_change_ts = now
            seen_new_rows = True

        if seen_new_rows and now - last_change_ts >= stable_seconds:
            return True

        if now - start_ts >= max_wait:
            return seen_new_rows

        time.sleep(3)


def replace_date_only(original: Optional[str], target_day: date) -> Optional[str]:
    if not original:
        return original
    raw = str(original).strip()
    if not raw:
        return original
    normalized = raw.replace("T", " ")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return original
    shifted = parsed.replace(year=target_day.year, month=target_day.month, day=target_day.day)
    return shifted.strftime("%Y-%m-%d %H:%M:%S.%f")


def redate_new_rows(
    target_day: date,
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
        for row in visit_events:
            shifted = replace_date_only(row["event_time"], target_day)
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
        for row in visitors:
            first_seen_at = replace_date_only(row["first_seen_at"], target_day)
            last_seen_at = replace_date_only(row["last_seen_at"], target_day)
            connection.execute(
                (
                    "UPDATE visitor_daily "
                    "SET visit_date = ?, first_seen_at = ?, last_seen_at = ? "
                    "WHERE visitor_daily_id = ?"
                ),
                (target_day.isoformat(), first_seen_at, last_seen_at, row["visitor_daily_id"]),
            )
        updated["visitor_daily"] = len(visitors)

        stats_rows = connection.execute(
            "SELECT stat_date, camera_id FROM daily_stats"
        ).fetchall()
        for row in stats_rows:
            stat_date = str(row["stat_date"] or "")
            if stat_date == target_day.isoformat():
                updated["daily_stats"] += 1
                continue
            if stat_date in reserved_stat_dates:
                continue
            connection.execute(
                "UPDATE daily_stats SET stat_date = ? WHERE stat_date = ? AND camera_id = ?",
                (target_day.isoformat(), stat_date, row["camera_id"]),
            )
            updated["daily_stats"] += 1

        if updated["daily_stats"] == 0:
            connection.execute(
                (
                    "INSERT INTO daily_stats "
                    "(stat_date, camera_id, total_events, unique_visitors, total_in, total_out, last_updated_at) "
                    "VALUES (?, ?, 0, 0, 0, 0, ?)"
                ),
                (target_day.isoformat(), 1, datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")),
            )
            updated["daily_stats"] = 1

        connection.commit()
    return updated


def recording_name_for(target: SimulationTarget, duration_seconds: float) -> str:
    start_dt = datetime(
        target.target_date.year,
        target.target_date.month,
        target.target_date.day,
        target.recording_start_hms[0],
        target.recording_start_hms[1],
        target.recording_start_hms[2],
    )
    end_dt = start_dt + timedelta(seconds=max(duration_seconds, 1.0))
    return (
        "cctv_recording_cam1_"
        f"{start_dt.strftime('%Y%m%d_%H%M%S')}_"
        f"{end_dt.strftime('%Y%m%d_%H%M%S')}.mp4"
    )


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


def main() -> int:
    validate_inputs(TARGETS)
    require_edge_online()

    runtime_payload = read_runtime_config()
    runtime_overrides = {
        "EDGE_CONFIG_REFRESH_SECONDS": "5",
        "EDGE_LOCAL_FILE_REPLAY_POST_EVENTS": "false",
        "EDGE_RECORDING_ENABLED": "false",
    }
    original_override_values = update_runtime_values(runtime_payload, runtime_overrides)
    wait_for_runtime_reload()

    info("menghapus data visitor lama")
    reset_database()
    info("mengosongkan backend/storage/footage dan recording_previews")
    clear_directory(FOOTAGE_DIR)
    clear_directory(PREVIEW_DIR)

    try:
        summaries: list[dict[str, Any]] = []
        reserved_stat_dates = {target.target_date.isoformat() for target in TARGETS}
        for target in TARGETS:
            duration_seconds = load_video_duration_seconds(target.source_path)
            with with_connection() as connection:
                baseline_event_id = current_max_id(connection, "visit_events", "event_id")
                baseline_visitor_daily_id = current_max_id(connection, "visitor_daily", "visitor_daily_id")

            runtime_payload = read_runtime_config()
            runtime_payload.setdefault("values", {})["EDGE_STREAM_URL"] = str(target.source_path.resolve())
            write_runtime_config(runtime_payload)
            wait_for_source(target.source_path)

            info(
                f"memutar {target.filename} untuk simulasi tanggal {target.target_date.isoformat()} "
                f"(durasi {duration_seconds:.1f}s)"
            )
            capture_job = start_overlay_capture(target, duration_seconds)
            got_new_events = wait_for_batch_to_settle(baseline_event_id, duration_seconds)
            recording_name = finish_overlay_capture(capture_job)
            shifted = redate_new_rows(
                target.target_date,
                baseline_event_id=baseline_event_id,
                baseline_visitor_daily_id=baseline_visitor_daily_id,
                reserved_stat_dates=reserved_stat_dates,
            )

            summaries.append(
                {
                    "target_date": target.target_date.isoformat(),
                    "source": target.filename,
                    "duration_seconds": round(duration_seconds, 2),
                    "got_new_events": got_new_events,
                    "shifted": shifted,
                    "recording_name": recording_name,
                }
            )
            info(
                f"selesai {target.filename}: "
                f"event={shifted['visit_events']}, unik={shifted['visitor_daily']}, "
                f"rekaman={recording_name}"
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
