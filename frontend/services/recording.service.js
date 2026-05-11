import { API_BASE } from "@/lib/constants";
import { getToken } from "@/lib/utils";

import { del, get } from "./api";

function parseFilenameFromDisposition(disposition, fallback) {
  const match =
    disposition?.match(/filename\*=UTF-8''([^;]+)/i) ||
    disposition?.match(/filename="?([^"]+)"?/i);
  if (!match?.[1]) return fallback;

  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

async function downloadFromApi(path, fallbackFilename) {
  const token = getToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(`${API_BASE}${path}`, { headers });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorPayload.detail || `Request failed (${response.status})`);
  }

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const disposition = response.headers.get("content-disposition");
  const filename = parseFilenameFromDisposition(disposition, fallbackFilename);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(downloadUrl), 1_000);

  return { ok: true, filename };
}

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

export function downloadRecording(filename) {
  return downloadFromApi(
    `/api/recordings/${encodeURIComponent(filename)}/download`,
    filename,
  );
}

export function downloadRecordingArchive(recordingDate) {
  return downloadFromApi(
    `/api/recordings/archive/${encodeURIComponent(recordingDate)}/download`,
    `arsip_rekaman_${recordingDate}.zip`,
  );
}
