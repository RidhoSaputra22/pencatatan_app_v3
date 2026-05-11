#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


EDGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = EDGE_DIR.parent
if str(EDGE_DIR) not in sys.path:
    sys.path.insert(0, str(EDGE_DIR))

from core.recording import _finalize_recording_file, _optimizing_path


AUTO_RECORDING_PREFIX = "cctv_recording_cam"
PREVIEW_SUFFIXES = (".browser.mp4", ".tmp.mp4")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate existing CCTV recordings to H.264 in place."
    )
    parser.add_argument(
        "--footage-dir",
        default=str(PROJECT_DIR / "backend" / "storage" / "footage"),
        help="Directory containing archived recordings.",
    )
    parser.add_argument(
        "--preview-dir",
        default=str(PROJECT_DIR / "backend" / "storage" / "recording_previews"),
        help="Directory containing browser preview copies.",
    )
    parser.add_argument(
        "--include-manual",
        action="store_true",
        help="Also migrate non-automatic MP4 uploads.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without changing files.",
    )
    return parser


def _probe_codec(file_path: Path) -> str:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return (result.stdout or "").strip().lower()


def _preview_paths(recording_path: Path, preview_dir: Path) -> list[Path]:
    stem = recording_path.stem
    return [preview_dir / f"{stem}{suffix}" for suffix in PREVIEW_SUFFIXES]


def _size_mb(file_path: Path) -> float:
    return round(file_path.stat().st_size / (1024 * 1024), 2)


def _should_skip(file_path: Path, include_manual: bool) -> bool:
    if not file_path.is_file():
        return True
    if file_path.suffix.lower() != ".mp4":
        return True
    if file_path.name.endswith(".partial.mp4") or file_path.name.endswith(".optimizing.mp4"):
        return True
    if not include_manual and not file_path.name.startswith(AUTO_RECORDING_PREFIX):
        return True
    return False


def main() -> int:
    args = _build_parser().parse_args()
    footage_dir = Path(args.footage_dir).expanduser().resolve()
    preview_dir = Path(args.preview_dir).expanduser().resolve()

    if not footage_dir.exists():
        print(f"Footage directory not found: {footage_dir}", file=sys.stderr)
        return 1

    candidates = sorted(footage_dir.iterdir())
    migrated = 0
    skipped = 0
    cleaned_preview = 0
    bytes_before = 0
    bytes_after = 0

    for file_path in candidates:
        if _should_skip(file_path, args.include_manual):
            continue

        codec = _probe_codec(file_path)
        if codec == "h264":
            skipped += 1
            for preview_path in _preview_paths(file_path, preview_dir):
                if preview_path.exists():
                    if not args.dry_run:
                        preview_path.unlink(missing_ok=True)
                    cleaned_preview += 1
            print(f"SKIP  {file_path.name} already h264")
            continue

        size_before = file_path.stat().st_size
        optimizing_path = _optimizing_path(file_path)
        print(
            f"{'PLAN' if args.dry_run else 'MOVE'}  {file_path.name} "
            f"({codec or 'unknown'}, {_size_mb(file_path)} MB)"
        )

        if args.dry_run:
            migrated += 1
            bytes_before += size_before
            continue

        if optimizing_path.exists():
            optimizing_path.unlink(missing_ok=True)
        file_path.replace(optimizing_path)
        _finalize_recording_file(optimizing_path, file_path)

        if not file_path.exists():
            raise RuntimeError(f"Final file missing after migration: {file_path}")

        for preview_path in _preview_paths(file_path, preview_dir):
            if preview_path.exists():
                preview_path.unlink(missing_ok=True)
                cleaned_preview += 1

        migrated += 1
        bytes_before += size_before
        bytes_after += file_path.stat().st_size

    if args.dry_run:
        print(f"\nDry run: {migrated} file(s) would be migrated.")
        return 0

    saved_bytes = max(0, bytes_before - bytes_after)
    saved_mb = round(saved_bytes / (1024 * 1024), 2)
    before_mb = round(bytes_before / (1024 * 1024), 2)
    after_mb = round(bytes_after / (1024 * 1024), 2)

    print("\nMigration complete.")
    print(f"Migrated files : {migrated}")
    print(f"Skipped h264   : {skipped}")
    print(f"Preview cleaned: {cleaned_preview}")
    print(f"Before total   : {before_mb} MB")
    print(f"After total    : {after_mb} MB")
    print(f"Saved          : {saved_mb} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
