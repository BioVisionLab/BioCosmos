import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained server with only the traced runtime dependencies, so
  // the production image does not ship the full node_modules (dev tools
  // included) and the vulnerabilities that come with it.
  output: "standalone",
  // Country geometry for the species-by-country map. The file name is not
  // content-hashed, so a day rather than `immutable`: regenerating it with
  // backend/scripts/export_country_geometry.py reaches readers within a day.
  async headers() {
    return [
      {
        source: "/geo/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=86400, stale-while-revalidate=604800",
          },
        ],
      },
    ];
  },
  images: {
    localPatterns: [
      {
        pathname: "/api/images/**",
        search: "?*",
      },
      {
        pathname: "/api/images/**",
        search: "",
      },
    ],
  },
};

export default nextConfig;
