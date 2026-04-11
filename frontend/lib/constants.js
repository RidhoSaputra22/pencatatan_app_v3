/**
 * Application constants
 */

function parsePositiveInt(value) {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

function joinUrl(base, pathname) {
  if (!base) {
    return pathname;
  }

  try {
    return new URL(pathname, base.endsWith("/") ? base : `${base}/`).toString();
  } catch {
    return `${base.replace(/\/+$/, "")}${pathname}`;
  }
}

// API Configuration
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";
export const EDGE_PUBLIC_BASE_URL = process.env.NEXT_PUBLIC_EDGE_PUBLIC_BASE_URL || "";

// Edge worker streaming endpoints
export const STREAM_URL =
  process.env.NEXT_PUBLIC_STREAM_URL || joinUrl(EDGE_PUBLIC_BASE_URL, "/video_feed");
export const STREAM_RAW_URL =
  process.env.NEXT_PUBLIC_STREAM_RAW_URL || joinUrl(EDGE_PUBLIC_BASE_URL, "/video_feed_raw");
export const WEBRTC_SIGNAL_URL =
  process.env.NEXT_PUBLIC_WEBRTC_SIGNAL_URL || joinUrl(EDGE_PUBLIC_BASE_URL, "/webrtc/offer");
export const STREAM_HEALTH_URL =
  process.env.NEXT_PUBLIC_STREAM_HEALTH_URL || joinUrl(EDGE_PUBLIC_BASE_URL, "/health");
export const STREAM_RELAY_URL =
  process.env.NEXT_PUBLIC_STREAM_RELAY_URL || joinUrl(API_BASE, "/stream/relay");
export const STREAM_RELAY_HEALTH_URL =
  process.env.NEXT_PUBLIC_STREAM_RELAY_HEALTH_URL || joinUrl(API_BASE, "/stream/relay/health");

// Application Configuration
export const APP_NAME = "Pencatatan Pengunjung System";
export const APP_VERSION = "1.2.0";

// Roles
export const ROLE_ADMIN = "ADMIN";
export const ROLE_OPERATOR = "OPERATOR";

// Pagination
export const DEFAULT_PAGE_SIZE = 20;

// Date formats
export const DATE_FORMAT = "YYYY-MM-DD";
export const DATETIME_FORMAT = "YYYY-MM-DD HH:mm:ss";

// Camera status
export const CAMERA_STATUS_ACTIVE = true;
export const CAMERA_STATUS_INACTIVE = false;

// Direction modes
export const DIRECTION_IN = "IN";
export const DIRECTION_OUT = "OUT";
export const DIRECTION_BOTH = "BOTH";

// Chart colors
export const CHART_COLORS = [
  "#3b82f6", // blue-500
  "#8b5cf6", // violet-500
  "#ec4899", // pink-500
  "#f59e0b", // amber-500
  "#10b981", // emerald-500
  "#06b6d4", // cyan-500
];

// Export formats
export const EXPORT_FORMAT_PDF = "pdf";
export const EXPORT_FORMAT_EXCEL = "excel";
export const EXPORT_FORMAT_CSV = "csv";

// Refresh intervals (ms)
export const POLL_INTERVAL = parsePositiveInt(
  process.env.NEXT_PUBLIC_POLL_INTERVAL_MS,
); // 30 seconds - polling interval for stats
export const STATS_REFRESH_INTERVAL = POLL_INTERVAL; // 30 seconds
export const LIVE_FEED_REFRESH_INTERVAL = 100; // 100ms for video feed
export const STREAM_HEALTH_INTERVAL = parsePositiveInt(
  process.env.NEXT_PUBLIC_STREAM_HEALTH_INTERVAL_MS,
); // 5 seconds - check if edge worker stream is healthy
