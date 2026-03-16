import { get, post, put, del } from "./api";

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
