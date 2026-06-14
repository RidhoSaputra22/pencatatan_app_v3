#!/usr/bin/env python3
"""Capture YOLO overlay recordings from local repaired clips without touching the database."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from simulate_may_footage import (
    FOOTAGE_DIR,
    PREVIEW_DIR,
    PROJECT_DIR,
    PROGRESS_LOG_INTERVAL_SECONDS,
    SOURCE_STOP_GRACE_SECONDS,
    SimulationTarget,
    describe_targets,
    discover_targets,
    fail,
    fetch_edge_health,
    finish_overlay_capture,
    info,
    load_video_duration_seconds,
    read_runtime_config,
    recording_name_for,
    require_edge_online,
    restore_runtime_values,
    start_overlay_capture,
    update_runtime_values,
    validate_inputs,
    wait_for_runtime_reload,
    wait_for_source,
    warn,
)


OVERLAY_BACKUP_DIR = PROJECT_DIR / "backend" / "storage" / "overlay_capture_backups"


@dataclass(frozen=True)
class SourceEndWaitResult:
    reached_source_end: bool
    reason: str
    elapsed_seconds: float
    final_health_status: str
    final_health_detail: Optional[str]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate ulang file rekaman overlay dari repaired clip tanpa "
            "reset database, tanpa hapus tabel, dan tanpa clear footage lain."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tampilkan target overlay yang akan diproses tanpa menjalankannya.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Timpa file rekaman target bila sudah ada. File lama dipindahkan ke "
            "backend/storage/overlay_capture_backups/."
        ),
    )
    parser.add_argument(
        "--day",
        action="append",
        default=[],
        help="Filter hari berdasarkan prefix filename, misalnya 11 atau 12.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Filter exact nama file source, misalnya 11_08-17.repaired.mp4.",
    )
    return parser


def normalize_day(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        fail("nilai --day tidak boleh kosong")
    if raw.isdigit():
        number = int(raw)
        if number < 1 or number > 31:
            fail(f"nilai --day di luar rentang 1-31: {value!r}")
        return f"{number:02d}"
    fail(f"nilai --day harus angka 1-31: {value!r}")


def filter_targets(
    targets: Iterable[SimulationTarget],
    *,
    days: list[str],
    sources: list[str],
) -> list[SimulationTarget]:
    selected = list(targets)
    if days:
        allowed_days = {normalize_day(day) for day in days}
        selected = [
            target
            for target in selected
            if target.filename[:2] in allowed_days
        ]
    if sources:
        allowed_sources = {str(item).strip() for item in sources if str(item).strip()}
        selected = [
            target for target in selected if target.filename in allowed_sources
        ]
    if not selected:
        fail("tidak ada target yang cocok dengan filter yang diberikan")
    return selected


def wait_for_source_end(
    source_path: Path,
    *,
    expected_duration_seconds: float,
) -> SourceEndWaitResult:
    start_ts = time.time()
    max_wait = max(
        int(expected_duration_seconds * 1.25 + max(SOURCE_STOP_GRACE_SECONDS, 600)),
        75,
    )
    last_progress_log_ts = start_ts
    wanted_source = str(source_path.resolve())
    seen_source_frames = False
    source_stop_seen_at: Optional[float] = None
    final_health_status = "unknown"
    final_health_detail: Optional[str] = None

    while True:
        now = time.time()
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
                            f"menunggu {SOURCE_STOP_GRACE_SECONDS} detik agar capture overlay flush dengan aman"
                        )

        if source_stop_seen_at is not None and now - source_stop_seen_at >= SOURCE_STOP_GRACE_SECONDS:
            return SourceEndWaitResult(
                reached_source_end=True,
                reason="source_stopped",
                elapsed_seconds=now - start_ts,
                final_health_status=final_health_status,
                final_health_detail=final_health_detail,
            )

        if now - last_progress_log_ts >= PROGRESS_LOG_INTERVAL_SECONDS:
            info(
                f"progress overlay {source_path.name}: elapsed={int(now - start_ts)}s, "
                f"status_edge={final_health_status}, "
                f"source_selesai={'ya' if source_stop_seen_at is not None else 'belum'}"
            )
            last_progress_log_ts = now

        if now - start_ts >= max_wait:
            return SourceEndWaitResult(
                reached_source_end=source_stop_seen_at is not None,
                reason="timeout",
                elapsed_seconds=now - start_ts,
                final_health_status=final_health_status,
                final_health_detail=final_health_detail,
            )

        time.sleep(3)


def overlay_backup_path(recording_path: Path) -> Path:
    OVERLAY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = OVERLAY_BACKUP_DIR / f"{recording_path.stem}.{stamp}{recording_path.suffix}"
    index = 1
    while candidate.exists():
        candidate = OVERLAY_BACKUP_DIR / f"{recording_path.stem}.{stamp}.{index}{recording_path.suffix}"
        index += 1
    return candidate


def build_plan(targets: Iterable[SimulationTarget]) -> list[dict[str, Any]]:
    plan = []
    for target in targets:
        output_name = recording_name_for(target)
        output_path = FOOTAGE_DIR / output_name
        source_duration_seconds = load_video_duration_seconds(target.source_path)
        plan.append(
            {
                "source": target.filename,
                "source_path": str(target.source_path.resolve()),
                "recording_name": output_name,
                "recording_path": str(output_path.resolve()),
                "recording_exists": output_path.exists(),
                "source_duration_seconds": round(source_duration_seconds, 2),
                "source_duration_hours": round(source_duration_seconds / 3600, 2),
            }
        )
    return plan


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    targets = filter_targets(
        discover_targets(),
        days=args.day,
        sources=args.source,
    )
    validate_inputs(targets)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": "dry-run",
                    "overwrite": bool(args.overwrite),
                    "targets": build_plan(targets),
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

    processed = 0
    skipped = 0

    try:
        for target in targets:
            output_name = recording_name_for(target)
            output_path = FOOTAGE_DIR / output_name
            preview_path = PREVIEW_DIR / f"{Path(output_name).stem}.browser.mp4"

            if output_path.exists() and not args.overwrite:
                skipped += 1
                warn(
                    f"skip {output_name}: file tujuan sudah ada. Pakai --overwrite jika ingin mengganti."
                )
                continue

            duration_seconds = load_video_duration_seconds(target.source_path)
            info(
                f"menyiapkan overlay {target.filename} -> {output_name} "
                f"({duration_seconds / 3600:.2f} jam source)"
            )

            runtime_payload = read_runtime_config()
            source_override = update_runtime_values(
                runtime_payload,
                {"EDGE_STREAM_URL": str(target.source_path.resolve())},
            )
            try:
                wait_for_source(target.source_path)
                capture_job = start_overlay_capture(target, duration_seconds)
                wait_result = wait_for_source_end(
                    target.source_path,
                    expected_duration_seconds=duration_seconds,
                )
                info(
                    f"capture {target.filename} selesai ditunggu dengan "
                    f"reason={wait_result.reason}, edge_status={wait_result.final_health_status}"
                )

                backup_path: Optional[Path] = None
                if output_path.exists():
                    backup_path = overlay_backup_path(output_path)
                    output_path.replace(backup_path)
                    info(f"file lama dipindahkan ke backup: {backup_path.name}")

                try:
                    recording_name = finish_overlay_capture(capture_job)
                except BaseException:
                    if backup_path is not None and backup_path.exists() and not output_path.exists():
                        backup_path.replace(output_path)
                    raise

                if wait_result.reason == "timeout" and not wait_result.reached_source_end:
                    output_path.unlink(missing_ok=True)
                    if backup_path is not None and backup_path.exists():
                        backup_path.replace(output_path)
                    fail(
                        f"clip {target.filename} timeout sebelum edge melaporkan EOF. "
                        f"Output {recording_name} tidak dianggap aman."
                    )

                preview_path.unlink(missing_ok=True)
                processed += 1
            finally:
                runtime_payload = read_runtime_config()
                restore_runtime_values(runtime_payload, source_override)
                wait_for_runtime_reload()
    finally:
        runtime_payload = read_runtime_config()
        restore_runtime_values(runtime_payload, original_override_values)
        wait_for_runtime_reload()

    print(
        json.dumps(
            {
                "ok": True,
                "processed": processed,
                "skipped": skipped,
                "overwrite": bool(args.overwrite),
                "targets": describe_targets(targets),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
