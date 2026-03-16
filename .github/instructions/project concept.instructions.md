---
applyTo: '**'
---

Berikut **konsep proyek** dan **skema database sederhana** yang sesuai dengan proposal + use case pada gambar (fokus: monitoring jumlah pengunjung & pengunjung unik harian dengan YOLOv5 + tracking).

---

## 1) Konsep Proyek (Project Concept)

### Tujuan

Membangun sistem **monitoring jumlah pengunjung perpustakaan** berbasis **CCTV** yang:

* Mendeteksi manusia menggunakan **YOLOv5**
* Melakukan **tracking** agar tidak menghitung orang yang sama berkali-kali dalam satu kejadian
* Menghitung **Pengunjung Unik Harian** (orang yang sama masuk 2–3 kali dalam sehari tetap dihitung **1 kali**)
* Menyajikan **dashboard**, statistik, filter per tanggal/periode, serta **ekspor/cetak laporan**

### Alur Sistem Tingkat Tinggi

1. **Kamera CCTV** mengirim stream ke modul **Edge/AI** (PC lokal/NVR/mini PC).
2. Modul **YOLOv5** mendeteksi manusia → modul **Tracking** (mis. SORT/DeepSORT/ByteTrack) memberi `track_id`.
3. Jika objek melewati **Area Hitung/ROI** (konfigurasi kamera), sistem membuat **event kunjungan**.
4. Untuk “unik harian”:

   * Sistem membuat `visitor_key` (identitas anonim) berdasarkan hasil tracking + (opsional) ReID embedding.
   * Saat ada event baru di tanggal yang sama, jika `visitor_key` sudah pernah tercatat → **tidak menambah unik**, hanya menambah total event bila perlu.
5. Backend menyimpan data, Dashboard menampilkan:

   * Total pengunjung (event)
   * Pengunjung unik harian
   * Statistik per jam/hari/periode
   * Ekspor PDF/Excel (opsional)

### Peran Pengguna

* **Admin**: login, kelola pengguna, konfigurasi kamera & area hitung, kelola data kunjungan.
* **Petugas/Operator**: login, monitoring dashboard, lihat statistik, filter periode, ekspor/cetak laporan.

---

## 2) Skema Database Sederhana (Simple Database Schema)

> Ini versi “cukup untuk skripsi & implementasi MVP”, tidak terlalu rumit tetapi sudah menutup kebutuhan use case.

### Tabel Inti

1. **roles**

* `role_id` (PK)
* `name` (ADMIN, OPERATOR)

2. **users**

* `user_id` (PK)
* `role_id` (FK → roles)
* `full_name`
* `username` (unique)
* `password_hash`
* `is_active`
* `created_at`, `updated_at`

3. **cameras**

* `camera_id` (PK)
* `name`
* `location` (mis. “Pintu Masuk Utama”)
* `stream_url` (rtsp/http)
* `is_active`
* `created_at`

4. **counting_areas** (Konfigurasi ROI/area hitung per kamera)

* `area_id` (PK)
* `camera_id` (FK → cameras)
* `name` (mis. “Gate Masuk”)
* `roi_polygon` (text/json: titik polygon)
* `direction_mode` (optional: IN/OUT/BOTH)
* `is_active`

5. **visitor_daily** (kunci unik per hari — untuk aturan “masuk 3x tetap 1”)

* `visitor_daily_id` (PK)
* `visit_date` (DATE)
* `visitor_key` (string hash/uuid anonim)
* `first_seen_at` (datetime)
* `last_seen_at` (datetime)
* `notes` (optional)
  **Unique index**: (`visit_date`, `visitor_key`)

6. **visit_events** (catatan kejadian kunjungan saat melewati area hitung)

* `event_id` (PK)
* `camera_id` (FK → cameras)
* `area_id` (FK → counting_areas)
* `event_time` (datetime)
* `track_id` (id tracking dari edge)
* `visitor_key` (untuk link ke unik harian)
* `direction` (optional: IN/OUT)
* `confidence_avg` (optional)
* `snapshot_path` (optional: bukti gambar)
* `created_at`

7. **daily_stats** (opsional tapi enak untuk dashboard cepat)

* `stat_date` (PK, DATE)
* `total_events` (jumlah event kunjungan)
* `unique_visitors` (jumlah unik harian)
* `last_updated_at`

> Dengan `visit_events` + `visitor_daily`, kamu sudah bisa:

* Hitung total pengunjung (event) per periode
* Hitung unik harian secara konsisten

---

## 3) Contoh DDL SQL (ringkas)

```sql
CREATE TABLE roles (
  role_id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(30) UNIQUE NOT NULL
);

CREATE TABLE users (
  user_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  role_id INT NOT NULL,
  full_name VARCHAR(120) NOT NULL,
  username VARCHAR(60) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (role_id) REFERENCES roles(role_id)
);

CREATE TABLE cameras (
  camera_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  location VARCHAR(160),
  stream_url TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE counting_areas (
  area_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  camera_id BIGINT NOT NULL,
  name VARCHAR(120) NOT NULL,
  roi_polygon JSON NOT NULL,
  direction_mode VARCHAR(10) DEFAULT 'BOTH',
  is_active BOOLEAN DEFAULT TRUE,
  FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
);

CREATE TABLE visitor_daily (
  visitor_daily_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  visit_date DATE NOT NULL,
  visitor_key VARCHAR(100) NOT NULL,
  first_seen_at DATETIME NOT NULL,
  last_seen_at DATETIME NOT NULL,
  notes VARCHAR(255),
  UNIQUE KEY uq_visitor_day (visit_date, visitor_key)
);

CREATE TABLE visit_events (
  event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  camera_id BIGINT NOT NULL,
  area_id BIGINT NOT NULL,
  event_time DATETIME NOT NULL,
  track_id VARCHAR(80),
  visitor_key VARCHAR(100) NOT NULL,
  direction VARCHAR(10),
  confidence_avg DECIMAL(5,4),
  snapshot_path TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (camera_id) REFERENCES cameras(camera_id),
  FOREIGN KEY (area_id) REFERENCES counting_areas(area_id),
  INDEX idx_event_time (event_time),
  INDEX idx_visitor_key (visitor_key)
);

CREATE TABLE daily_stats (
  stat_date DATE PRIMARY KEY,
  total_events INT NOT NULL DEFAULT 0,
  unique_visitors INT NOT NULL DEFAULT 0,
  last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4) Catatan Penting untuk “Pengunjung Unik Harian”

Agar sesuai requirement “masuk berkali-kali dalam sehari tetap 1”:

* Saat ada event baru:

  * Cek apakah (`visit_date`, `visitor_key`) sudah ada di `visitor_daily`
  * Jika belum ada → insert `visitor_daily` (unik bertambah)
  * Jika sudah ada → update `last_seen_at` saja (unik tidak bertambah)

`visitor_key` bisa dibuat dengan pendekatan MVP:


* **Lebih kuat** (disarankan skripsi): gunakan tracker + ReID embedding (mis. DeepSORT) lalu hash embedding → lebih stabil walau track_id berubah

// janagan gunakan docker biarkan saya run manual
// gunakan database sqlite, tidak perlu postges dan redis
