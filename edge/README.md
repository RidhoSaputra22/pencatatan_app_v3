# Edge Worker - Modular Structure

Edge worker mendeteksi manusia (YOLOv5), tracking, dan menyajikan video feed yang sudah diproses.

## Arsitektur

```
Kamera (webcam/RTSP/HTTP)
     │
     ▼
[worker.py] ──── Flask server (port 5000)
     │                  └── /video_feed (MJPEG, frame + overlay)
     │                  └── /health
     ▼
[Backend API] ◄── kirim event kunjungan
```

**Catatan**: Edge worker langsung membaca webcam (EDGE_STREAM_URL=0).
Tidak perlu menjalankan `rstp/rtsp_webcam_server.py` terpisah.

## Struktur Folder

```
edge/
├── worker.py              # Entry point utama (36 lines)
├── core/                  # Core modules
│   ├── __init__.py
│   ├── config.py          # Environment configuration
│   ├── api_client.py      # Backend API communication
│   ├── streaming.py       # Flask video streaming server
│   ├── tracker.py         # CentroidTracker class
│   ├── detection.py       # YOLOv5 & ROI utilities
│   ├── visualization.py   # Drawing functions
│   └── loops.py           # Processing loops (fake_loop, real_loop)
├── requirements.txt
└── yolov5s.pt
```

## Modul-Modul

### 1. `worker.py` - Main Entry Point
- Entry point aplikasi
- Menginisialisasi Flask streaming server
- Memilih mode (fake/real) dan menjalankan loop yang sesuai

### 2. `core/config.py` - Configuration
- Load environment variables dari `.env`
- Menyediakan konstanta konfigurasi:
  - Mode (FAKE/REAL)
  - Camera ID
  - YOLOv5 parameters
  - Tracking parameters
  - Backend API URLs

### 3. `core/api_client.py` - API Communication
- `login_token()` - Autentikasi ke backend
- `get_camera_config()` - Fetch camera config
- `get_counting_areas()` - Fetch ROI config
- `send_visitor_event()` - Kirim event ke backend
- `generate_visitor_key()` - Generate unique visitor key

### 4. `core/streaming.py` - Video Streaming
- Flask server untuk MJPEG streaming
- Thread-safe frame sharing
- Health check endpoint
- Route: `/video_feed` dan `/health`

### 5. `core/tracker.py` - Object Tracking
- `Track` dataclass - Representasi tracked object
- `CentroidTracker` class - Simple centroid tracking
  - Association algorithm
  - Track lifecycle management

### 6. `core/detection.py` - Detection & ROI
- `load_yolov5_model()` - Load YOLOv5 model
- `parse_roi()` - Parse ROI dari JSON/list
- `point_in_roi()` - Check if point inside polygon

### 7. `core/visualization.py` - Visualization
- `draw_roi_polygon()` - Draw ROI pada frame
- `draw_bounding_boxes()` - Draw bbox dengan status
- `draw_info_overlay()` - Draw info text

### 8. `core/loops.py` - Processing Loops
- `fake_loop()` - Mode testing dengan data random
- `real_loop()` - Mode production dengan YOLOv5

## Cara Menggunakan

### Menjalankan Worker

```bash
cd edge
python worker.py
```

### Mode yang Tersedia

Mode REAL dengan YOLOv5:
```bash
# Di .env
EDGE_MODE=real
EDGE_STREAM_URL=0          # webcam langsung
# EDGE_STREAM_URL=rtsp://ip:port/stream   # IP camera
```

## Keuntungan Refactoring

1. ✅ **Separation of Concerns** - Setiap modul punya tanggung jawab spesifik
2. ✅ **Maintainability** - Mudah mencari dan memperbaiki bug
3. ✅ **Testability** - Mudah untuk unit testing
4. ✅ **Reusability** - Function bisa dipakai ulang
5. ✅ **Readability** - Kode lebih mudah dibaca
6. ✅ **Scalability** - Mudah menambah fitur baru

## Perubahan dari Versi Lama

- ❌ Removed: `webcam_simple_loop()` - tidak dipakai
- ✅ Organized: Semua function dikelompokkan by concern
- ✅ Simplified: `worker.py` hanya 36 lines
- ✅ Modular: 8 modul terpisah untuk maintainability

## Dependencies

Lihat `requirements.txt` untuk daftar lengkap dependencies.

Key dependencies:
- `opencv-python` - Computer vision
- `torch` - YOLOv5 inference
- `flask` - Video streaming
- `requests` - API communication
- `python-dotenv` - Environment config
