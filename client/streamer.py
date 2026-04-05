"""
Client Streamer — Mengirim footage CCTV dari sisi lokal ke server via UDP.

Arsitektur (sesuai diagram):
  LOCAL                               SERVER
  ┌──────────────┐                   ┌──────────────────────┐
  │ CCTV         │                   │ Backend              │
  │   ↓          │                   │  (UDP receiver)      │
  │ Client       │───UDP frames───→  │   ↓                  │
  │ (script ini) │                   │  /stream/relay       │
  │              │←───HTTP──────────│   ↓                  │
  │ Frontend     │                   │  Edge Worker (YOLO)  │
  └──────────────┘                   └──────────────────────┘

Cara pakai:
  python streamer.py --source 0 --server-ip 192.168.1.100 --server-port 9999
  python streamer.py --source rtsp://admin:admin@192.168.1.50:554/live
  python streamer.py --source /path/to/cctv-recording.mp4

Opsi:
  --source      : Sumber video (webcam index / RTSP URL / file path)
  --server-ip   : IP server backend yang menerima UDP stream
  --server-port : Port UDP di server (default: 9999)
  --quality     : JPEG quality 1-100 (default: 70)
  --max-fps     : Batas FPS pengiriman (default: 15)
  --width       : Resize width sebelum kirim (default: 1280)
  --height      : Resize height sebelum kirim (default: 720)
  --loop        : Loop video file jika habis
"""
import argparse
import os
import socket
import struct
import sys
import time

import cv2
import numpy as np


# Maximum safe UDP payload (~65507 bytes minus headers).
# We split large frames into chunks.
MAX_UDP_PACKET = 60000


def open_source(source: str):
    """Open a video source: webcam index, RTSP URL, or file path."""
    if source.isdigit():
        cap = cv2.VideoCapture(int(source))
    else:
        cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def is_file_source(source: str) -> bool:
    """Check if source is a local file."""
    if source.isdigit():
        return False
    if source.startswith(("rtsp://", "http://", "https://")):
        return False
    return os.path.isfile(source)


def stream_to_server(
    source: str,
    server_ip: str,
    server_port: int,
    quality: int = 70,
    max_fps: int = 15,
    width: int = 1280,
    height: int = 720,
    loop: bool = True,
):
    """Capture frames from source and send them via UDP to the server."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    frame_interval = 1.0 / max_fps if max_fps > 0 else 0.0
    frame_id = 0

    print(f"[client] Source       : {source}")
    print(f"[client] Server       : {server_ip}:{server_port}")
    print(f"[client] JPEG quality : {quality}")
    print(f"[client] Max FPS      : {max_fps}")
    print(f"[client] Resolution   : {width}x{height}")
    print(f"[client] Loop file    : {loop}")
    print()

    file_mode = is_file_source(source)
    cap = None

    try:
        while True:
            # Open / reopen source
            if cap is None or not cap.isOpened():
                cap = open_source(source)
                if not cap.isOpened():
                    print("[client] Gagal membuka sumber video. Retry 3s...")
                    time.sleep(3)
                    continue
                print(f"[client] Sumber video terhubung.")

            t_start = time.monotonic()
            ok, frame = cap.read()

            if not ok or frame is None:
                if file_mode and loop:
                    print("[client] Video habis, mengulang dari awal...")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                elif file_mode:
                    print("[client] Video habis. Selesai.")
                    break
                else:
                    print("[client] Frame gagal dibaca. Reconnecting...")
                    cap.release()
                    cap = None
                    time.sleep(2)
                    continue

            # Resize
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height))

            # Encode to JPEG
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if not ok:
                continue

            data = buf.tobytes()
            data_len = len(data)
            frame_id += 1

            # Send frame as UDP chunks
            # Header format: [frame_id (4B)][total_chunks (2B)][chunk_idx (2B)][data]
            total_chunks = (data_len + MAX_UDP_PACKET - 1) // MAX_UDP_PACKET
            for i in range(total_chunks):
                start = i * MAX_UDP_PACKET
                end = min(start + MAX_UDP_PACKET, data_len)
                chunk = data[start:end]

                header = struct.pack("!IHH", frame_id % (2**32), total_chunks, i)
                try:
                    sock.sendto(header + chunk, (server_ip, server_port))
                except OSError as e:
                    print(f"[client] Send error: {e}")
                    break

            if frame_id % 100 == 0:
                print(f"[client] Sent frame #{frame_id} ({data_len} bytes, {total_chunks} chunk(s))")

            # Rate limit
            if frame_interval > 0:
                elapsed = time.monotonic() - t_start
                sleep_for = frame_interval - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)

    except KeyboardInterrupt:
        print("\n[client] Dihentikan.")
    finally:
        if cap is not None:
            cap.release()
        sock.close()


def main():
    parser = argparse.ArgumentParser(description="Client CCTV Streamer — kirim footage via UDP ke server")
    parser.add_argument("--source", default="0", help="Sumber video: webcam index / RTSP URL / file path")
    parser.add_argument("--server-ip", default="127.0.0.1", help="IP server backend")
    parser.add_argument("--server-port", type=int, default=9999, help="UDP port server")
    parser.add_argument("--quality", type=int, default=70, help="JPEG quality (1-100)")
    parser.add_argument("--max-fps", type=int, default=15, help="Batas FPS pengiriman")
    parser.add_argument("--width", type=int, default=1280, help="Resize width")
    parser.add_argument("--height", type=int, default=720, help="Resize height")
    parser.add_argument("--loop", action="store_true", default=True, help="Loop video file")
    parser.add_argument("--no-loop", dest="loop", action="store_false", help="Jangan loop video")
    args = parser.parse_args()

    stream_to_server(
        source=args.source,
        server_ip=args.server_ip,
        server_port=args.server_port,
        quality=max(1, min(100, args.quality)),
        max_fps=max(1, args.max_fps),
        width=args.width,
        height=args.height,
        loop=args.loop,
    )


if __name__ == "__main__":
    main()
