"""
Edge Worker untuk Visitor Monitoring
- Deteksi manusia menggunakan YOLOv5
- Tracking dengan CentroidTracker / DeepSORT
- Menghitung pengunjung unik harian (visitor_key)
- Mengirim event ke backend API
- Menyediakan live video feed WebRTC ke browser dengan MJPEG fallback

Catatan arsitektur:
  - Edge worker membaca stream dari kamera (RTSP/HTTP/webcam langsung)
  - YOLO + tracker memproses frame
  - Frame hasil proses dipublish sebagai WebRTC video track
  - MJPEG tetap tersedia sebagai fallback/ROI editor
  - TIDAK perlu menjalankan rtsp_webcam_server.py terpisah
    jika EDGE_STREAM_URL di-set ke index webcam (misal "0")
"""
import threading
import time

from core.config import MODE, EDGE_STREAM_PORT
from core.logger import get_logger
from core.streaming import start_flask_server
from core.loops import real_loop

log = get_logger("main")


def main():
    """Main entry point"""
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
    flask_thread.start()
    log.info("Edge video server started on port %d", EDGE_STREAM_PORT)

    # Wait a bit for the video server to start
    time.sleep(1)

    # Run detection + tracking loop
    real_loop()


if __name__ == "__main__":
    main()
