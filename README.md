# Visitor Monitoring System MVP

Sistem monitoring jumlah pengunjung perpustakaan berbasis CCTV dengan YOLOv5 + tracking.

## Fitur Utama

- Deteksi manusia menggunakan **YOLOv5**
- **Tracking** (DeepSORT / Centroid Tracker)
- **Penyaringan pegawai** dengan face recognition berbasis InsightFace/ArcFace
- **Pengunjung Unik Harian** (masuk 2-3 kali dalam sehari tetap dihitung 1 kali)
- **Backup footage hasil YOLO** otomatis per segmen 10 menit
- **Dashboard** dengan statistik real-time + live camera preview
- Filter per tanggal/periode
- Export laporan CSV

## Arsitektur (Tanpa Docker)

```
              ┌──────────────────────────────────────┐
              │            Frontend (Next.js)         │
              │           http://localhost:3000       │
              └──────┬───────────────────┬───────────┘
                     │ API               │ WebRTC video
                     ▼                   ▼
    ┌────────────────────┐   ┌───────────────────────────┐
    │  Backend (FastAPI)  │   │  Edge Worker (port 5000)   │
    │  http://localhost   │   │  /webrtc/offer             │
    │  :8000              │◄──│  YOLO + Tracking           │
    │  SQLite DB          │   │  /video_feed (fallback)    │
    │                     │   │  Kirim event → backend     │
    └────────────────────┘   └───────────┬───────────────┘
                                         │
                              ┌──────────┴──────────┐
                              │   Kamera (sumber)    │
                              │  webcam / RTSP / HTTP│
                              └─────────────────────┘
```

**Hanya butuh 3 terminal**: Backend, Edge Worker, Frontend.
`rstp/rtsp_webcam_server.py` TIDAK perlu dijalankan jika webcam di PC yang sama.

## Teknologi

- **Backend**: FastAPI + SQLite (SQLModel)
- **Edge/AI**: YOLOv5 + OpenCV + DeepSORT/CentroidTracker + FastAPI/Uvicorn + aiortc
- **Employee filter**: InsightFace face detection + ArcFace embedding + registry pegawai
- **Frontend**: Next.js 14

## Struktur Folder

```
├── backend/           # FastAPI backend + SQLite
│   ├── app/
│   │   ├── main.py    # API endpoints
│   │   ├── models.py  # Database models (SQLModel)
│   │   ├── db.py      # Database connection
│   │   ├── auth.py    # JWT Authentication
│   │   └── settings.py
│   └── requirements.txt
├── edge/              # Edge worker (YOLO detection + streaming)
│   ├── worker.py      # Entry point: jalankan YOLO + serve video
│   ├── core/
│   │   ├── loops.py       # Main detection loop
│   │   ├── streaming.py   # WebRTC server + MJPEG fallback (port 5000)
│   │   ├── detection.py   # YOLOv5 wrapper
│   │   ├── tracker.py     # DeepSORT / CentroidTracker
│   │   ├── reid.py        # Re-identification
│   │   ├── visualization.py # Draw overlay
│   │   ├── api_client.py  # Kirim event ke backend
│   │   └── config.py      # Environment variables
│   └── requirements.txt
├── frontend/          # Next.js dashboard
│   ├── app/
│   │   ├── page.js        # Redirect ke login
│   │   ├── login/         # Login page
│   │   ├── dashboard/     # Dashboard + live camera
│   │   └── camera/        # Konfigurasi kamera & ROI
│   └── package.json
├── rstp/              # (OPSIONAL) Webcam HTTP relay server
│   └── rtsp_webcam_server.py
├── backend/storage/runtime_config.json  # Tuning runtime dari dashboard
└── .env               # Bootstrap, secret, dan endpoint service
```

## Cara Menjalankan (Manual, tanpa Docker)

Catatan versi Python:
- Mode dasar project berjalan di Python 3.12+.
- Fitur filter pegawai berbasis `InsightFace` saat ini sebaiknya dijalankan dengan **Python 3.12**.
- Jika environment dibuat dengan Python 3.13, `pip install -r requirements.txt` akan melewati `insightface` dan `onnxruntime`, sehingga aplikasi tetap bisa jalan tetapi filter pegawai nonaktif.

### 1. Setup Backend

```bash
cd backend
python3.12 -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend: http://localhost:8000

### 2. Setup Edge Worker

```bash
cd edge
python3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python worker.py
```

Edge worker akan:
- Baca kamera dari runtime config `EDGE_STREAM_URL`, lalu fallback ke stream kamera di database jika kosong
- Deteksi + tracking manusia
- Kirim event ke backend
- Publish hasil overlay ke browser via WebRTC (`POST /webrtc/offer`)
- Tetap expose MJPEG fallback di: http://localhost:5000/video_feed

### 3. Setup Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:3000

## Konfigurasi

`.env` dipakai untuk bootstrap dan secret saja: database, JWT, akun awal,
alamat service, port, dan kredensial edge. Tuning YOLO, tracking, ReID, stream,
dan face filtering disimpan di `backend/storage/runtime_config.json` lewat menu
**Konfigurasi** di dashboard.

```env
# Backend bootstrap
APP_ENV=dev
JWT_SECRET=your-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
DATABASE_URL=sqlite:///./visitors.db

# Edge bootstrap
EDGE_MODE=real
EDGE_CAMERA_ID=1
EDGE_STREAM_PORT=5000    # Port signaling WebRTC + MJPEG fallback
EDGE_WEBRTC_ENABLED=true
EDGE_WEBRTC_ICE_SERVERS=[{"urls":"stun:stun.l.google.com:19302"}]
BACKEND_URL=http://localhost:8000

# Face model bootstrap
INSIGHTFACE_MODEL_NAME=buffalo_l
INSIGHTFACE_DET_SIZE=640

# Frontend
FRONTEND_PORT=3000
```

### Tuning Runtime

Ubah nilai seperti `EDGE_STREAM_URL`, `EDGE_PROCESSING_MAX_FPS`,
`EDGE_STREAM_MAX_FPS`, `YOLO_CONF`, `YOLOV5_WEIGHTS`, tracking, ReID, dan face
filtering dari dashboard. Backend menyimpan perubahan ke
`backend/storage/runtime_config.json`; edge worker mengambilnya lewat endpoint
`/api/admin/runtime-config`.

Catatan:
- `EDGE_PROCESSING_MAX_FPS` membatasi ritme inferensi/tracking agar CPU/GPU tidak penuh terus.
- `EDGE_STREAM_MAX_FPS` mengatur ritme frame ke browser; stream akan mengulang frame terakhir jika inferensi lebih lambat.
- `FACE_DETECTION_FRAME_INTERVAL` mengurangi beban InsightFace dengan tidak menjalankan deteksi wajah di setiap frame.

## Kamera: Webcam vs RTSP

### Webcam Langsung (paling mudah)
```text
EDGE_STREAM_URL=0
```
Isi `EDGE_STREAM_URL` di dashboard dengan `0`. Edge worker langsung membuka webcam index 0.

### IP Camera (RTSP)
```text
EDGE_STREAM_URL=rtsp://192.168.1.100:554/stream
```

### HTTP Relay (opsional, kasus khusus)
Jika kamera di PC lain, jalankan `rstp/rtsp_webcam_server.py` di PC kamera:
```text
EDGE_STREAM_URL=http://192.168.1.50:8081/video
```

## Backup Footage YOLO

- Worker edge sekarang menyimpan **frame yang sudah diberi overlay YOLO/tracking** ke file MP4 otomatis.
- Satu file backup berisi **10 menit** video dan file selesai akan muncul di `backend/storage/footage`.
- Nama file memakai format `cctv_recording_cam1_YYYYmmdd_HHMMSS_YYYYmmdd_HHMMSS.mp4`.
- File yang masih berjalan tidak ditampilkan ke daftar footage sampai segmennya lengkap.

Konfigurasi utama:
- `EDGE_RECORDING_ENABLED=true` untuk mengaktifkan backup otomatis.
- `EDGE_RECORDING_SEGMENT_MINUTES=10` untuk durasi setiap segmen backup.
- `EDGE_RECORDING_FPS=0` berarti mengikuti `EDGE_PROCESSING_MAX_FPS`; jika ingin paksa FPS tertentu, isi misalnya `12`.

## Database Schema

Sesuai dengan konsep proyek:

1. **roles** - Role pengguna (ADMIN, OPERATOR)
2. **users** - Data pengguna
3. **cameras** - Konfigurasi kamera
4. **counting_areas** - Area ROI per kamera
5. **employees** - Registry pegawai + embedding wajah referensi
6. **visitor_daily** - Pengunjung unik harian pelanggan
7. **visit_events** - Log event kunjungan + klasifikasi CUSTOMER/EMPLOYEE
8. **daily_stats** - Statistik harian pelanggan (pegawai diabaikan)

## Alur Filter Pegawai

```text
Camera
  -> YOLOv5 (deteksi orang)
  -> DeepSORT (tracking ID)
  -> InsightFace (face detection + ArcFace embedding)
  -> Cek database pegawai
  -> EMPLOYEE: event dilog tetapi tidak masuk statistik pelanggan
  -> CUSTOMER: event dihitung ke visitor_daily dan daily_stats
```

Catatan implementasi:
- Project ini memakai edge worker Python tunggal, jadi deteksi wajah dan embedding ArcFace disatukan lewat `InsightFace` agar sesuai dengan struktur repo yang sudah ada.
- Jika registry pegawai belum diisi, sistem tetap berjalan dan semua orang diperlakukan sebagai pelanggan.

## Logika Pengunjung Unik Harian

```
visitor_key = hash(camera_id + track_id + tanggal)

Saat ada event:
1. Cek (visit_date, visitor_key) di visitor_daily
2. Jika BELUM ADA → insert (unik bertambah)
3. Jika SUDAH ADA → update last_seen_at (unik tidak bertambah)
```

## API Endpoints

### Auth
- `POST /api/auth/login` - Login
- `GET /api/me` - Get current user

### Cameras
- `GET /api/cameras` - List cameras
- `GET /api/cameras/{id}` - Get camera
- `PUT /api/cameras/{id}` - Update camera
- `GET /api/cameras/{id}/areas` - Get counting areas

### Employees
- `GET /api/employees` - List pegawai
- `POST /api/employees` - Tambah pegawai + upload foto referensi
- `PUT /api/employees/{id}` - Update data/foto pegawai
- `GET /api/employees/registry` - Registry embedding aktif untuk edge worker

### Statistics
- `GET /api/stats/daily` - Daily stats
- `GET /api/stats/summary` - Dashboard summary

### Reports
- `GET /api/reports/csv` - Export CSV

### Edge Integration
- `POST /api/events/ingest` - Receive events from edge

## Default Login

- Username: `admin`
- Password: `admin123`

## Screenshots

Dashboard menampilkan:
- Total event kunjungan
- **Pengunjung unik harian** (highlight)
- Total masuk/keluar
- Live camera preview
- Tabel statistik per kamera
