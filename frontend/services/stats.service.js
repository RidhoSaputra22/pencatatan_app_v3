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
export function fetchSummary(day, options = {}) {
  const params = new URLSearchParams();
  if (day) params.set("day", day);
  if (options.fromDateTime) {
    params.set("from_datetime", options.fromDateTime);
  }
  if (options.toDateTime) {
    params.set("to_datetime", options.toDateTime);
  }
  return get(`/api/stats/summary?${params.toString()}`);
}

/**
 * GET /api/stats/daily with optional date range.
 * @param {string} day - single day (YYYY-MM-DD)
 * @param {string} fromDate - start of range
 * @param {string} toDate - end of range
 */
export function fetchDaily(day, fromDate, toDate, options = {}) {
  const params = new URLSearchParams();
  if (day) params.set("day", day);
  if (fromDate && toDate) {
    params.set("from_date", fromDate);
    params.set("to_date", toDate);
  }
  if (options.fromDateTime) {
    params.set("from_datetime", options.fromDateTime);
  }
  if (options.toDateTime) {
    params.set("to_datetime", options.toDateTime);
  }
  return get(`/api/stats/daily?${params.toString()}`);
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
export function fetchStatsPerSecond(day, cameraId, options = {}) {
  const params = new URLSearchParams({ day });
  if (cameraId) params.set("camera_id", String(cameraId));
  if (options.fromDateTime) {
    params.set("from_datetime", options.fromDateTime);
  }
  if (options.toDateTime) {
    params.set("to_datetime", options.toDateTime);
  }
  return get(`/api/stats/per_second?${params.toString()}`);
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
 * GET /api/visitors/current — visitors currently inside the room.
 */
export function fetchCurrentVisitors(options = {}) {
  const params = new URLSearchParams();

  if (options.cameraId) {
    params.set("camera_id", String(options.cameraId));
  }
  if (options.limit) {
    params.set("limit", String(options.limit));
  }

  const query = params.toString();
  return get(query ? `/api/visitors/current?${query}` : "/api/visitors/current");
}

/**
 * GET /api/visitors/current-history — snapshot histori pengunjung di dalam ruangan per menit.
 */
export function fetchCurrentVisitorHistory(fromDate, toDate, options = {}) {
  const params = new URLSearchParams();

  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  if (options.fromDateTime) {
    params.set("from_datetime", options.fromDateTime);
  }
  if (options.toDateTime) {
    params.set("to_datetime", options.toDateTime);
  }
  if (options.cameraId) {
    params.set("camera_id", String(options.cameraId));
  }
  if (options.limit) {
    params.set("limit", String(options.limit));
  }

  const query = params.toString();
  return get(query ? `/api/visitors/current-history?${query}` : "/api/visitors/current-history");
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
