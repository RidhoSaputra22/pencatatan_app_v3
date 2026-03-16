"""
Edge Worker untuk Visitor Monitoring
- Deteksi manusia menggunakan YOLOv5
- Tracking dengan CentroidTracker / DeepSORT
- Menghitung pengunjung unik harian (visitor_key)
- Mengirim event ke backend API
- Menyediakan live video feed (MJPEG) di port EDGE_STREAM_PORT

Catatan arsitektur:
  - Edge worker membaca stream dari kamera (RTSP/HTTP/webcam langsung)
  - YOLO + tracker memproses frame
  - Frame hasil proses di-stream via Flask (port 5000 default)
  - Frontend dashboard mengambil feed dari port ini
  - TIDAK perlu menjalankan rtsp_webcam_server.py terpisah
    jika EDGE_STREAM_URL di-set ke index webcam (misal "0")
"""
import threading
import time

from core.config import MODE, EDGE_STREAM_PORT
from core.streaming import start_flask_server
from core.loops import real_loop


def main():
    """Main entry point"""
    # Start Flask streaming server in background thread
    # Server ini menyajikan frame YOLO+tracking ke frontend dashboard
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
    flask_thread.start()
    print(f"[main] Flask streaming server started on port {EDGE_STREAM_PORT}")

    # Wait a bit for Flask to start
    time.sleep(1)

    # Run detection + tracking loop
    real_loop()


if __name__ == "__main__":
    main()
