#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
FOOTAGE_DIR = PROJECT_DIR / "backend" / "storage" / "footage"
PREVIEW_DIR = PROJECT_DIR / "backend" / "storage" / "recording_previews"
SOURCE_ROOT = PROJECT_DIR / "rstp" / "footage" / "merged_mp4_08_17"
BACKUP_DIR = PROJECT_DIR / "backend" / "storage" / "footage_invalid_backup"
AUTO_RECORDING_PREFIX = "cctv_recording_cam"
RECORDING_NAME_PATTERN = re.compile(
    r"^cctv_recording_cam(?P<camera_id>\d+)_(?P<start_date>\d{8})_(?P<start_time>\d{6})_"
    r"(?P<end_date>\d{8})_(?P<end_time>\d{6})\.mp4$"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Repair invalid simulated CCTV recordings by relinking them to the "
            "matching *.repaired.mp4 source clip."
        )
    )
    parser.add_argument(
        "--footage-dir",
        default=str(FOOTAGE_DIR),
        help="Directory containing generated CCTV recordings.",
    )
    parser.add_argument(
        "--source-root",
        default=str(SOURCE_ROOT),
        help="Root directory containing YYYYMM/DD_HH-HH.repaired.mp4 source clips.",
    )
    parser.add_argument(
        "--preview-dir",
        default=str(PREVIEW_DIR),
        help="Directory containing browser preview copies that should be cleared.",
    )
    parser.add_argument(
        "--backup-dir",
        default=str(BACKUP_DIR),
        help="Directory used to stash invalid files before replacement.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be repaired without changing any files.",
    )
    return parser


def probe_video_file(path: Path) -> tuple[bool, str]:
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


def iter_recordings(footage_dir: Path) -> list[Path]:
    items = []
    for path in sorted(footage_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() != ".mp4":
            continue
        if path.name.endswith(".partial.mp4") or path.name.endswith(".optimizing.mp4"):
            continue
        if not path.name.startswith(AUTO_RECORDING_PREFIX):
            continue
        items.append(path)
    return items


def source_candidate_for(recording_path: Path, source_root: Path) -> Path | None:
    match = RECORDING_NAME_PATTERN.fullmatch(recording_path.name)
    if not match:
        return None

    start_date = match.group("start_date")
    start_time = match.group("start_time")
    end_date = match.group("end_date")
    end_time = match.group("end_time")
    if start_time[2:] != "0000" or end_time[2:] != "0000":
        return None

    month_dir = start_date[:6]
    day = start_date[6:8]
    start_hour = start_time[:2]
    end_hour = end_time[:2]
    if end_date != start_date:
        return None
    return source_root / month_dir / f"{day}_{start_hour}-{end_hour}.repaired.mp4"


def unique_backup_path(path: Path) -> Path:
    candidate = path
    index = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}.{index}{path.suffix}")
        index += 1
    return candidate


def preview_path_for(recording_path: Path, preview_dir: Path) -> Path:
    return preview_dir / f"{recording_path.stem}.browser.mp4"


def link_or_copy(source_path: Path, destination_path: Path) -> str:
    try:
        os.link(source_path, destination_path)
        return "hardlink"
    except OSError:
        shutil.copy2(source_path, destination_path)
        return "copy"


def main() -> int:
    args = build_parser().parse_args()
    footage_dir = Path(args.footage_dir).expanduser().resolve()
    source_root = Path(args.source_root).expanduser().resolve()
    preview_dir = Path(args.preview_dir).expanduser().resolve()
    backup_dir = Path(args.backup_dir).expanduser().resolve()

    if not footage_dir.exists():
        raise SystemExit(f"footage directory tidak ditemukan: {footage_dir}")
    if not source_root.exists():
        raise SystemExit(f"source root tidak ditemukan: {source_root}")

    repaired = 0
    skipped_valid = 0
    skipped_unmapped = 0
    failed = 0

    for recording_path in iter_recordings(footage_dir):
        is_valid, detail = probe_video_file(recording_path)
        if is_valid:
            skipped_valid += 1
            print(f"SKIP  {recording_path.name} valid ({detail})")
            continue

        source_path = source_candidate_for(recording_path, source_root)
        if source_path is None:
            skipped_unmapped += 1
            print(f"MISS  {recording_path.name} tidak punya mapping source ({detail})")
            continue
        if not source_path.exists():
            failed += 1
            print(f"FAIL  {recording_path.name} source tidak ditemukan: {source_path}")
            continue

        source_valid, source_detail = probe_video_file(source_path)
        if not source_valid:
            failed += 1
            print(f"FAIL  {recording_path.name} source invalid: {source_path.name} ({source_detail})")
            continue

        backup_path = unique_backup_path(backup_dir / recording_path.name)
        preview_path = preview_path_for(recording_path, preview_dir)
        action = "PLAN" if args.dry_run else "FIX"
        print(
            f"{action}  {recording_path.name} <= {source_path.relative_to(source_root)} "
            f"(rusak: {detail}; source: {source_detail})"
        )

        if args.dry_run:
            repaired += 1
            continue

        backup_dir.mkdir(parents=True, exist_ok=True)
        recording_path.replace(backup_path)
        try:
            mode = link_or_copy(source_path, recording_path)
        except Exception:
            backup_path.replace(recording_path)
            raise

        preview_path.unlink(missing_ok=True)
        replaced_valid, replaced_detail = probe_video_file(recording_path)
        if not replaced_valid:
            recording_path.unlink(missing_ok=True)
            backup_path.replace(recording_path)
            failed += 1
            print(
                f"FAIL  {recording_path.name} hasil penggantian invalid "
                f"({replaced_detail}); file asli dipulihkan."
            )
            continue

        repaired += 1
        print(f"OK    {recording_path.name} repaired via {mode} ({replaced_detail})")

    print("")
    print(f"Repaired        : {repaired}")
    print(f"Skipped valid   : {skipped_valid}")
    print(f"Skipped unmapped: {skipped_unmapped}")
    print(f"Failed          : {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
