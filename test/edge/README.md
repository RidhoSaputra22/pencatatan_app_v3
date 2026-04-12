# Test Edge Video Runner

Folder ini dipakai untuk uji lokal pipeline `YOLO + DeepSORT + reID` memakai file video, lalu menghasilkan:

- video hasil tracking ber-overlay
- CSV berisi data track per frame
- file summary JSON

Hasil export otomatis dipisah ke subfolder sesuai model yang dipilih, jadi run `yolo26n`, `yolo26x`, atau `yolov5s` tidak saling menimpa.

Pastikan runner dijalankan dari environment Python yang sudah meng-install dependency di `edge/requirements.txt`.

## File

- `run_video_tracking.py`: runner utama untuk proses video offline
- `test.sh`: wrapper untuk menjalankan runner dengan `edge/.venv`
- `output/`: lokasi default hasil export

## Contoh Pakai

Lewat wrapper yang langsung memakai `edge/.venv`:

```bash
bash test/edge/test.sh \
  --input rstp/cctv-footage-1.mp4 \
  --backend ultralytics \
  --weights edge/yolo26n.pt
```

Atau panggil Python langsung:

```bash
python3 test/edge/run_video_tracking.py \
  --input rstp/cctv-footage-1.mp4 \
  --output-dir test/edge/output \
  --weights edge/yolov5s.pt \
  --backend yolov5
```

Contoh dengan ROI manual:

```bash
python3 test/edge/run_video_tracking.py \
  --input rstp/cctv-swalayan.mp4 \
  --roi-json '[[50,50],[1230,50],[1230,670],[50,670]]'
```

Contoh jika ingin aktifkan face recognition employee:

```bash
python3 test/edge/run_video_tracking.py \
  --input rstp/cctv-footage-1.mp4 \
  --with-face-recognition
```

## Output

Dengan input `rstp/cctv-footage-1.mp4`, output default akan menjadi:

- `test/edge/output/<backend>_<model>/cctv-footage-1_tracking.mp4`
- `test/edge/output/<backend>_<model>/cctv-footage-1_tracks.csv`
- `test/edge/output/<backend>_<model>/cctv-footage-1_summary.json`

Contoh:

- `test/edge/output/ultralytics_yolo26n/cctv-footage-1_tracking.mp4`
- `test/edge/output/ultralytics_yolo26x/cctv-footage-1_tracking.mp4`
- `test/edge/output/yolov5_yolov5s/cctv-footage-1_tracking.mp4`

`summary.json` sekarang juga menyimpan ringkasan agregat seperti jumlah `enter`, `exit`, visitor unik, breakdown per `person_type`, dan peak track selama video diproses.
Field `unique_visitors` utama memakai mode `peak_visible`, sedangkan hitungan kumulatif tetap tersedia sebagai `cumulative_unique_visitors`.

## Kolom CSV

CSV track menyimpan informasi inti per frame:

- `track_id`, `visitor_key`, `visitor_key_short`
- `roi_status`, `event`, `unique_status`
- `person_type`, `employee_*`, `match_score`
- `x1`, `y1`, `x2`, `y2`, `centroid_x`, `centroid_y`
- `confidence`, `embedding_available`

## Catatan

- Secara default script ini mematikan face recognition agar test video lokal tetap ringan dan tidak tergantung model InsightFace.
- Jika `YOLOV5_WEIGHTS` di `.env` mengarah ke file yang tidak ada, runner akan fallback ke `edge/yolov5s.pt` bila file itu tersedia.
- Resolusi default output mengikuti pipeline edge saat ini: `1280x720`. Gunakan `--keep-source-size` kalau ingin mempertahankan ukuran asli video.
