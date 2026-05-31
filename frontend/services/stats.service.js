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
export function fetchEvents(fromDate, toDate, options = {}) {
  const normalizedOptions =
    typeof options === "number" ? { cameraId: options } : options;
  const params = new URLSearchParams({
    from_date: fromDate,
    to_date: toDate,
  });

  if (normalizedOptions.cameraId) {
    params.set("camera_id", String(normalizedOptions.cameraId));
  }
  if (normalizedOptions.fromDateTime) {
    params.set("from_datetime", normalizedOptions.fromDateTime);
  }
  if (normalizedOptions.toDateTime) {
    params.set("to_datetime", normalizedOptions.toDateTime);
  }

  return get(`/api/reports/events?${params.toString()}`);
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
export function fetchVisitorDaily(fromDate, toDate, options = {}) {
  const params = new URLSearchParams();

  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  if (options.fromDateTime) {
    params.set("from_datetime", options.fromDateTime);
  }
  if (options.toDateTime) {
    params.set("to_datetime", options.toDateTime);
  }

  const query = params.toString();
  return get(query ? `/api/visitors/daily?${query}` : "/api/visitors/daily");
}

/**
 * POST /api/admin/reset-db — reset visitor data (admin only).
 */
export function resetDatabase() {
  return post("/api/admin/reset-db", {});
}

/**
 * POST /api/admin/reset-daily?day=YYYY-MM-DD — reset data visitor untuk 1 hari.
 */
export function resetDailyStats(day) {
  return post(`/api/admin/reset-daily?day=${encodeURIComponent(day)}`, {});
}
