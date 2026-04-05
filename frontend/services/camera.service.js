import { get, post, put, del, upload } from "./api";

/**
 * GET /api/cameras/discover — detect available cameras on the system.
 */
export function discoverCameras() {
  return get("/api/cameras/discover");
}

/**
 * GET /api/cameras — list all cameras.
 */
export function fetchCameras() {
  return get("/api/cameras");
}

/**
 * GET /api/cameras/:id
 */
export function fetchCamera(id = 1) {
  return get(`/api/cameras/${id}`);
}

/**
 * POST /api/cameras — create new camera.
 */
export function createCamera(data) {
  return post("/api/cameras", data);
}

/**
 * PUT /api/cameras/:id
 */
export function updateCamera(id = 1, data) {
  return put(`/api/cameras/${id}`, data);
}

/**
 * DELETE /api/cameras/:id — delete camera (admin only).
 */
export function deleteCamera(id) {
  return del(`/api/cameras/${id}`);
}

/**
 * GET /api/cameras/:id/areas
 */
export function fetchAreas(cameraId = 1) {
  return get(`/api/cameras/${cameraId}/areas`);
}

/**
 * POST /api/areas — create new counting area.
 */
export function createArea(data) {
  return post("/api/areas", data);
}

/**
 * PUT /api/areas/:id — update existing counting area.
 */
export function updateArea(areaId, data) {
  return put(`/api/areas/${areaId}`, data);
}

/**
 * DELETE /api/areas/:id — delete counting area (admin only).
 */
export function deleteArea(areaId) {
  return del(`/api/areas/${areaId}`);
}

// ==================== Stream Relay ====================

/**
 * GET /stream/relay/health — check UDP stream relay status.
 */
export async function fetchStreamRelayHealth() {
  const { API_BASE } = await import("@/lib/constants");
  const res = await fetch(`${API_BASE}/stream/relay/health`);
  if (!res.ok) throw new Error("Stream relay not available");
  return res.json();
}

// ==================== Footage Upload ====================

/**
 * POST /api/footage/upload — upload video CCTV file.
 */
export function uploadFootage(file, { setAsSource = false, cameraId = 1 } = {}) {
  const formData = new FormData();
  formData.append("video", file);
  formData.append("set_as_source", setAsSource);
  formData.append("camera_id", cameraId);
  return upload("/api/footage/upload", formData);
}

/**
 * GET /api/footage — list uploaded footage files.
 */
export function fetchFootageList() {
  return get("/api/footage");
}

/**
 * DELETE /api/footage/:filename — delete uploaded footage.
 */
export function deleteFootage(filename) {
  return del(`/api/footage/${encodeURIComponent(filename)}`);
}

/**
 * POST /api/footage/:filename/set-source — set footage as camera source.
 */
export function setFootageAsSource(filename, cameraId = 1) {
  return post(`/api/footage/${encodeURIComponent(filename)}/set-source?camera_id=${cameraId}`);
}
