/** @type {import('next').NextConfig} */
const nextConfig = {
  reactCompiler: true,
  trailingSlash: true,
  async redirects() {
    return [
      { source: "/About", destination: "/about", permanent: true },
      { source: "/Contact", destination: "/contact", permanent: true },
      { source: "/Privacy", destination: "/privacy", permanent: true },
      { source: "/Terms", destination: "/terms", permanent: true },
      { source: "/License", destination: "/license", permanent: true },
      { source: "/Licence", destination: "/license", permanent: true },
      { source: "/licence", destination: "/license", permanent: true },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "/api/proxy/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
