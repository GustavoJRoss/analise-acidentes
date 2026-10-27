import type { NextConfig } from "next";

// O navegador só fala com o Next; /api/* é repassado ao backend FastAPI (sem CORS).
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};

export default nextConfig;
