import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    localPatterns: [
      {
        pathname: '/api/images/**',
        search: '?*',
      },
      {
        pathname: '/api/images/**',
        search: '',
      },
    ],
  },
};

export default nextConfig;
