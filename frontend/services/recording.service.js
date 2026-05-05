import { del, get } from "./api";

/**
 * GET /api/recordings — list rekaman CCTV otomatis yang sudah selesai dipotong.
 */
export function fetchRecordingList() {
  return get("/api/recordings");
}

/**
 * DELETE /api/recordings/:filename — hapus rekaman CCTV otomatis.
 */
export function deleteRecording(filename) {
  return del(`/api/recordings/${encodeURIComponent(filename)}`);
}
