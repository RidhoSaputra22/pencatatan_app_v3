import { get, post } from "./api";

/**
 * GET /api/me — current user profile.
 */
export function fetchMe() {
  return get("/api/me");
}

/**
 * GET /api/stats/summary?day=YYYY-MM-DD
 */
export function fetchSummary(day) {
  return get(`/api/stats/summary?day=${day}`);
}

/**
 * GET /api/stats/daily with optional date range.
 * @param {string} day - single day (YYYY-MM-DD)
 * @param {string} fromDate - start of range
 * @param {string} toDate - end of range
 */
export function fetchDaily(day, fromDate, toDate) {
  if (fromDate && toDate) {
    return get(`/api/stats/daily?from_date=${fromDate}&to_date=${toDate}`);
  }
  return get(`/api/stats/daily?day=${day}`);
}

/**
 * GET /api/reports/events — detailed visit events for reporting.
 */
export function fetchEvents(fromDate, toDate, cameraId) {
  let url = `/api/reports/events?from_date=${fromDate}&to_date=${toDate}`;
  if (cameraId) url += `&camera_id=${cameraId}`;
  return get(url);
}

/**
 * GET /api/stats/per_second — statistik event per detik untuk 1 hari
 * @param {string} day - format YYYY-MM-DD
 * @param {number} cameraId - optional
 */
export function fetchStatsPerSecond(day, cameraId) {
  let url = `/api/stats/per_second?day=${day}`;
  if (cameraId) url += `&camera_id=${cameraId}`;
  return get(url);
}

/**
 * GET /api/visitors/daily — unique daily visitors.
 */
export function fetchVisitorDaily(fromDate, toDate) {
  let url = `/api/visitors/daily`;
  const params = [];
  if (fromDate) params.push(`from_date=${fromDate}`);
  if (toDate) params.push(`to_date=${toDate}`);
  if (params.length) url += `?${params.join("&")}`;
  return get(url);
}

/**
 * POST /api/admin/reset-db — reset visitor data (admin only).
 */
export function resetDatabase() {
  return post("/api/admin/reset-db", {});
}
