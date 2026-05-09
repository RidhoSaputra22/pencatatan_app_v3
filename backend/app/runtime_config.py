"""Runtime configuration metadata and JSON persistence helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_DIR / "backend" / "storage" / "runtime_config.json"


class RuntimeConfigError(ValueError):
    """Raised when a runtime config update is invalid."""


def _option(value: str, label: str) -> Dict[str, str]:
    return {"value": value, "label": label}


CONFIG_GROUPS: List[Dict[str, str]] = [
    {
        "id": "stream",
        "label": "Stream & Runtime",
        "description": "Sumber video, refresh config, dan cadence frame worker.",
    },
    {
        "id": "yolo",
        "label": "YOLO Detection",
        "description": "Backend model, confidence, IoU, input size, dan filter duplikat.",
    },
    {
        "id": "tracking",
        "label": "DeepSORT / Tracking",
        "description": "Parameter tracker, entry/exit gate, dan cooldown event.",
    },
    {
        "id": "reid",
        "label": "ReID Identity",
        "description": "Ambang kemiripan visitor dan mode identitas harian.",
    },
    {
        "id": "face",
        "label": "Face & Pegawai",
        "description": "Face recognition untuk filter pegawai dan face identity.",
    },
]


CONFIG_ITEMS: List[Dict[str, Any]] = [
    {
        "key": "EDGE_STREAM_URL",
        "group": "stream",
        "label": "Sumber stream",
        "type": "string",
        "default": "",
        "help": "Index webcam, RTSP/HTTP URL, relay backend, atau path video lokal.",
    },
    {
        "key": "EDGE_CONFIG_REFRESH_SECONDS",
        "group": "stream",
        "label": "Refresh config edge",
        "type": "int",
        "default": "30",
        "min": 1,
        "max": 3600,
        "unit": "detik",
        "help": "Interval edge worker mengambil config kamera dan runtime.",
    },
    {
        "key": "EDGE_PROCESSING_MAX_FPS",
        "group": "stream",
        "label": "FPS proses YOLO",
        "type": "float",
        "default": "12",
        "min": 0,
        "max": 120,
        "unit": "fps",
        "help": "0 berarti tanpa limit eksplisit.",
    },
    {
        "key": "EDGE_STREAM_MAX_FPS",
        "group": "stream",
        "label": "FPS stream browser",
        "type": "float",
        "default": "15",
        "min": 0,
        "max": 120,
        "unit": "fps",
        "help": "Target publish frame untuk WebRTC/MJPEG.",
    },
    {
        "key": "EDGE_STREAM_JPEG_QUALITY",
        "group": "stream",
        "label": "Kualitas MJPEG",
        "type": "int",
        "default": "65",
        "min": 10,
        "max": 95,
        "unit": "%",
    },
    {
        "key": "EDGE_FILE_FRAME_STEP",
        "group": "stream",
        "label": "Frame step file lokal",
        "type": "int",
        "default": "3",
        "min": 1,
        "max": 120,
        "help": "Lewati frame saat sumber berupa file video lokal.",
    },
    {
        "key": "EDGE_LOCAL_FILE_REPLAY_POST_EVENTS",
        "group": "stream",
        "label": "Post event saat file replay",
        "type": "bool",
        "default": "false",
    },
    {
        "key": "YOLO_BACKEND",
        "aliases": ["BACKEND"],
        "group": "yolo",
        "label": "Backend YOLO",
        "type": "select",
        "default": "yolov5",
        "options": [_option("yolov5", "YOLOv5 torch.hub"), _option("ultralytics", "Ultralytics YOLOv8+"),],
        "restart_required": True,
        "help": "Mengganti backend perlu load ulang model.",
    },
    {
        "key": "YOLOV5_WEIGHTS",
        "group": "yolo",
        "label": "Path weights",
        "type": "string",
        "default": "./edge/yolov5s.pt",
        "restart_required": True,
    },
    {
        "key": "YOLO_REPO",
        "aliases": ["YOLOV5_REPO"],
        "group": "yolo",
        "label": "Repo YOLOv5 lokal",
        "type": "string",
        "default": "",
        "restart_required": True,
        "help": "Kosongkan untuk torch.hub default.",
    },
    {
        "key": "YOLO_DEVICE",
        "aliases": ["YOLOV5_DEVICE"],
        "group": "yolo",
        "label": "Device inferensi",
        "type": "select",
        "default": "auto",
        "options": [_option("auto", "Auto"), _option("cpu", "CPU"), _option("cuda", "CUDA"), _option("cuda:0", "CUDA 0"), _option("xpu", "Intel XPU")],
        "restart_required": True,
    },
    {
        "key": "YOLO_CONF",
        "aliases": ["YOLOV5_CONF"],
        "group": "yolo",
        "label": "Confidence threshold",
        "type": "float",
        "default": "0.45",
        "min": 0,
        "max": 1,
    },
    {
        "key": "YOLO_IOU",
        "aliases": ["YOLOV5_IOU"],
        "group": "yolo",
        "label": "IoU threshold",
        "type": "float",
        "default": "0.45",
        "min": 0,
        "max": 1,
    },
    {
        "key": "YOLO_IMG_SIZE",
        "aliases": ["YOLOV5_IMG_SIZE"],
        "group": "yolo",
        "label": "Image size",
        "type": "int",
        "default": "640",
        "min": 32,
        "max": 2048,
    },
    {
        "key": "SUPPRESS_NESTED_DUPLICATES",
        "group": "yolo",
        "label": "Filter deteksi duplikat",
        "type": "bool",
        "default": "true",
    },
    {
        "key": "DUPLICATE_CONTAINMENT_THRESHOLD",
        "group": "yolo",
        "label": "Containment duplikat",
        "type": "float",
        "default": "0.9",
        "min": 0,
        "max": 1,
    },
    {
        "key": "DUPLICATE_IOU_THRESHOLD",
        "group": "yolo",
        "label": "IoU duplikat",
        "type": "float",
        "default": "0.85",
        "min": 0,
        "max": 1,
    },
    {
        "key": "FORCE_CENTROID",
        "group": "tracking",
        "label": "Paksa centroid tracker",
        "type": "bool",
        "default": "false",
        "help": "Matikan DeepSORT dan gunakan fallback centroid.",
    },
    {
        "key": "TRACK_MAX_AGE",
        "aliases": ["TRACK_MAX_DISAPPEARED"],
        "group": "tracking",
        "label": "Max age track",
        "type": "int",
        "default": "30",
        "min": 0,
        "max": 300,
        "unit": "frame",
    },
    {
        "key": "TRACK_N_INIT",
        "aliases": ["TRACK_CONFIRM_FRAMES"],
        "group": "tracking",
        "label": "Frame konfirmasi track",
        "type": "int",
        "default": "3",
        "min": 1,
        "max": 60,
    },
    {
        "key": "TRACK_MAX_DISTANCE",
        "group": "tracking",
        "label": "Jarak max centroid",
        "type": "float",
        "default": "80",
        "min": 0,
        "max": 1000,
    },
    {
        "key": "TRACK_MAX_COSINE_DISTANCE",
        "group": "tracking",
        "label": "Cosine max DeepSORT",
        "type": "float",
        "default": "0.3",
        "min": 0,
        "max": 1,
    },
    {
        "key": "TRACK_ROI_POINT",
        "group": "tracking",
        "label": "Titik hitung ROI",
        "type": "select",
        "default": "feet",
        "options": [_option("feet", "Kaki / bawah bbox"), _option("center", "Center bbox"), _option("head", "Kepala / atas bbox")],
    },
    {
        "key": "TRACK_ENTRY_CONFIRM_FRAMES",
        "group": "tracking",
        "label": "Konfirmasi masuk",
        "type": "int",
        "default": "4",
        "min": 1,
        "max": 120,
    },
    {
        "key": "TRACK_EXIT_CONFIRM_FRAMES",
        "group": "tracking",
        "label": "Konfirmasi keluar",
        "type": "int",
        "default": "3",
        "min": 1,
        "max": 120,
    },
    {
        "key": "TRACK_EXIT_BOTTOM_CONFIRM_FRAMES",
        "group": "tracking",
        "label": "Konfirmasi tepi bawah",
        "type": "int",
        "default": "1",
        "min": 1,
        "max": 120,
    },
    {
        "key": "TRACK_EXIT_EDGE_MARGIN",
        "group": "tracking",
        "label": "Margin tepi frame",
        "type": "float",
        "default": "48",
        "min": 0,
        "max": 1000,
    },
    {
        "key": "TRACK_EXIT_BOTTOM_MARGIN",
        "group": "tracking",
        "label": "Margin bawah frame",
        "type": "float",
        "default": "110",
        "min": 0,
        "max": 1000,
    },
    {
        "key": "TRACK_EXIT_MIN_DELTA_Y",
        "group": "tracking",
        "label": "Delta Y keluar minimum",
        "type": "float",
        "default": "3",
        "min": 0,
        "max": 200,
    },
    {
        "key": "TRACK_EXIT_ALLOW_WITHOUT_ENTRY",
        "group": "tracking",
        "label": "Izinkan keluar tanpa masuk",
        "type": "bool",
        "default": "true",
    },
    {
        "key": "TRACK_EXIT_WITHOUT_ENTRY_MIN_FRAMES",
        "group": "tracking",
        "label": "Min frame keluar tanpa masuk",
        "type": "int",
        "default": "12",
        "min": 1,
        "max": 300,
    },
    {
        "key": "TRACK_EVENT_COOLDOWN_SECONDS",
        "group": "tracking",
        "label": "Cooldown event",
        "type": "float",
        "default": "12",
        "min": 0,
        "max": 3600,
        "unit": "detik",
    },
    {
        "key": "TRACK_SAME_TRACK_OUT_COOLDOWN_SECONDS",
        "group": "tracking",
        "label": "Cooldown OUT track sama",
        "type": "float",
        "default": "8",
        "min": 0,
        "max": 3600,
        "unit": "detik",
    },
    {
        "key": "TRACK_REENTRY_COOLDOWN_SECONDS",
        "group": "tracking",
        "label": "Cooldown re-entry",
        "type": "float",
        "default": "90",
        "min": 0,
        "max": 7200,
        "unit": "detik",
    },
    {
        "key": "IDENTITY_MODE",
        "group": "reid",
        "label": "Mode identitas visitor",
        "type": "select",
        "default": "reid",
        "options": [_option("reid", "DeepSORT ReID"), _option("face", "Face embedding"), _option("track", "Track ID fallback")],
    },
    {
        "key": "REID_MATCH_THRESHOLD",
        "group": "reid",
        "label": "ReID match threshold",
        "type": "float",
        "default": "0.77",
        "min": 0,
        "max": 1,
    },
    {
        "key": "REID_MIN_TRACK_FRAMES",
        "group": "reid",
        "label": "Sample minimum ReID",
        "type": "int",
        "default": "3",
        "min": 1,
        "max": 120,
    },
    {
        "key": "REID_STRONG_MATCH_THRESHOLD",
        "group": "reid",
        "label": "Strong match ReID",
        "type": "float",
        "default": "0.86",
        "min": 0,
        "max": 1,
    },
    {
        "key": "REID_AMBIGUITY_MARGIN",
        "group": "reid",
        "label": "Margin ambiguitas ReID",
        "type": "float",
        "default": "0.04",
        "min": 0,
        "max": 1,
    },
    {
        "key": "REID_PROTOTYPE_ALPHA",
        "group": "reid",
        "label": "Prototype alpha ReID",
        "type": "float",
        "default": "0.18",
        "min": 0.01,
        "max": 1,
    },
    {
        "key": "WITH_FACE_RECOGNITION",
        "aliases": ["FACE_RECOGNITION_ENABLED"],
        "group": "face",
        "label": "Face recognition pegawai",
        "type": "bool",
        "default": "false",
        "restart_required": True,
        "help": "Mengaktifkan InsightFace perlu inisialisasi ulang worker.",
    },
    {
        "key": "EMPLOYEE_MATCH_THRESHOLD",
        "group": "face",
        "label": "Threshold match pegawai",
        "type": "float",
        "default": "0.45",
        "min": 0,
        "max": 1,
    },
    {
        "key": "EMPLOYEE_REGISTRY_REFRESH_SECONDS",
        "group": "face",
        "label": "Refresh registry pegawai",
        "type": "int",
        "default": "60",
        "min": 1,
        "max": 3600,
        "unit": "detik",
    },
    {
        "key": "FACE_RECHECK_SECONDS",
        "group": "face",
        "label": "Interval recheck wajah",
        "type": "float",
        "default": "0.8",
        "min": 0,
        "max": 60,
        "unit": "detik",
    },
    {
        "key": "FACE_UNKNOWN_TIMEOUT",
        "group": "face",
        "label": "Timeout wajah unknown",
        "type": "float",
        "default": "2.5",
        "min": 0,
        "max": 120,
        "unit": "detik",
    },
    {
        "key": "FACE_DETECTION_FRAME_INTERVAL",
        "group": "face",
        "label": "Interval deteksi wajah",
        "type": "int",
        "default": "3",
        "min": 1,
        "max": 120,
        "unit": "frame",
    },
    {
        "key": "FACE_REGISTRY_SOURCE",
        "group": "face",
        "label": "Sumber registry wajah",
        "type": "select",
        "default": "backend",
        "options": [_option("backend", "Backend database"), _option("folder", "Folder lokal")],
    },
    {
        "key": "EDGE_EMPLOYEE_FACES_DIR",
        "aliases": ["EMPLOYEE_FACES_DIR"],
        "group": "face",
        "label": "Folder wajah pegawai",
        "type": "string",
        "default": "./backend/storage/employee_faces",
    },
    {
        "key": "FACE_ID_MATCH_THRESHOLD",
        "group": "face",
        "label": "Face ID match threshold",
        "type": "float",
        "default": "0.55",
        "min": 0,
        "max": 1,
    },
    {
        "key": "FACE_ID_MIN_TRACK_FRAMES",
        "group": "face",
        "label": "Sample minimum Face ID",
        "type": "int",
        "default": "3",
        "min": 1,
        "max": 120,
    },
    {
        "key": "FACE_ID_STRONG_MATCH_THRESHOLD",
        "group": "face",
        "label": "Strong match Face ID",
        "type": "float",
        "default": "0.65",
        "min": 0,
        "max": 1,
    },
    {
        "key": "FACE_ID_AMBIGUITY_MARGIN",
        "group": "face",
        "label": "Margin ambiguitas Face ID",
        "type": "float",
        "default": "0.03",
        "min": 0,
        "max": 1,
    },
    {
        "key": "FACE_ID_PROTOTYPE_ALPHA",
        "group": "face",
        "label": "Prototype alpha Face ID",
        "type": "float",
        "default": "0.18",
        "min": 0.01,
        "max": 1,
    },
]

CONFIG_HINTS: Dict[str, str] = {
    "EDGE_STREAM_URL": "Sumber frame yang dibaca edge worker. Jika kosong, worker memakai stream kamera dari database saat EDGE_STREAM_URL tidak diset. Jika path/URL salah, deteksi berhenti karena tidak ada frame. Sumber resolusi tinggi atau jaringan lambat menaikkan latency dan beban decode.",
    "EDGE_CONFIG_REFRESH_SECONDS": "Interval worker mengambil konfigurasi kamera, ROI, registry, dan runtime config. Nilai terlalu tinggi membuat perubahan panel lambat aktif. Nilai terlalu rendah menambah request ke backend dan bisa membuat log/API lebih ramai.",
    "EDGE_PROCESSING_MAX_FPS": "Batas FPS untuk inferensi YOLO dan tracking. Terlalu tinggi membuat CPU/GPU berat, suhu naik, dan frame bisa antre. Terlalu rendah membuat bbox lambat mengikuti objek dan gerakan cepat lebih mudah terlewat.",
    "EDGE_STREAM_MAX_FPS": "Batas FPS preview WebRTC/MJPEG ke browser. Terlalu tinggi menaikkan bandwidth dan beban browser. Terlalu rendah hanya membuat preview patah-patah, tetapi tidak selalu menurunkan akurasi deteksi.",
    "EDGE_STREAM_JPEG_QUALITY": "Kualitas kompresi MJPEG preview. Nilai tinggi membuat gambar lebih jelas untuk cek ROI, tetapi bandwidth dan CPU encoding naik. Nilai rendah membuat artefak kompresi dan preview sulit dibaca.",
    "EDGE_FILE_FRAME_STEP": "Jumlah frame file lokal yang dilompati saat replay video. Nilai tinggi mempercepat pemrosesan file, tetapi crossing singkat bisa hilang. Nilai rendah lebih teliti, tetapi proses lebih lambat dan lebih berat.",
    "EDGE_LOCAL_FILE_REPLAY_POST_EVENTS": "Mengatur apakah video lokal yang diputar ulang tetap mengirim event setelah selesai satu putaran. Aktif cocok untuk test berulang, tetapi bisa menduplikasi data. Nonaktif menjaga replay berikutnya hanya sebagai preview.",
    "YOLO_BACKEND": "Loader model deteksi. Ultralytics cocok untuk YOLOv8/v9/v10/v11, YOLOv5 memakai torch.hub. Pilihan yang tidak cocok dengan weights membuat model gagal load. Perubahan perlu restart karena model diinisialisasi saat worker start.",
    "YOLOV5_WEIGHTS": "Path file model .pt yang dipakai mendeteksi manusia. Model lebih besar biasanya lebih akurat tetapi lebih lambat. Model lebih kecil lebih cepat tetapi lebih mudah miss. Path salah membuat worker gagal memuat model.",
    "YOLO_REPO": "Path repo YOLOv5 lokal untuk torch.hub. Isi hanya jika memakai backend YOLOv5 dan repo lokal tersedia. Path salah membuat load model gagal. Kosong berarti memakai sumber default torch.hub.",
    "YOLO_DEVICE": "Perangkat inferensi model. GPU/CUDA/XPU bisa lebih cepat jika tersedia, tetapi gagal jika driver/device tidak cocok. CPU lebih stabil di banyak mesin, tetapi biasanya lebih lambat. Auto memilih perangkat terbaik yang terdeteksi.",
    "YOLO_CONF": "Ambang confidence deteksi orang. Terlalu tinggi mengurangi false positive, tetapi orang jauh/gelap/tertutup bisa tidak terdeteksi. Terlalu rendah menangkap lebih banyak kandidat, tetapi noise, duplicate box, dan false track meningkat.",
    "YOLO_IOU": "Ambang IoU NMS YOLO untuk menggabungkan bbox yang overlap. Terlalu tinggi dapat menyisakan bbox ganda pada orang yang sama. Terlalu rendah dapat menghapus salah satu orang saat pengunjung berdempetan.",
    "YOLO_IMG_SIZE": "Ukuran input model saat inferensi. Nilai tinggi membantu orang kecil/jauh dan bbox lebih stabil, tetapi FPS turun dan memori naik. Nilai rendah lebih cepat, tetapi deteksi kecil atau detail tubuh lebih mudah hilang.",
    "SUPPRESS_NESTED_DUPLICATES": "Filter tambahan untuk membuang bbox orang yang saling bertumpuk/nested sebelum tracking. Aktif mengurangi double track pada satu orang. Jika scene sangat padat, filter agresif bisa menghapus orang asli yang overlap.",
    "DUPLICATE_CONTAINMENT_THRESHOLD": "Seberapa besar bbox harus saling menutupi agar dianggap duplikat nested. Terlalu tinggi membuat duplikat tetap lolos. Terlalu rendah membuat orang berbeda yang berdekatan bisa dianggap satu.",
    "DUPLICATE_IOU_THRESHOLD": "IoU minimum agar dua bbox dianggap duplikat. Terlalu tinggi hanya membuang bbox hampir identik. Terlalu rendah membuat bbox orang yang berdekatan lebih mudah terhapus.",
    "FORCE_CENTROID": "Memaksa tracker memakai centroid sederhana, bukan DeepSORT. Aktif lebih ringan dan berguna saat DeepSORT bermasalah, tetapi ID mudah berubah saat occlusion. Nonaktif memakai DeepSORT+ReID yang lebih stabil tetapi lebih berat.",
    "TRACK_MAX_AGE": "Jumlah frame track boleh hilang sebelum dihapus. Terlalu tinggi menjaga track saat occlusion, tetapi track usang bisa hidup terlalu lama dan salah sambung. Terlalu rendah membuat ID sering pecah saat deteksi putus sebentar.",
    "TRACK_N_INIT": "Jumlah frame deteksi sebelum track dianggap valid. Terlalu tinggi mengurangi track palsu, tetapi counting terlambat. Terlalu rendah lebih responsif, tetapi noise singkat bisa menjadi track valid.",
    "TRACK_MAX_DISTANCE": "Jarak maksimum centroid untuk menyambung deteksi ke track lama. Terlalu tinggi bisa menukar identitas antar orang yang berdekatan. Terlalu rendah membuat track putus saat orang bergerak cepat atau FPS rendah.",
    "TRACK_MAX_COSINE_DISTANCE": "Batas jarak appearance DeepSORT. Terlalu tinggi membuat matching longgar dan identitas bisa tertukar. Terlalu rendah terlalu ketat sehingga orang yang sama mudah dibuat track baru.",
    "TRACK_ROI_POINT": "Titik bbox yang dipakai untuk menguji masuk ROI. Feet biasanya paling stabil untuk gerbang/lantai. Center atau head dapat menghitung lebih cepat/lambat, dan pilihan yang tidak sesuai perspektif bisa membuat crossing tidak tercatat.",
    "TRACK_ENTRY_CONFIRM_FRAMES": "Jumlah frame berturut-turut di ROI sebelum event IN dikunci. Terlalu tinggi mengurangi IN palsu, tetapi pengunjung cepat bisa terlewat. Terlalu rendah membuat jitter di batas ROI mudah dihitung masuk.",
    "TRACK_EXIT_CONFIRM_FRAMES": "Jumlah frame konfirmasi sebelum OUT dikunci. Terlalu tinggi membuat OUT lebih aman tetapi terlambat atau miss. Terlalu rendah membuat track yang sebentar hilang dekat gerbang mudah dihitung keluar.",
    "TRACK_EXIT_BOTTOM_CONFIRM_FRAMES": "Jumlah frame track harus menyentuh/keluar lewat tepi bawah. Terlalu tinggi membuat exit cepat tidak tercatat. Terlalu rendah membuat gerakan singkat dekat bawah frame lebih mudah menjadi OUT.",
    "TRACK_EXIT_EDGE_MARGIN": "Lebar area tepi frame untuk mendeteksi track sedang keluar. Terlalu besar memperluas zona exit dan menaikkan risiko OUT palsu. Terlalu kecil hanya menghitung saat benar-benar dekat tepi sehingga exit bisa miss.",
    "TRACK_EXIT_BOTTOM_MARGIN": "Tinggi zona bawah frame untuk exit. Terlalu besar membuat orang yang masih di area bawah dianggap mendekati keluar. Terlalu kecil membuat exit bawah terlambat atau tidak terdeteksi.",
    "TRACK_EXIT_MIN_DELTA_Y": "Gerak vertikal minimum untuk dianggap bergerak ke bawah/keluar. Terlalu tinggi melewatkan orang yang berjalan pelan. Terlalu rendah membuat jitter bbox dianggap gerakan keluar.",
    "TRACK_EXIT_ALLOW_WITHOUT_ENTRY": "Mengizinkan OUT walau track belum pernah tercatat IN. Aktif membantu saat kamera mulai di tengah alur atau entry miss, tetapi bisa membuat OUT palsu. Nonaktif lebih ketat, tetapi exit bisa hilang jika entry gagal.",
    "TRACK_EXIT_WITHOUT_ENTRY_MIN_FRAMES": "Minimal frame track terlihat sebelum boleh OUT tanpa entry. Terlalu tinggi melewatkan orang yang cepat keluar. Terlalu rendah membuat noise/track singkat bisa dihitung keluar.",
    "TRACK_EVENT_COOLDOWN_SECONDS": "Jeda minimum event arah yang sama untuk visitor yang sama. Terlalu tinggi menahan event valid saat orang bolak-balik cepat. Terlalu rendah meningkatkan risiko double count dari jitter.",
    "TRACK_SAME_TRACK_OUT_COOLDOWN_SECONDS": "Jeda minimum OUT ulang dari track yang sama. Terlalu tinggi bisa menahan OUT valid pada skenario re-entry cepat. Terlalu rendah membuat OUT berulang dari track yang belum bersih lebih mungkin.",
    "TRACK_REENTRY_COOLDOWN_SECONDS": "Jeda sebelum visitor yang sama boleh dianggap masuk lagi setelah OUT. Terlalu tinggi membuat kunjungan balik cepat tidak tercatat. Terlalu rendah bisa membuat loop IN/OUT karena jitter di area gerbang.",
    "IDENTITY_MODE": "Sumber identitas visitor unik. ReID memakai embedding DeepSORT, face memakai embedding wajah, track memakai ID tracker fallback. Mode yang tidak sesuai data kamera bisa membuat unique visitor pecah atau tergabung salah.",
    "REID_MATCH_THRESHOLD": "Kemiripan minimum agar embedding dianggap visitor yang sama. Terlalu tinggi membuat orang yang sama dihitung sebagai visitor baru. Terlalu rendah menggabungkan orang berbeda menjadi satu visitor.",
    "REID_MIN_TRACK_FRAMES": "Jumlah sample track sebelum identitas ReID dikunci. Terlalu tinggi membuat identitas stabil tetapi terlambat. Terlalu rendah memakai embedding awal yang noisy dan rawan salah match.",
    "REID_STRONG_MATCH_THRESHOLD": "Ambang match kuat saat ada kandidat mirip. Terlalu tinggi membuat match valid ditolak dan visitor terpecah. Terlalu rendah membuat kandidat yang belum cukup kuat lebih mudah digabung.",
    "REID_AMBIGUITY_MARGIN": "Selisih minimum antara kandidat terbaik dan kedua. Terlalu tinggi menolak banyak match di kerumunan. Terlalu rendah menerima match ambigu dan bisa menggabungkan orang yang mirip.",
    "REID_PROTOTYPE_ALPHA": "Kecepatan prototype embedding visitor diperbarui. Terlalu tinggi cepat beradaptasi tetapi mudah drift oleh pose/noise. Terlalu rendah stabil tetapi lambat mengikuti perubahan penampilan.",
    "WITH_FACE_RECOGNITION": "Mengaktifkan InsightFace untuk filter pegawai. Aktif dapat mengecualikan pegawai dari hitungan customer, tetapi menambah beban CPU/GPU dan perlu model face siap. Nonaktif semua orang diperlakukan customer.",
    "EMPLOYEE_MATCH_THRESHOLD": "Kemiripan minimum wajah agar track dianggap pegawai. Terlalu tinggi membuat pegawai tidak dikenali dan ikut terhitung customer. Terlalu rendah membuat pengunjung mirip pegawai bisa terabaikan.",
    "EMPLOYEE_REGISTRY_REFRESH_SECONDS": "Interval reload data wajah pegawai. Terlalu tinggi membuat perubahan pegawai lambat terbaca. Terlalu rendah menambah query backend atau scan folder dan bisa membebani sistem.",
    "FACE_RECHECK_SECONDS": "Jeda pemeriksaan ulang wajah pada track yang belum stabil. Terlalu tinggi membuat klasifikasi pegawai lambat. Terlalu rendah menjalankan face matching terlalu sering dan menurunkan FPS.",
    "FACE_UNKNOWN_TIMEOUT": "Waktu tunggu sebelum track tanpa wajah dianggap customer. Terlalu tinggi menunda kepastian tipe orang. Terlalu rendah membuat pegawai cepat jatuh ke customer sebelum wajah terbaca.",
    "FACE_DETECTION_FRAME_INTERVAL": "Jarak frame antar deteksi wajah batch. Terlalu tinggi menghemat proses tetapi wajah singkat bisa terlewat. Terlalu rendah lebih responsif tetapi face detection menjadi berat.",
    "FACE_REGISTRY_SOURCE": "Sumber embedding pegawai: backend database atau folder lokal. Sumber salah/kosong membuat registry kosong dan pegawai tidak dikenali. Folder cocok offline, backend cocok saat data pegawai dikelola aplikasi.",
    "EDGE_EMPLOYEE_FACES_DIR": "Folder gambar wajah pegawai saat registry source folder. Path salah atau foto tanpa wajah membuat registry kosong. Banyak file memperlama refresh, tetapi registry lebih lengkap.",
    "FACE_ID_MATCH_THRESHOLD": "Threshold kemiripan saat identity mode memakai face. Terlalu tinggi membuat orang yang sama mudah dihitung baru. Terlalu rendah menggabungkan wajah berbeda.",
    "FACE_ID_MIN_TRACK_FRAMES": "Jumlah sample wajah sebelum Face ID dikunci. Terlalu tinggi lebih stabil tetapi lambat. Terlalu rendah rawan memakai embedding wajah blur/parsial.",
    "FACE_ID_STRONG_MATCH_THRESHOLD": "Ambang match kuat untuk Face ID. Terlalu tinggi memecah visitor yang sama. Terlalu rendah meningkatkan risiko salah gabung wajah mirip.",
    "FACE_ID_AMBIGUITY_MARGIN": "Selisih kandidat Face ID terbaik dan kedua. Terlalu tinggi banyak match ditolak. Terlalu rendah menerima match ambigu di orang yang mirip.",
    "FACE_ID_PROTOTYPE_ALPHA": "Kecepatan prototype Face ID diperbarui. Terlalu tinggi mudah drift karena pose/blur. Terlalu rendah stabil tetapi lambat mengikuti perubahan kualitas wajah.",
}


CONFIG_BY_KEY: Dict[str, Dict[str, Any]] = {}
for item in CONFIG_ITEMS:
    CONFIG_BY_KEY[item["key"]] = item
    for alias in item.get("aliases", []):
        CONFIG_BY_KEY[alias] = item


def _item_keys(item: Dict[str, Any]) -> List[str]:
    return [item["key"], *item.get("aliases", [])]


def _item_value(item: Dict[str, Any], stored_values: Dict[str, str]) -> str:
    for key in _item_keys(item):
        if key in stored_values:
            return stored_values[key]
    return str(item.get("default", ""))


def _format_number(value: float) -> str:
    return f"{value:g}"


def _coerce_value(item: Dict[str, Any], raw_value: Any) -> str:
    value_type = item.get("type", "string")
    raw = "" if raw_value is None else str(raw_value).strip()
    label = item.get("label", item["key"])

    if value_type == "bool":
        normalized = raw.lower()
        if normalized in {"1", "true", "yes", "on"}:
            return "true"
        if normalized in {"0", "false", "no", "off"}:
            return "false"
        raise RuntimeConfigError(f"{label} harus bernilai true/false")

    if value_type == "select":
        allowed = {option["value"] for option in item.get("options", [])}
        if raw not in allowed:
            allowed_label = ", ".join(sorted(allowed))
            raise RuntimeConfigError(f"{label} harus salah satu dari: {allowed_label}")
        return raw

    if value_type == "int":
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            raise RuntimeConfigError(f"{label} harus berupa angka bulat") from None
        minimum = item.get("min")
        maximum = item.get("max")
        if minimum is not None and parsed < int(minimum):
            raise RuntimeConfigError(f"{label} minimal {minimum}")
        if maximum is not None and parsed > int(maximum):
            raise RuntimeConfigError(f"{label} maksimal {maximum}")
        return str(parsed)

    if value_type == "float":
        try:
            parsed = float(raw)
        except (TypeError, ValueError):
            raise RuntimeConfigError(f"{label} harus berupa angka") from None
        minimum = item.get("min")
        maximum = item.get("max")
        if minimum is not None and parsed < float(minimum):
            raise RuntimeConfigError(f"{label} minimal {minimum}")
        if maximum is not None and parsed > float(maximum):
            raise RuntimeConfigError(f"{label} maksimal {maximum}")
        return _format_number(parsed)

    if value_type == "json":
        try:
            json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeConfigError(f"{label} harus JSON valid: {exc.msg}") from None
        return raw

    return raw


def _default_values() -> Dict[str, str]:
    return {item["key"]: str(item.get("default", "")) for item in CONFIG_ITEMS}


def _read_config_values() -> Dict[str, str]:
    if not CONFIG_PATH.exists():
        return {}

    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeConfigError(f"File runtime config JSON tidak valid: {exc.msg}") from None

    if isinstance(payload, dict) and isinstance(payload.get("values"), dict):
        raw_values = payload["values"]
    elif isinstance(payload, dict):
        raw_values = payload
    else:
        raise RuntimeConfigError("File runtime config harus berupa object JSON")

    values: Dict[str, str] = {}
    for raw_key, raw_value in raw_values.items():
        item = CONFIG_BY_KEY.get(str(raw_key))
        if item is None:
            continue
        values[item["key"]] = _coerce_value(item, raw_value)
    return values


def _write_config_values(values: Dict[str, str]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ordered_values = {item["key"]: values[item["key"]] for item in CONFIG_ITEMS if item["key"] in values}
    payload = {"values": ordered_values}
    temp_path = CONFIG_PATH.with_suffix(f"{CONFIG_PATH.suffix}.tmp")
    temp_path.write_text(f"{json.dumps(payload, indent=2, sort_keys=False)}\n", encoding="utf-8")
    temp_path.replace(CONFIG_PATH)


def load_runtime_config() -> Dict[str, Any]:
    stored_values = _read_config_values()
    config_mtime = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else None
    items: List[Dict[str, Any]] = []
    values: Dict[str, str] = {}

    for item in CONFIG_ITEMS:
        current_value = _item_value(item, stored_values)
        values[item["key"]] = current_value
        items.append(
            {
                **item,
                "value": current_value,
                "aliases": item.get("aliases", []),
                "hint": item.get("hint") or CONFIG_HINTS.get(item["key"]) or item.get("help") or "",
                "restart_required": bool(item.get("restart_required", False)),
            }
        )

    return {
        "storage_driver": "json",
        "config_path": str(CONFIG_PATH),
        "config_mtime": config_mtime,
        "groups": CONFIG_GROUPS,
        "items": items,
        "values": values,
    }


def save_runtime_config(values: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(values, dict):
        raise RuntimeConfigError("Payload values harus berupa object")

    current_values = _default_values()
    current_values.update(_read_config_values())
    next_values = dict(current_values)
    changed_items: List[Dict[str, Any]] = []

    for incoming_key, raw_value in values.items():
        item = CONFIG_BY_KEY.get(str(incoming_key))
        if item is None:
            raise RuntimeConfigError(f"Config {incoming_key} tidak diizinkan")

        coerced = _coerce_value(item, raw_value)
        current_value = _item_value(item, current_values)
        next_values[item["key"]] = coerced

        if coerced != current_value:
            changed_items.append(
                {
                    "key": item["key"],
                    "label": item.get("label", item["key"]),
                    "value": coerced,
                    "restart_required": bool(item.get("restart_required", False)),
                }
            )

    if values:
        _write_config_values(next_values)

    config = load_runtime_config()
    config.update(
        {
            "status": "success",
            "changed": changed_items,
            "restart_required": any(item["restart_required"] for item in changed_items),
        }
    )
    return config
