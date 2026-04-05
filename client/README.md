# Client CCTV Streamer

Script untuk mengirim footage CCTV dari PC lokal (client) ke server via UDP.

## Arsitektur

```
LOCAL (Client)                          SERVER
┌──────────────────┐               ┌─────────────────────────┐
│ CCTV             │               │ Backend (FastAPI)        │
│   ↓              │               │   UDP Receiver (:9999)   │
│ streamer.py      │──UDP frames──→│        ↓                 │
│                  │               │   /stream/relay (MJPEG)  │
│ Frontend (Next)  │←────HTTP─────│        ↓                 │
└──────────────────┘               │   Edge Worker (YOLOv5)   │
                                   └─────────────────────────┘
```

## Instalasi

```bash
pip install -r requirements.txt
```

## Penggunaan

```bash
# Dari webcam (index 0)
python streamer.py --source 0 --server-ip <IP_SERVER> --server-port 9999

# Dari CCTV via RTSP
python streamer.py --source "rtsp://admin:admin@192.168.1.50:554/live" --server-ip <IP_SERVER>

# Dari file rekaman
python streamer.py --source "/path/to/recording.mp4" --server-ip <IP_SERVER>
```

## Parameter

| Parameter       | Default     | Keterangan                          |
|-----------------|-------------|-------------------------------------|
| `--source`      | `0`         | Sumber video (webcam/RTSP/file)     |
| `--server-ip`   | `127.0.0.1` | IP server backend                  |
| `--server-port` | `9999`      | Port UDP di server                  |
| `--quality`     | `70`        | JPEG quality (1-100)                |
| `--max-fps`     | `15`        | Batas FPS pengiriman                |
| `--width`       | `1280`      | Resize width                        |
| `--height`      | `720`       | Resize height                       |
| `--loop`        | aktif       | Loop video file jika habis          |
| `--no-loop`     | -           | Jangan loop video file              |

## Konfigurasi Server

Di server, set environment variable di `.env`:
```
EDGE_STREAM_URL=http://localhost:8000/stream/relay
UDP_RELAY_HOST=0.0.0.0
UDP_RELAY_PORT=9999
```
