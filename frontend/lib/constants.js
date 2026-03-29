/**
 * Application constants
 */

// API Configuration
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

// Edge worker streaming endpoints
export const STREAM_URL = process.env.NEXT_PUBLIC_STREAM_URL || "http://localhost:5000/video_feed";
export const STREAM_RAW_URL = process.env.NEXT_PUBLIC_STREAM_RAW_URL || "http://localhost:5000/video_feed_raw";

// Application Configuration
export const APP_NAME = "Visitor Monitoring System";
export const APP_VERSION = "1.0.0";

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
export const POLL_INTERVAL = 30000; // 30 seconds - polling interval for stats
export const STATS_REFRESH_INTERVAL = 30000; // 30 seconds
export const LIVE_FEED_REFRESH_INTERVAL = 100; // 100ms for video feed
export const STREAM_HEALTH_INTERVAL = 5000; // 5 seconds - check if edge worker stream is healthy
