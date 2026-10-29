import type {NextConfig} from 'next';
import path from 'node:path';

const nextConfig: NextConfig = {
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || "",
  // Genera un servidor mínimo para el contenedor de uso normal. El modo de
  // desarrollo con Turbopack sigue disponible en compose.dev.yaml.
  output: "standalone",
  // Limita el trazado de archivos al propio frontend. Evita que Next detecte
  // por error un package-lock ajeno situado en un directorio padre al compilar.
  outputFileTracingRoot: path.join(__dirname),
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'placehold.co',
        port: '',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
        port: '',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'picsum.photos',
        port: '',
        pathname: '/**',
      },
    ],
  },
};

export default nextConfig;
