const path = require("path");
const { loadEnvConfig } = require("@next/env");

loadEnvConfig(path.resolve(__dirname, ".."));

function requireEnv(name) {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`[frontend] Missing required environment variable: ${name}`);
  }
  return value;
}

function withTrailingSlash(value) {
  return value.endsWith("/") ? value : `${value}/`;
}

function joinUrl(base, pathname) {
  return new URL(pathname, withTrailingSlash(base)).toString();
}

const backendUrl = requireEnv("BACKEND_URL");
const edgePublicBaseUrl = requireEnv("EDGE_PUBLIC_BASE_URL");
const pollIntervalMs = requireEnv("NEXT_PUBLIC_POLL_INTERVAL_MS");
const streamHealthIntervalMs = requireEnv("NEXT_PUBLIC_STREAM_HEALTH_INTERVAL_MS");
const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || process.env.APP_ENV || "").trim();

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
      {
        source: "/storage/:path*",
        destination: `${backendUrl}/storage/:path*`,
      },
    ];
  },

  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || backendUrl,
    NEXT_PUBLIC_EDGE_PUBLIC_BASE_URL:
      process.env.NEXT_PUBLIC_EDGE_PUBLIC_BASE_URL || edgePublicBaseUrl,
    NEXT_PUBLIC_STREAM_URL:
      process.env.NEXT_PUBLIC_STREAM_URL || joinUrl(edgePublicBaseUrl, "/video_feed"),
    NEXT_PUBLIC_STREAM_RAW_URL:
      process.env.NEXT_PUBLIC_STREAM_RAW_URL || joinUrl(edgePublicBaseUrl, "/video_feed_raw"),
    NEXT_PUBLIC_WEBRTC_SIGNAL_URL:
      process.env.NEXT_PUBLIC_WEBRTC_SIGNAL_URL || joinUrl(edgePublicBaseUrl, "/webrtc/offer"),
    NEXT_PUBLIC_STREAM_HEALTH_URL:
      process.env.NEXT_PUBLIC_STREAM_HEALTH_URL || joinUrl(edgePublicBaseUrl, "/health"),
    NEXT_PUBLIC_POLL_INTERVAL_MS: pollIntervalMs,
    NEXT_PUBLIC_STREAM_HEALTH_INTERVAL_MS: streamHealthIntervalMs,
    NEXT_PUBLIC_APP_ENV: appEnv,
  },

  images: {
    unoptimized: true,
  },
};

module.exports = nextConfig;
