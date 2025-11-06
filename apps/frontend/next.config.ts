import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
 
   eslint: {
    ignoreDuringBuilds: true, // ⬅️ allow production build even if ESLint errors exist
  }, 
  
};

export default nextConfig;
