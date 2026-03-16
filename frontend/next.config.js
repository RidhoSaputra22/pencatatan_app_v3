/** @type {import('next').NextConfig} */
const nextConfig = {
  // API proxy — forward /api/* requests to backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ];
  },

  // Environment variables
  env: {
    BACKEND_URL: 'http://localhost:8000',
  },

  // Image optimization
  images: {
    domains: ['localhost'],
    unoptimized: true,
  },

  // Headers for video streaming
  async headers() {
    return [
      {
        source: '/video_feed',
        headers: [
          { key: 'Cache-Control', value: 'no-cache, no-store, must-revalidate' },
          { key: 'Pragma', value: 'no-cache' },
          { key: 'Expires', value: '0' },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
